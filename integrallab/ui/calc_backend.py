"""Ejecución de los trabajos de cálculo en un proceso aparte.

Responsabilidad:
Sacar SymPy del proceso de la interfaz. Un hilo de Python no basta: comparte el GIL con el
hilo de Qt, y mientras SymPy calcula, cada evento que la interfaz atiende en Python espera
su turno. Medido en esta auditoría: un clic que cuesta 195 ms pasó a 2,6 s y diez ciclos de
repintado de 34 ms a ~1 s con un hilo de cálculo activo. En un proceso aparte no hay GIL
compartido y la cancelación es real (se termina el proceso).

Diseño:
- Un único proceso "caliente" (contexto ``spawn``, portable a Windows y macOS) que importa
  SymPy una sola vez (~0,4 s) y atiende trabajos en serie (``pipeline.serve_requests``).
- Un hilo *daemon* escucha la tubería y reenvía cada mensaje como señal Qt (en cola al hilo
  principal). Pasa casi todo el tiempo bloqueado en ``recv`` (sin retener el GIL).
- Cancelar o reemplazar un trabajo en curso termina el proceso y arranca otro en segundo
  plano: el siguiente cálculo espera solo el arranque, no al cálculo abandonado.
"""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
import sys
import threading
from collections.abc import Iterator
from typing import Any

from integrallab.core.pipeline import CalculationRequest
from integrallab.viz.report_assets import serve_calculations

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _without_parent_main() -> Iterator[None]:
    """Evita que ``spawn`` vuelva a ejecutar el ``__main__`` del proceso padre en el hijo.

    La función del hijo vive en ``integrallab.core.pipeline``; el script de arranque no hace
    falta. Si el lanzador no usa ``if __name__ == "__main__":`` (scripts, IDEs, Jupyter), el
    hijo abriría otra ventana. Se ocultan ``__spec__``/``__file__`` solo durante ``start()``.
    """
    main = sys.modules.get("__main__")
    saved: dict[str, Any] = {}
    if main is not None:
        for attr in ("__spec__", "__file__"):
            if hasattr(main, attr):
                saved[attr] = getattr(main, attr)
        if "__spec__" in saved:
            main.__spec__ = None  # type: ignore[assignment]
        if "__file__" in saved:
            delattr(main, "__file__")
    try:
        yield
    finally:
        for attr, value in saved.items():
            setattr(main, attr, value)


# Reciclar el proceso tras N cálculos: SymPy acumula cachés y el RSS del hijo crecía
# ≈ 1,7 MB por cálculo distinto (117 → 318 MB en 120 cálculos), sin techo práctico.
RECYCLE_AFTER_JOBS = 60


def _close_quietly(conn: Any) -> None:
    with contextlib.suppress(OSError):
        conn.close()


class ProcessCalculationBackend:
    """Envía trabajos a un proceso de cálculo y publica sus resultados con señales Qt.

    ``signals`` debe exponer ``mesh_ready(int, object)``, ``assets_ready(int, object)``,
    ``finished(int, object)`` y ``failed(int, str)``.
    """

    def __init__(self, signals: Any) -> None:
        self._signals = signals
        self._ctx = multiprocessing.get_context("spawn")
        self._lock = threading.Lock()
        self._proc: Any = None
        self._conn: Any = None
        self._running_job: int | None = None
        self._jobs_done = 0
        self._closed = False
        self._spare: tuple[Any, Any] | None = None
        self._ensure_process()
        self._start_spare()

    # ── Ciclo de vida del proceso ────────────────────────────────────────────

    def _ensure_process(self) -> None:
        with self._lock:
            if self._closed or (self._proc is not None and self._proc.is_alive()):
                return
            parent_conn, child_conn = self._ctx.Pipe(duplex=True)
            proc = self._ctx.Process(
                target=serve_calculations, args=(child_conn,), name="integrallab-calculo", daemon=True
            )
            with _without_parent_main():
                proc.start()
            child_conn.close()
            self._proc, self._conn = proc, parent_conn
            self._jobs_done = 0
        threading.Thread(
            target=self._listen, args=(proc, parent_conn), name="integrallab-escucha", daemon=True
        ).start()

    def _start_spare(self) -> None:
        """Arranca un proceso de reserva para que el reemplazo no espere spawn."""
        if self._closed or getattr(self, '_spare', None) is not None:
            return
        try:
            parent_conn, child_conn = self._ctx.Pipe(duplex=True)
            proc = self._ctx.Process(
                target=serve_calculations, args=(child_conn,),
                name="integrallab-calculo-reserva", daemon=True
            )
            with _without_parent_main():
                proc.start()
            child_conn.close()
            with self._lock:
                self._spare = (proc, parent_conn)
            threading.Thread(
                target=self._listen, args=(proc, parent_conn),
                name="integrallab-escucha", daemon=True
            ).start()
        except Exception:
            logger.exception("No se pudo iniciar el proceso de reserva")

    def _restart(self) -> None:
        """Termina el proceso actual e intercambia por el proceso de reserva."""
        with self._lock:
            old_proc = self._proc
            spare = getattr(self, '_spare', None)
            if spare is not None:
                self._proc, self._conn = spare
                self._spare = None
            else:
                self._proc = self._conn = None
            self._running_job = None
            self._jobs_done = 0
        if old_proc is not None:
            old_proc.terminate()
            with contextlib.suppress(Exception):
                old_proc.join(timeout=0.2)
        # La conexion de un proceso vivo la cierra su hilo oyente al recibir EOF.
        multiprocessing.active_children()  # recoge procesos terminados
        self._ensure_process()  # arranca proceso principal si no habia reserva
        self._start_spare()    # arranca nueva reserva en segundo plano

    def shutdown(self) -> None:
        """Detiene el proceso de calculo (al cerrar la ventana)."""
        self._closed = True
        with self._lock:
            proc, conn = self._proc, self._conn
            spare = getattr(self, '_spare', None)
            self._proc = self._conn = None
            self._spare = None
            self._running_job = None
        if proc is not None:
            proc.terminate()
            with contextlib.suppress(Exception):
                proc.join(timeout=0.2)
        elif conn is not None:
            _close_quietly(conn)
        if spare:
            sp_proc, sp_conn = spare
            if sp_proc is not None:
                sp_proc.terminate()
                with contextlib.suppress(Exception):
                    sp_proc.join(timeout=0.2)
            elif sp_conn is not None:
                _close_quietly(sp_conn)

    # ── Trabajos ─────────────────────────────────────────────────────────────

    @property
    def is_busy(self) -> bool:
        return self._running_job is not None

    def submit(self, job_id: int, request: CalculationRequest) -> None:
        """Envía un trabajo. Si había otro en curso, se abandona terminando el proceso."""
        with self._lock:
            needs_restart = self._running_job is not None or self._jobs_done >= RECYCLE_AFTER_JOBS
        if needs_restart:
            self._restart()
        self._ensure_process()
        with self._lock:
            self._running_job = job_id
            conn = self._conn
        try:
            if conn is None:
                raise OSError("Conexión de tubería no disponible.")
            conn.send((job_id, request))
        except (OSError, ValueError):
            # El proceso murió entre la comprobación y el envío: un reintento con uno nuevo.
            self._restart()
            with self._lock:
                self._running_job = job_id
                conn = self._conn
            if conn is None:
                raise OSError("No hay proceso de cálculo disponible tras reiniciar.")
            conn.send((job_id, request))

    def recycle_if_idle(self) -> bool:
        """Reemplaza el proceso por uno limpio si ya atendió muchos cálculos y está libre.

        Se llama desde el hilo de Qt al terminar un cálculo: el arranque (~0,9 s) ocurre mientras
        el usuario lee el resultado, no en el siguiente clic.
        """
        if self._running_job is None and self._jobs_done >= RECYCLE_AFTER_JOBS:
            self._restart()
            return True
        return False

    def cancel(self) -> None:
        """Cancela el trabajo en curso (si lo hay)."""
        if self._running_job is not None:
            self._restart()

    def _listen(self, proc: Any, conn: Any) -> None:
        try:
            self._listen_loop(proc, conn)
        finally:
            _close_quietly(conn)  # único dueño del extremo padre de la tubería

    def _listen_loop(self, proc: Any, conn: Any) -> None:
        while True:
            try:
                if hasattr(conn, 'poll') and not conn.poll(0.1):
                    if proc is not None and not proc.is_alive():
                        break
                    continue
                kind, job_id, payload = conn.recv()
            except (EOFError, OSError, ValueError, TypeError):
                break  # proceso terminado o tubería cerrada
            except Exception:  # noqa: BLE001 - un mensaje ilegible no debe matar al oyente
                logger.exception("Mensaje ilegible del proceso de cálculo")
                break
            try:
                if kind == "mesh":
                    self._signals.mesh_ready.emit(job_id, payload)
                    continue
                if kind == "assets":
                    self._signals.assets_ready.emit(job_id, payload)
                    continue
                with self._lock:
                    if self._running_job == job_id:
                        self._running_job = None
                    if proc is self._proc:
                        self._jobs_done += 1
                if kind == "done":
                    self._signals.finished.emit(job_id, payload)
                else:
                    self._signals.failed.emit(job_id, str(payload))
            except RuntimeError:
                return  # la ventana ya no existe
        # El proceso murió sin que se le pidiera (p. ej. memoria agotada): avisar del trabajo.
        with self._lock:
            orphan = self._running_job if proc is self._proc else None
            if orphan is not None:
                self._running_job = None
                self._proc = self._conn = None
        if orphan is not None and not self._closed:
            try:
                self._signals.failed.emit(orphan, "El proceso de cálculo terminó inesperadamente.")
            except RuntimeError:
                pass

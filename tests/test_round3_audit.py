"""Regresiones de la tercera auditoría (post-parches): volúmenes erróneos, dominio y ciclo de vida.

Cada caso reproducía un fallo con la aplicación real antes de esta corrección:
- Casquillos con curvas que se cruzan: x vs x² en [0, 2] alrededor del eje Y daba −8π/3 (es 3π).
- Singularidad evitable en el punto medio: sin(x)/x en [-1, 1] daba −5,638 (es +5,638).
- solve() sin algoritmo (Max/Min): max(x, 1−x) vs 0,6 daba −0,7016 (es +0,7728).
- Fuera del dominio: sqrt(x) en [-1, 1] mostraba área «2/3 + 2*I/3» y V = 0 como éxito.
- Integrales no elementales: x**x mostraba «No disponible»; floor(x) un error interno de SymPy.
- El proceso de cálculo quedaba huérfano al 95 % de CPU si la interfaz moría de golpe.
- La tubería se cerraba desde el hilo de Qt con el oyente bloqueado en ``recv``.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import textwrap
import time

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from integrallab.core.operations import integrate_definite
from integrallab.core.parser import parse_math_expression
from integrallab.core.pipeline import CalculationRequest, run_calculation
from integrallab.core.solids import (
    Region2D,
    RevolutionAxis,
    SolidMesh3D,
    SolidMethod,
    VolumeResult,
    _reject_negative,
    calculate_revolution_volume,
    domain_error,
    inversion_is_cheap,
)
from integrallab.viz.threejs_wrapper import encode_solid_mesh


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


# ── Volúmenes que antes salían con signo o valor erróneo ────────────────────

@pytest.mark.parametrize(
    ("axis", "expected"),
    [(RevolutionAxis.y_axis(), 3 * math.pi), (RevolutionAxis.vertical(-1), 5 * math.pi)],
)
def test_shells_with_crossing_curves(axis: RevolutionAxis, expected: float) -> None:
    res = calculate_revolution_volume(Region2D("x", "x**2", 0, 2), axis, SolidMethod.SHELLS)
    assert res.is_success
    assert res.numeric_value == pytest.approx(expected, rel=1e-9)


def test_shells_with_crossings_show_one_integral_per_piece() -> None:
    res = calculate_revolution_volume(Region2D("x", "x**2", 0, 2), RevolutionAxis.y_axis(), SolidMethod.SHELLS)
    assert [s.expression_plain_text for s in res.steps][2] == "V_1 = pi/6; V_2 = 17*pi/6"
    assert res.integral_setup_latex.count("\\int") == 2  # sin |f − g| convertido en (f − g)


def test_spline_shells_with_crossings_is_fast_and_correct() -> None:
    """Spline de 5 puntos vs 0,2 en el eje Y: antes −18,67 (signo), luego 140 s en el desarrollo."""
    from integrallab.core.interpolation import interpolate_cubic_spline

    spline = interpolate_cubic_spline([(0, 0), (1, 1), (2, 0), (3, 1), (4, 0)]).to_parsed_expression("pts")
    t = time.perf_counter()
    res = calculate_revolution_volume(Region2D(spline, "0.2", 0, 4), RevolutionAxis.y_axis(), SolidMethod.SHELLS)
    assert res.is_success and res.numeric_value == pytest.approx(21.2734456, rel=1e-6)
    assert time.perf_counter() - t < 30


def test_removable_singularity_at_midpoint_keeps_orientation() -> None:
    res = calculate_revolution_volume(Region2D("sin(x)/x", None, -1, 1), RevolutionAxis.x_axis(), None)
    assert res.is_success
    assert res.numeric_value == pytest.approx(5.638150729701207, rel=1e-9)


def test_crossings_found_when_solve_has_no_algorithm() -> None:
    res = calculate_revolution_volume(Region2D("max(x,1-x)", "0.6", 0, 1), RevolutionAxis.x_axis(), None)
    assert res.is_success
    assert res.numeric_value == pytest.approx(0.7728317927830892, rel=1e-6)


def test_negative_volume_is_never_reported_as_success() -> None:
    bad = _reject_negative(VolumeResult(method=SolidMethod.DISKS, numeric_value=-2.0))
    assert not bad.is_success and "negativo" in (bad.error_message or "")
    ok = _reject_negative(VolumeResult(method=SolidMethod.DISKS, numeric_value=0.0))
    assert ok.is_success


# ── Dominio y resultados complejos ──────────────────────────────────────────

@pytest.mark.parametrize(("f", "a", "b"), [("sqrt(x)", -1, 1), ("asin(x)", 0, 2), ("log(x)", -1, 1)])
def test_domain_error_detects_non_real_regions(f: str, a: float, b: float) -> None:
    assert domain_error(Region2D(f, None, a, b))


@pytest.mark.parametrize(("f", "a", "b"), [("log(x)", 0, 1), ("sin(x)/x", -1, 1), ("1/sqrt(x)", 0, 1), ("x**2", -3, 3)])
def test_domain_error_allows_endpoints_and_removable_points(f: str, a: float, b: float) -> None:
    assert domain_error(Region2D(f, None, a, b)) is None


def test_complex_area_is_an_error() -> None:
    res = integrate_definite("sqrt(x)", -1, 1)
    assert not res.is_success and "complejo" in (res.error_message or "")


@pytest.mark.parametrize(("f", "a", "b"), [("1/x", "-1", "1"), ("tan(x)", "0", "2"), ("1/(x-1)**2", "0", "2")])
def test_vertical_asymptotes_inside_the_interval_are_divergent(f: str, a: str, b: str) -> None:
    res = integrate_definite(f, a, b)
    assert not res.is_success and "no converge" in (res.error_message or "")


def test_float_overflow_is_not_called_divergence() -> None:
    res = integrate_definite("exp(1000*x)", "0", "1")  # ≈ 1,97e431: converge
    assert not res.is_success and "finito" in (res.error_message or "") and "no converge" not in (res.error_message or "")


def test_non_elementary_integrals_get_a_numeric_value() -> None:
    area = integrate_definite("x**x", 0, 2)
    assert area.is_success and area.value == pytest.approx(2.833888, rel=1e-5)
    step = integrate_definite("floor(x)", 0, 3.5)
    assert step.is_success and step.value == pytest.approx(4.5, rel=1e-3)


# ── Pipeline ────────────────────────────────────────────────────────────────

def _req(f: str, a: str, b: str) -> CalculationRequest:
    return CalculationRequest(parse_math_expression(f), None, a, b, RevolutionAxis.x_axis(), None, 24, 18)


def test_pipeline_rejects_free_symbols() -> None:
    out = run_calculation(_req("a*x**2", "0", "1"))
    assert not out.res_2d.is_success and "símbolos sin valor: a" in (out.res_2d.error_message or "")


@pytest.mark.parametrize(("f", "a", "b"), [("log(x)", "0", "1"), ("sin(x)/x", "-1", "1")])
def test_display_mesh_is_finite_at_singular_points(f: str, a: str, b: str) -> None:
    meshes: list[SolidMesh3D] = []
    out = run_calculation(_req(f, a, b), on_mesh=meshes.append)
    assert out.vol_res.is_success
    assert meshes and np.all(np.isfinite(meshes[0].y_outer)) and np.all(np.isfinite(meshes[0].z_outer))
    assert encode_solid_mesh(meshes[0])  # el visor sí recibe la malla


def test_payload_rejects_float32_overflow() -> None:
    big = SolidMesh3D(x_outer=np.ones((3, 4)), y_outer=np.full((3, 4), 1e40), z_outer=np.ones((3, 4)))
    assert encode_solid_mesh(big) == {}


def test_inversion_cost_classifier() -> None:
    assert inversion_is_cheap(Region2D("x**2", None, 0, 1))
    assert not inversion_is_cheap(Region2D("exp(-x**2)*cos(3*x)**2 + 1", None, 0, 2))


# ── Interfaz ────────────────────────────────────────────────────────────────

def test_number_formatting(qapp: QApplication) -> None:
    from integrallab.ui.main_window import _fmt

    assert _fmt(0.62832) == "0.6283"
    assert _fmt(1.1350533e87) == "1.1351e+87"
    assert _fmt(1.0472e-36) == "1.0472e-36"


def test_failed_mesh_clears_the_viewer(qapp: QApplication, monkeypatch) -> None:
    from integrallab.ui.main_window import MainWindow

    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    cleared: list[bool] = []
    monkeypatch.setattr(w.threejs_viewer, "plot_solid_mesh", lambda *a, **k: False)
    monkeypatch.setattr(w.threejs_viewer, "clear_canvas", lambda: cleared.append(True))
    w.expression_input.setText("x**2")
    w.limit_a_input.setText("0")
    w.limit_b_input.setText("1")
    w._on_plot_clicked()
    assert cleared, "si el visor no puede dibujar, no debe quedarse con el sólido anterior"


def test_2d_view_follows_the_integration_limits(qapp: QApplication) -> None:
    from integrallab.ui.main_window import MainWindow

    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    w.expression_input.setText("x**2")
    w.limit_a_input.setText("20")
    w.limit_b_input.setText("30")
    w._on_plot_clicked()
    xs = w.canvas.curve_lines[0].get_xdata()
    assert min(xs) <= 20 and max(xs) >= 30  # la curva cubre la región sombreada
    w.expression_input.setText("a*x")
    w._on_plot_clicked()
    assert "símbolos sin valor" in w.status_bar.currentMessage()


# ── Proceso de cálculo ──────────────────────────────────────────────────────

def test_backend_recycles_idle_process_after_many_jobs(qapp: QApplication) -> None:
    from PySide6.QtCore import QObject, Signal

    from integrallab.ui import calc_backend

    class Signals(QObject):
        mesh_ready = Signal(int, object)
        assets_ready = Signal(int, object)
        finished = Signal(int, object)
        failed = Signal(int, str)

    backend = calc_backend.ProcessCalculationBackend(Signals())
    try:
        first = backend._proc
        backend._jobs_done = calc_backend.RECYCLE_AFTER_JOBS
        assert backend.recycle_if_idle() is True
        assert backend._proc is not first and backend._jobs_done == 0
    finally:
        backend.shutdown()


@pytest.mark.skipif(sys.platform == "win32", reason="usa /proc y señales POSIX")
def test_calc_process_exits_when_the_ui_dies() -> None:
    """Antes el hijo seguía calculando como huérfano (ppid=1) al matar la interfaz."""
    script = textwrap.dedent("""
        import os, sys, time
        from PySide6.QtCore import QObject, Signal
        from PySide6.QtWidgets import QApplication
        from integrallab.core.parser import parse_math_expression
        from integrallab.core.pipeline import CalculationRequest
        from integrallab.core.solids import RevolutionAxis
        from integrallab.ui.calc_backend import ProcessCalculationBackend
        app = QApplication(sys.argv)
        class S(QObject):
            mesh_ready = Signal(int, object); assets_ready = Signal(int, object)
            finished = Signal(int, object); failed = Signal(int, str)
        b = ProcessCalculationBackend(S())
        time.sleep(1.5)
        b.submit(1, CalculationRequest(parse_math_expression("sin(x)**3*exp(x)*log(x+2)"), None, "0", "2",
                                       RevolutionAxis.x_axis(), None))
        time.sleep(1.0)
        print(b._proc.pid, flush=True)
        os.kill(os.getpid(), 9)
    """)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env["PYTHONPATH"] = os.pathsep.join([os.getcwd(), env.get("PYTHONPATH", "")])
    proc = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True,
                          timeout=60, start_new_session=True)
    child = int(proc.stdout.strip().splitlines()[-1])
    deadline = time.time() + 10
    alive = True
    while time.time() < deadline:
        try:
            state = open(f"/proc/{child}/stat").read().split()[2]
            alive = state != "Z"
        except OSError:
            alive = False
        if not alive:
            break
        time.sleep(0.2)
    diag = ""
    if alive:
        try:
            st = open(f"/proc/{child}/status").read()
            diag = " | ".join(l for l in st.splitlines() if l.split(":")[0] in ("State", "PPid", "Threads"))
            diag += " | wchan=" + open(f"/proc/{child}/wchan").read()
            diag += " | cmd=" + open(f"/proc/{child}/cmdline").read().replace("\0", " ")[:150]
            diag += " | stderr=" + proc.stderr[-600:]
        except OSError:
            pass
        os.kill(child, 9)
    assert not alive, f"el proceso de cálculo quedó huérfano: {diag}"


def test_pipe_is_closed_only_by_its_listener_thread(qapp: QApplication) -> None:
    """Antes ``_restart``/``shutdown`` cerraban la tubería desde el hilo de Qt con el oyente en ``recv``.

    Eso daba ``TypeError`` dentro de multiprocessing (registrado como «Mensaje ilegible») y, peor,
    el número de descriptor liberado lo reutiliza la tubería del proceso nuevo: el oyente viejo
    podía leer (y desordenar) mensajes del proceso nuevo.
    """
    import threading as _th

    from PySide6.QtCore import QObject, Signal

    from integrallab.ui import calc_backend

    class Signals(QObject):
        mesh_ready = Signal(int, object)
        assets_ready = Signal(int, object)
        finished = Signal(int, object)
        failed = Signal(int, str)

    closers: list[str] = []

    class Spy:
        def __init__(self, conn) -> None:
            self._c = conn

        def __getattr__(self, name):
            return getattr(self._c, name)

        def close(self) -> None:
            closers.append(_th.current_thread().name)
            self._c.close()

    backend = calc_backend.ProcessCalculationBackend.__new__(calc_backend.ProcessCalculationBackend)
    real_ctx = calc_backend.multiprocessing.get_context("spawn")

    class Ctx:
        Process = real_ctx.Process

        @staticmethod
        def Pipe(duplex: bool = True):
            parent, child = real_ctx.Pipe(duplex=duplex)
            return Spy(parent), child

    backend._signals = Signals()
    backend._ctx = Ctx()
    backend._lock = _th.Lock()
    backend._proc = backend._conn = None
    backend._running_job = None
    backend._jobs_done = 0
    backend._closed = False
    backend._ensure_process()
    slow = CalculationRequest(parse_math_expression("log(x+1)*x + 1"), None, "0", "2", RevolutionAxis.vertical(-1), None)
    try:
        for i in range(4):
            backend.submit(i, slow)
            time.sleep(0.1)
        backend.cancel()
    finally:
        backend.shutdown()
    deadline = time.time() + 5
    while len(closers) < 6 and time.time() < deadline:
        time.sleep(0.05)
    assert closers and set(closers) == {"integrallab-escucha"}, closers


def test_restarting_a_busy_process_logs_no_pipe_errors(qapp: QApplication, caplog) -> None:
    """Humo: reemplazar y cancelar trabajos en curso no deja errores en el registro."""
    from PySide6.QtCore import QObject, Signal

    from integrallab.ui import calc_backend

    class Signals(QObject):
        mesh_ready = Signal(int, object)
        assets_ready = Signal(int, object)
        finished = Signal(int, object)
        failed = Signal(int, str)

    slow = CalculationRequest(parse_math_expression("log(x+1)*x + 1"), None, "0", "2", RevolutionAxis.vertical(-1), None)
    backend = calc_backend.ProcessCalculationBackend(Signals())
    try:
        for i in range(8):
            backend.submit(i, slow)
            time.sleep(0.05)
        backend.cancel()
        time.sleep(0.5)
    finally:
        backend.shutdown()
    time.sleep(0.3)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]

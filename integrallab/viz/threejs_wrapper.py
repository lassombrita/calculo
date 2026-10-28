"""Lienzo de visualización tridimensional interactivo para sólidos con Three.js.

Responsabilidad:
Proporcionar un widget Qt basado en QWebEngineView que renderiza sólidos de revolución
(SolidMesh3D) mediante WebGL y Three.js, con soporte para rotación orbital suave,
zoom continuo, paneo con ratón y materiales semitransparentes.

Puente Python → JavaScript:
La malla viaja como float32 en base64 (``encode_solid_mesh``), no como listas JSON de
floats: el texto es ~4 veces más corto, no hay bucles Python por elemento y Three.js
recibe exactamente los mismos float32 que antes construía a partir de las listas.
El visor informa por ``backend_status_changed`` si WebGL no está disponible, para que la
interfaz cambie al motor Matplotlib en lugar de mostrar una vista vacía.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = QWidget  # type: ignore[misc,assignment]
    QWebEnginePage = object  # type: ignore[misc,assignment]
    WEBENGINE_AVAILABLE = False

from integrallab.core.solids import AxisOrientation, SolidMesh3D

logger = logging.getLogger(__name__)


def _axis_line(mesh: SolidMesh3D) -> dict[str, list[float]]:
    pos = float(mesh.axis.position)
    if mesh.axis.orientation == AxisOrientation.HORIZONTAL:
        x_min = float(np.min(mesh.x_outer))
        x_max = float(np.max(mesh.x_outer))
        pad = max(abs(x_max - x_min) * 0.2, 0.5)
        return {"x": [x_min - pad, x_max + pad], "y": [pos, pos], "z": [0.0, 0.0]}
    y_min = float(np.min(mesh.y_outer))
    y_max = float(np.max(mesh.y_outer))
    pad = max(abs(y_max - y_min) * 0.2, 0.5)
    return {"x": [pos, pos], "y": [y_min - pad, y_max + pad], "z": [0.0, 0.0]}


_FLOAT32_SAFE = 1e37


def _valid_grid(x: np.ndarray | None, y: np.ndarray | None, z: np.ndarray | None) -> bool:
    if x is None or y is None or z is None or x.size == 0 or x.ndim != 2:
        return False
    if x.shape != y.shape or x.shape != z.shape or x.shape[0] < 2 or x.shape[1] < 2:
        return False
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and np.all(np.isfinite(z))):
        return False
    # El visor usa float32 (máx. ≈ 3,4e38): exp(x) en [0, 100] (radio 2,7e43) llegaba como Inf
    # y Three.js dibujaba una vista vacía.
    return bool(max(np.max(np.abs(x)), np.max(np.abs(y)), np.max(np.abs(z))) < _FLOAT32_SAFE)


def serialize_solid_mesh(
    mesh: SolidMesh3D,
    color_outer: str = "#5CE1FF",
    color_inner: str = "#FF6B8A",
    alpha: float = 0.6,
    show_axis: bool = True,
) -> dict[str, Any]:
    """Convierte un SolidMesh3D numérico en una estructura JSON serializable para Three.js.

    Formato de listas ``x``/``y``/``z`` (legible, para depuración y compatibilidad). El
    visor usa ``encode_solid_mesh``, que transporta los mismos datos en binario.

    Args:
        mesh: Malla de sólido con matrices NumPy 2D.
        color_outer: Color hexadecimal para la superficie exterior.
        color_inner: Color hexadecimal para la superficie interior (si aplica).
        alpha: Nivel de opacidad (0.0 a 1.0).
        show_axis: Si es True, incluye las coordenadas del eje de revolución.

    Returns:
        Diccionario serializable a JSON con arrays planos y dimensiones rows x cols.
    """
    if not mesh.is_valid:
        return {}

    if mesh.x_outer.size == 0 or mesh.x_outer.ndim != 2:
        return {}

    rows, cols = mesh.x_outer.shape
    if rows < 2 or cols < 2:
        return {}

    # Rechazar mallas con valores no finitos (NaN / Inf) para evitar triángulos falsos o picos
    if not (
        np.all(np.isfinite(mesh.x_outer))
        and np.all(np.isfinite(mesh.y_outer))
        and np.all(np.isfinite(mesh.z_outer))
    ):
        return {}

    payload: dict[str, Any] = {
        "color_outer": color_outer,
        "color_inner": color_inner,
        "alpha": alpha,
        "outer": {
            "x": mesh.x_outer.ravel().astype(float).tolist(),
            "y": mesh.y_outer.ravel().astype(float).tolist(),
            "z": mesh.z_outer.ravel().astype(float).tolist(),
            "rows": int(rows),
            "cols": int(cols),
        },
    }

    if (
        mesh.x_inner is not None
        and mesh.y_inner is not None
        and mesh.z_inner is not None
        and mesh.x_inner.size > 0
        and mesh.x_inner.ndim == 2
    ):
        i_rows, i_cols = mesh.x_inner.shape
        if i_rows >= 2 and i_cols >= 2:
            if not (
                np.all(np.isfinite(mesh.x_inner))
                and np.all(np.isfinite(mesh.y_inner))
                and np.all(np.isfinite(mesh.z_inner))
            ):
                return {}
            payload["inner"] = {
                "x": mesh.x_inner.ravel().astype(float).tolist(),
                "y": mesh.y_inner.ravel().astype(float).tolist(),
                "z": mesh.z_inner.ravel().astype(float).tolist(),
                "rows": int(i_rows),
                "cols": int(i_cols),
            }

    if show_axis:
        payload["axis_line"] = _axis_line(mesh)

    return payload


def _encode_grid(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> dict[str, Any]:
    """Empaqueta una rejilla como float32 little-endian intercalado (x, y, z) en base64."""
    xyz = np.stack((x.ravel(), y.ravel(), z.ravel()), axis=1).astype("<f4", copy=False)
    return {
        "rows": int(x.shape[0]),
        "cols": int(x.shape[1]),
        "positions_b64": base64.b64encode(np.ascontiguousarray(xyz).tobytes()).decode("ascii"),
    }


def encode_solid_mesh(
    mesh: SolidMesh3D,
    color_outer: str = "#5CE1FF",
    color_inner: str = "#FF6B8A",
    alpha: float = 0.6,
    show_axis: bool = True,
    fit_camera: bool = True,
) -> dict[str, Any]:
    """Versión compacta de ``serialize_solid_mesh`` para el puente con JavaScript.

    Mismas reglas de validación (mallas vacías o con NaN/Inf devuelven ``{}``), pero las
    posiciones viajan como float32 en base64 e incluye la orientación y posición del eje,
    que el visor necesita para cerrar el sólido con tapas.
    """
    if not mesh.is_valid or not _valid_grid(mesh.x_outer, mesh.y_outer, mesh.z_outer):
        return {}
    payload: dict[str, Any] = {
        "format": 2,
        "color_outer": color_outer,
        "color_inner": color_inner,
        "alpha": alpha,
        "fit_camera": fit_camera,
        "outer": _encode_grid(mesh.x_outer, mesh.y_outer, mesh.z_outer),
        "axis": {
            "orientation": "horizontal" if mesh.axis.orientation == AxisOrientation.HORIZONTAL else "vertical",
            "position": float(mesh.axis.position),
        },
    }
    if mesh.x_inner is not None and mesh.x_inner.size > 0:
        if not _valid_grid(mesh.x_inner, mesh.y_inner, mesh.z_inner):
            return {}
        payload["inner"] = _encode_grid(mesh.x_inner, mesh.y_inner, mesh.z_inner)  # type: ignore[arg-type]
    if show_axis:
        payload["axis_line"] = _axis_line(mesh)
    return payload


if WEBENGINE_AVAILABLE:

    class _ConsolePage(QWebEnginePage):  # type: ignore[misc]
        """Página que reenvía la consola JavaScript al logging de Python (sin fallos silenciosos)."""

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            lv = QWebEnginePage.JavaScriptConsoleMessageLevel
            py_level = {
                lv.InfoMessageLevel: logging.DEBUG,
                lv.WarningMessageLevel: logging.WARNING,
                lv.ErrorMessageLevel: logging.ERROR,
            }.get(level, logging.INFO)
            logger.log(py_level, "JS %s:%s %s", Path(str(source)).name, line, message)


class ThreeJSViewer(QWidget):
    """Widget de visualización 3D interactivo acelerado por hardware vía QWebEngineView y Three.js."""

    BUNDLE_PATH = Path(__file__).parent.parent / "resources" / "threejs_bundle.html"

    # (webgl_disponible, motivo). Se emite una vez tras cargar el visor, y de nuevo si cambia.
    backend_status_changed = Signal(bool, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 800,
        height: int = 600,
    ) -> None:
        """Inicializa el contenedor Qt y el navegador embebido WebEngine."""
        super().__init__(parent)
        self.setObjectName("ThreeJSViewer")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._is_ready: bool = False
        self._webgl_ok: bool | None = None
        self._status_reason: str = ""
        self._pending_mesh_data: dict[str, Any] | None = None
        # Control de vuelo: un solo envío a JavaScript a la vez. Si el deslizador va más rápido
        # que el visor, solo se conserva el último cuadro (antes las llamadas se encolaban y la
        # vista llegaba tarde).
        self._in_flight = False
        self._queued_data: dict[str, Any] | None = None

        if WEBENGINE_AVAILABLE:
            self._view = QWebEngineView(parent=self)
            self._view.setPage(_ConsolePage(self._view))
            self._layout.addWidget(self._view)
            self._view.loadFinished.connect(self._on_load_finished)
            if not self.load_bundle():
                QTimer.singleShot(0, lambda: self._set_status(False, "No se encontró threejs_bundle.html."))
        else:
            self._view = None
            QTimer.singleShot(
                0, lambda: self._set_status(False, "QtWebEngine no está instalado (PySide6-Addons).")
            )

        self.resize(width, height)

    # ── Estado del motor ─────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool | None:
        """True/False cuando ya se sabe si WebGL funciona; None mientras carga."""
        return self._webgl_ok

    @property
    def status_reason(self) -> str:
        """Motivo legible cuando WebGL no está disponible."""
        return self._status_reason

    def _set_status(self, ok: bool, reason: str = "") -> None:
        changed = ok != self._webgl_ok or reason != self._status_reason
        self._webgl_ok = ok
        self._status_reason = reason
        if not ok:
            self._is_ready = False
            if reason:
                logger.warning("Visor Three.js no disponible: %s", reason)
        if changed:
            self.backend_status_changed.emit(ok, reason)

    def load_bundle(self) -> bool:
        """Carga la plantilla HTML local empaquetada."""
        if not self._view or not self.BUNDLE_PATH.exists():
            return False
        self._view.load(QUrl.fromLocalFile(str(self.BUNDLE_PATH.resolve())))
        return True

    def _on_load_finished(self, ok: bool) -> None:
        """Al cargar la página, pregunta a JavaScript si WebGL arrancó (handshake)."""
        self._in_flight = False  # una página recargada no responde los envíos anteriores
        if not ok:
            self._set_status(False, "No se pudo cargar el visor 3D (threejs_bundle.html).")
            return
        self._view.page().runJavaScript(
            "(window.IntegralLab3D && window.IntegralLab3D.status) ? window.IntegralLab3D.status()"
            " : JSON.stringify({ok: false, reason: 'No se cargó el módulo Three.js.'})",
            0,
            self._on_status_reply,
        )

    def _on_status_reply(self, reply: object) -> None:
        try:
            info = json.loads(reply) if isinstance(reply, str) else {}
        except ValueError:
            info = {}
        ok = bool(info.get("ok"))
        reason = str(info.get("reason") or ("" if ok else "Respuesta inválida del visor 3D."))
        self._is_ready = ok
        self._set_status(ok, reason)
        if ok and self._pending_mesh_data is not None:
            data, self._pending_mesh_data = self._pending_mesh_data, None
            self._dispatch_render(data)

    # ── API de dibujo ────────────────────────────────────────────────────────

    def plot_solid_mesh(
        self,
        mesh: SolidMesh3D,
        color_outer: str = "#5CE1FF",
        color_inner: str = "#FF6B8A",
        alpha: float = 0.6,
        show_axis: bool = True,
        clear: bool = True,
        fit_camera: bool = True,
    ) -> bool:
        """Renderiza una malla tridimensional de revolución en Three.js.

        Args:
            mesh: Contenedor numérico SolidMesh3D.
            color_outer: Color hexadecimal de la superficie exterior.
            color_inner: Color hexadecimal de la superficie interior.
            alpha: Transparencia (0.0 a 1.0).
            show_axis: Si es True, traza el eje de giro.
            clear: Si es True, limpia el contenido previo.

        Returns:
            True si la malla es válida y se envió (o quedó en cola) para renderizar.
        """
        if not mesh.is_valid:
            return False

        data = encode_solid_mesh(
            mesh,
            color_outer=color_outer,
            color_inner=color_inner,
            alpha=alpha,
            show_axis=show_axis,
            fit_camera=fit_camera,
        )
        if not data:
            return False

        if not self._is_ready:
            self._pending_mesh_data = data
            return True

        return self._dispatch_render(data)

    def _dispatch_render(self, data: dict[str, Any]) -> bool:
        """Envía los datos de la malla al contexto de ejecución JavaScript."""
        if not self._view:
            return False

        # Escapar < y > para evitar cualquier cierre de contexto o inyección en el evaluador JS
        if self._in_flight:
            self._queued_data = data
            return True
        json_data = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e")
        js_code = (
            "(window.IntegralLab3D && window.IntegralLab3D.renderSolid) ? "
            f"window.IntegralLab3D.renderSolid({json_data}) : null"
        )
        self._in_flight = True
        self._view.page().runJavaScript(js_code, 0, self._on_render_reply)
        return True

    def _flush_queue(self) -> None:
        self._in_flight = False
        if self._queued_data is not None and self._is_ready:
            data, self._queued_data = self._queued_data, None
            self._dispatch_render(data)

    def _on_render_reply(self, reply: object) -> None:
        """Detecta, tras cada envío, si el contexto WebGL se perdió.

        Una respuesta vacía (una excepción puntual en ``renderSolid``) ya no desactiva WebGL para
        toda la sesión: se pregunta el estado real del visor y solo se desactiva si tampoco
        responde.
        """
        if reply is None:
            if self._view is not None:
                self._view.page().runJavaScript(
                    "window.IntegralLab3D ? window.IntegralLab3D.status() : null", 0, self._on_status_probe
                )
            else:
                self._flush_queue()
            return
        self._flush_queue()
        try:
            info = json.loads(reply) if isinstance(reply, str) else {}
        except ValueError:
            return
        if info and not info.get("ok", True):
            self._set_status(False, str(info.get("reason") or "WebGL dejó de responder."))

    def _on_status_probe(self, reply: object) -> None:
        if reply is None:
            self._in_flight = False
            self._queued_data = None
            self._set_status(False, "El visor 3D no respondió.")
            return
        try:
            info = json.loads(reply) if isinstance(reply, str) else {}
        except ValueError:
            info = {}
        if info and not info.get("ok", True):
            self._in_flight = False
            self._queued_data = None
            self._set_status(False, str(info.get("reason") or "WebGL dejó de responder."))
            return
        logger.debug("renderSolid falló una vez; el visor sigue activo")
        self._flush_queue()

    def _run(self, code: str) -> None:
        if self._view and self._is_ready:
            self._view.page().runJavaScript(f"if (window.IntegralLab3D) {{ {code} }}")

    def clear_canvas(self) -> None:
        """Limpia el contenido del lienzo tridimensional."""
        self._pending_mesh_data = None
        self._queued_data = None
        self._run("window.IntegralLab3D.clearCanvas();")

    def set_auto_rotate(self, enabled: bool) -> None:
        """Habilita o deshabilita la auto-rotación orbital de la cámara (se recuerda entre sólidos)."""
        flag = "true" if enabled else "false"
        self._run(f"window.IntegralLab3D.setAutoRotate({flag});")

    def fit_camera(self) -> None:
        """Reencuadra la cámara sobre el sólido actual."""
        self._run("window.IntegralLab3D.fitCamera();")

    def zoom(self, factor: float) -> None:
        """Aplica un factor multiplicativo a la distancia cámara–objetivo."""
        self._run(f"window.IntegralLab3D.zoom({float(factor)!r});")

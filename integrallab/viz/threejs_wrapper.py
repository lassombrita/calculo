"""Lienzo de visualización tridimensional interactivo para sólidos con Three.js.

Responsabilidad:
Proporcionar un widget Qt basado en QWebEngineView que renderiza sólidos de revolución
(SolidMesh3D) mediante WebGL y Three.js, con soporte para rotación orbital suave,
zoom continuo, paneo con ratón y materiales semitransparentes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    QWebEngineView = QWidget  # type: ignore[misc,assignment]
    WEBENGINE_AVAILABLE = False

from integrallab.core.solids import AxisOrientation, SolidMesh3D


def serialize_solid_mesh(
    mesh: SolidMesh3D,
    color_outer: str = "#5CE1FF",
    color_inner: str = "#FF6B8A",
    alpha: float = 0.6,
    show_axis: bool = True,
) -> dict[str, Any]:
    """Convierte un SolidMesh3D numérico en una estructura JSON serializable para Three.js.

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
            "x": [float(v) for v in mesh.x_outer.flatten()],
            "y": [float(v) for v in mesh.y_outer.flatten()],
            "z": [float(v) for v in mesh.z_outer.flatten()],
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
                "x": [float(v) for v in mesh.x_inner.flatten()],
                "y": [float(v) for v in mesh.y_inner.flatten()],
                "z": [float(v) for v in mesh.z_inner.flatten()],
                "rows": int(i_rows),
                "cols": int(i_cols),
            }

    if show_axis:
        pos = float(mesh.axis.position)
        if mesh.axis.orientation == AxisOrientation.HORIZONTAL:
            x_min = float(np.min(mesh.x_outer))
            x_max = float(np.max(mesh.x_outer))
            pad = max(abs(x_max - x_min) * 0.2, 0.5)
            payload["axis_line"] = {
                "x": [x_min - pad, x_max + pad],
                "y": [pos, pos],
                "z": [0.0, 0.0],
            }
        else:
            y_min = float(np.min(mesh.y_outer))
            y_max = float(np.max(mesh.y_outer))
            pad = max(abs(y_max - y_min) * 0.2, 0.5)
            payload["axis_line"] = {
                "x": [pos, pos],
                "y": [y_min - pad, y_max + pad],
                "z": [0.0, 0.0],
            }

    return payload


class ThreeJSViewer(QWidget):
    """Widget de visualización 3D interactivo acelerado por hardware vía QWebEngineView y Three.js."""

    BUNDLE_PATH = Path(__file__).parent.parent / "resources" / "threejs_bundle.html"

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
        self._pending_mesh_data: dict[str, Any] | None = None

        if WEBENGINE_AVAILABLE:
            self._view = QWebEngineView(parent=self)
            self._layout.addWidget(self._view)
            self._view.loadFinished.connect(self._on_load_finished)
            self.load_bundle()
        else:
            self._view = None

        self.resize(width, height)

    def load_bundle(self) -> bool:
        """Carga la plantilla HTML local empaquetada."""
        if not self._view or not self.BUNDLE_PATH.exists():
            return False
        self._view.load(QUrl.fromLocalFile(str(self.BUNDLE_PATH.resolve())))
        return True

    def _on_load_finished(self, ok: bool) -> None:
        """Notificación de que el contenido HTML/WebGL está listo para recibir comandos."""
        self._is_ready = ok
        if ok and self._pending_mesh_data is not None:
            self._dispatch_render(self._pending_mesh_data)
            self._pending_mesh_data = None

    def plot_solid_mesh(
        self,
        mesh: SolidMesh3D,
        color_outer: str = "#5CE1FF",
        color_inner: str = "#FF6B8A",
        alpha: float = 0.6,
        show_axis: bool = True,
        clear: bool = True,
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
            True si la malla es válida y se envió a renderizar, False en caso contrario.
        """
        if not mesh.is_valid:
            return False

        data = serialize_solid_mesh(
            mesh,
            color_outer=color_outer,
            color_inner=color_inner,
            alpha=alpha,
            show_axis=show_axis,
        )

        if not self._is_ready:
            self._pending_mesh_data = data
            return True

        return self._dispatch_render(data)

    def _dispatch_render(self, data: dict[str, Any]) -> bool:
        """Envía los datos de la malla al contexto de ejecución JavaScript."""
        if not self._view:
            return False

        json_data = json.dumps(data)
        js_code = f"if (window.IntegralLab3D) {{ window.IntegralLab3D.renderSolid({json_data}); }}"
        self._view.page().runJavaScript(js_code)
        return True

    def clear_canvas(self) -> None:
        """Limpia el contenido del lienzo tridimensional."""
        self._pending_mesh_data = None
        if self._view and self._is_ready:
            self._view.page().runJavaScript(
                "if (window.IntegralLab3D) { window.IntegralLab3D.clearCanvas(); }"
            )

    def set_auto_rotate(self, enabled: bool) -> None:
        """Habilita o deshabilita la auto-rotación orbital de la cámara."""
        if self._view and self._is_ready:
            flag = "true" if enabled else "false"
            self._view.page().runJavaScript(
                f"if (window.IntegralLab3D) {{ window.IntegralLab3D.setAutoRotate({flag}); }}"
            )

    def zoom(self, factor: float) -> None:
        """Aplica un factor multiplicativo al zoom de la cámara."""
        if self._view and self._is_ready:
            self._view.page().runJavaScript(
                f"if (window.IntegralLab3D) {{ window.IntegralLab3D.zoom({factor}); }}"
            )

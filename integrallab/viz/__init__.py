"""Módulo de visualización (2D y 3D) con soporte PySide6/Qt.

Proporciona integración con Matplotlib para la interfaz gráfica Qt en 2D
y Three.js empaquetado localmente para 3D, diseñado para consumir datos
puramente numéricos generados por el dominio matemático sin dependencias externas.
"""

from __future__ import annotations

from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.threejs_wrapper import ThreeJSViewer
from integrallab.viz.latex_render import latex_to_base64_html, render_latex_to_png_bytes

__all__ = [
    "PlotCanvas",
    "PlotCanvas3D",
    "ThreeJSViewer",
    "latex_to_base64_html",
    "render_latex_to_png_bytes",
]

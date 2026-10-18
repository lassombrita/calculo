"""Subpaquete de visualización para IntegralLab.

Provee integración con Matplotlib para la interfaz gráfica Qt en 2D y 3D,
diseñado para consumir datos puramente numéricos generados por el dominio matemático.
"""

from __future__ import annotations

from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.latex_render import latex_to_base64_html, render_latex_to_png_bytes

__all__ = [
    "PlotCanvas",
    "PlotCanvas3D",
    "latex_to_base64_html",
    "render_latex_to_png_bytes",
]


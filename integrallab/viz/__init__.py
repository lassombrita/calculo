"""Subpaquete de visualización para IntegralLab — Rediseño Premium.

Provee integración con Matplotlib para la interfaz gráfica Qt en 2D y 3D,
diseñado para consumir datos puramente numéricos generados por el dominio matemático.
"""

from __future__ import annotations

from integrallab.viz.canvas import PlotCanvas, PremiumCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.latex_render import latex_to_base64_html, render_latex_to_png_bytes, render_latex_png
from integrallab.viz.style import apply_mpl_theme, style_axes, glow

__all__ = [
    "PlotCanvas",  # Legacy canvas (sin efectos premium)
    "PremiumCanvas",  # Nuevo: reveal animation + tooltip magnético + glow
    "PlotCanvas3D",
    "latex_to_base64_html",
    "render_latex_to_png_bytes",
    "render_latex_png",
    "apply_mpl_theme",
    "style_axes",
    "glow",
]

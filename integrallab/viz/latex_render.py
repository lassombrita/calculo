"""Render de fórmulas LaTeX a PNG con el motor mathtext de Matplotlib (sin instalar TeX)."""
from __future__ import annotations

import io
from functools import lru_cache

from matplotlib.figure import Figure

from integrallab.viz.style import apply_mpl_theme, TEXT


@lru_cache(maxsize=256)
def render_latex_png(expr: str, color: str = "#E8ECF8", fontsize: float = 16.0, dpi: int = 288) -> bytes:
    """Devuelve un PNG transparente recortado al contenido de ``expr``.

    ``expr`` va sin signos ``$``. Si mathtext no puede interpretarla, se dibuja como texto plano
    para que la UI nunca falle por una fórmula mal formada.
    """
    apply_mpl_theme()
    expr = expr.strip().strip("$")
    for text in (f"${expr}$", expr.replace("$", "")):
        fig = Figure(figsize=(0.1, 0.1), dpi=dpi)
        fig.patch.set_alpha(0.0)
        fig.text(0.0, 0.0, text, color=color, fontsize=fontsize)
        buf = io.BytesIO()
        try:
            fig.savefig(buf, format="png", dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.05)
        except ValueError:
            continue
        return buf.getvalue()
    raise ValueError(f"No se pudo renderizar: {expr!r}")

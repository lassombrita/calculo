"""Estilo Matplotlib de IntegralLab: tema oscuro, cuadrícula sutil, glow en curvas y tipografía matemática.

Este módulo no calcula nada: solo define apariencia (ver AGENTS.md, "Visualización desacoplada").
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.patheffects as pe
from matplotlib import font_manager
from matplotlib.axes import Axes

TEXT = "#E8ECF8"
MUTED = "#8B95B5"
PANEL = "#101830"
EDGE = "#26325A"
SPINE = "#3A4673"
UI_FONT_CANDIDATES = ("Geist", "Segoe UI Variable", "Inter", "Segoe UI", "DejaVu Sans")


def _first_available_font() -> str:
    installed = {f.name for f in font_manager.fontManager.ttflist}
    return next((name for name in UI_FONT_CANDIDATES if name in installed), "DejaVu Sans")


def apply_mpl_theme() -> None:
    """Aplica rcParams globales. STIX da una tipografía matemática estilo LaTeX sin instalar TeX."""
    mpl.rcParams.update({
        "font.family": _first_available_font(),
        "mathtext.fontset": "stix",
        "text.color": TEXT,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "figure.facecolor": "none",
        "axes.facecolor": "none",
        "savefig.facecolor": "none",
        "axes.unicode_minus": False,
        "lines.antialiased": True,
        "path.simplify": True,
    })


def style_axes(ax: Axes) -> None:
    """Cuadrícula mayor/menor muy tenue, ejes en cero y sin marco superior/derecho."""
    ax.set_facecolor("none")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(SPINE)
        ax.spines[side].set_linewidth(0.9)
    ax.minorticks_on()
    ax.grid(True, which="major", color="#FFFFFF", alpha=0.055, linewidth=0.8)
    ax.grid(True, which="minor", color="#FFFFFF", alpha=0.022, linewidth=0.5)
    ax.tick_params(which="both", length=0, labelsize=9)
    ax.tick_params(which="major", pad=8)
    ax.axhline(0, color="#FFFFFF", alpha=0.22, linewidth=1.0, zorder=1)
    ax.axvline(0, color="#FFFFFF", alpha=0.22, linewidth=1.0, zorder=1)


def glow(color: str, width: float = 2.4) -> list[pe.AbstractPathEffect]:
    """Resplandor neón: dos trazos anchos y translúcidos bajo la línea principal."""
    return [
        pe.Stroke(linewidth=width + 7, foreground=color, alpha=0.07),
        pe.Stroke(linewidth=width + 3.5, foreground=color, alpha=0.16),
        pe.Normal(),
    ]

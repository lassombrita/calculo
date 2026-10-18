"""``PremiumCanvas``: gráfica con revelado animado, glow, cuadrícula fina y tooltips con imán.

Recibe series ya calculadas (arrays). No usa SymPy ni calcula nada. La suavidad de la curva
depende de la densidad de muestreo que entregue ``core`` (recomendado: >= 800 puntos).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QEasingCurve, QVariantAnimation
from PySide6.QtWidgets import QWidget

from integrallab.viz.style import EDGE, MUTED, PANEL, TEXT, apply_mpl_theme, glow, style_axes


@dataclass(frozen=True)
class Series:
    """Una curva lista para dibujar."""

    label: str
    x: np.ndarray
    y: np.ndarray
    color: str
    fill_to_zero: bool = False


class PremiumCanvas(FigureCanvasQTAgg):
    """Canvas translúcido pensado para vivir dentro de una ``GlassCard``."""

    REVEAL_MS = 1100

    def __init__(self, parent: QWidget | None = None) -> None:
        apply_mpl_theme()
        fig = Figure(figsize=(7, 4.5), dpi=100, layout="constrained")
        fig.patch.set_alpha(0.0)
        super().__init__(fig)
        self.setParent(parent)
        self.setStyleSheet("background: transparent;")
        self.ax = fig.add_subplot(111)
        self._series: list[Series] = []
        self._lines: list = []
        self._fills: list = []
        self._vline = None
        self._dots: list = []
        self._tip = None
        self._reveal = QVariantAnimation(self)
        self._reveal.setStartValue(0.0)
        self._reveal.setEndValue(1.0)
        self._reveal.setDuration(self.REVEAL_MS)
        self._reveal.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reveal.valueChanged.connect(self._on_reveal)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("axes_leave_event", lambda _e: self._hide_tip())
        self.show_empty_state()

    # -- API pública -------------------------------------------------
    def show_empty_state(self, message: str = "Escribe una función para ver su gráfica") -> None:
        self._reveal.stop()
        self.ax.clear()
        self._lines, self._fills, self._dots = [], [], []
        self._vline = self._tip = None
        self.ax.set_axis_off()
        self.ax.text(0.5, 0.5, message, transform=self.ax.transAxes, ha="center", va="center",
                     color=MUTED, fontsize=11)
        self.draw_idle()

    def plot_series(self, series: list[Series], *, animate: bool = True) -> None:
        """Dibuja las series; con ``animate`` la curva se traza de izquierda a derecha."""
        self._reveal.stop()
        self._reset_axes()
        self._series = list(series)
        if not self._series:
            self.show_empty_state()
            return
        self._set_limits()
        for s in self._series:
            (line,) = self.ax.plot(
                s.x, s.y, color=s.color, linewidth=2.4, label=s.label,
                solid_capstyle="round", solid_joinstyle="round", path_effects=glow(s.color), zorder=3,
            )
            self._lines.append(line)
            if s.fill_to_zero:
                self._fills.append(self.ax.fill_between(s.x, 0, s.y, color=s.color, alpha=0.0, linewidth=0, zorder=2))
        legend = self.ax.legend(loc="upper left", frameon=True, facecolor=PANEL, edgecolor=EDGE,
                                labelcolor=TEXT, fontsize=10, framealpha=0.9)
        legend.get_frame().set_linewidth(0.8)
        self._build_tooltip()
        if animate:
            self._on_reveal(0.0)
            self._reveal.start()
        else:
            self._on_reveal(1.0)

    # -- internos ----------------------------------------------------
    def _reset_axes(self) -> None:
        self.ax.clear()
        self.ax.set_axis_on()
        style_axes(self.ax)
        self._lines, self._fills, self._dots = [], [], []
        self._vline = self._tip = None

    def _set_limits(self) -> None:
        xs = np.concatenate([s.x for s in self._series])
        ys = np.concatenate([s.y for s in self._series])
        ys = ys[np.isfinite(ys)]
        xs = xs[np.isfinite(xs)]
        if xs.size:
            self.ax.set_xlim(float(xs.min()), float(xs.max()))
        if ys.size:
            lo, hi = float(ys.min()), float(ys.max())
            pad = (hi - lo) * 0.12 or 1.0
            self.ax.set_ylim(lo - pad, hi + pad)

    def _on_reveal(self, value: object) -> None:
        t = float(value)  # type: ignore[arg-type]
        for s, line in zip(self._series, self._lines):
            n = max(2, int(len(s.x) * t))
            line.set_data(s.x[:n], s.y[:n])
        for poly in self._fills:
            poly.set_alpha(0.16 * max(0.0, (t - 0.45) / 0.55))
        self.draw_idle()

    def _build_tooltip(self) -> None:
        self._vline = self.ax.axvline(0, color="#FFFFFF", alpha=0.28, linewidth=1.0,
                                      linestyle=(0, (3, 3)), visible=False, zorder=4)
        self._dots = [
            self.ax.plot([], [], "o", markersize=9, markerfacecolor="#05070D", markeredgecolor=s.color,
                         markeredgewidth=2.2, zorder=6, visible=False)[0]
            for s in self._series
        ]
        self._tip = self.ax.annotate(
            "", xy=(0, 0), xytext=(16, 16), textcoords="offset points", fontsize=10, color=TEXT, multialignment="left",
            bbox={"boxstyle": "round,pad=0.55,rounding_size=0.6", "fc": PANEL, "ec": EDGE, "alpha": 0.96},
            visible=False, zorder=10, annotation_clip=False,
        )

    def _on_move(self, event) -> None:
        if event.inaxes is not self.ax or not self._series or event.xdata is None or self._tip is None:
            return
        lines_txt, anchor = [], None
        for s, dot in zip(self._series, self._dots):
            i = int(np.clip(np.searchsorted(s.x, event.xdata), 0, len(s.x) - 1))
            if i > 0 and abs(s.x[i - 1] - event.xdata) < abs(s.x[i] - event.xdata):
                i -= 1
            x, y = float(s.x[i]), float(s.y[i])
            if not np.isfinite(y):
                dot.set_visible(False)
                continue
            dot.set_data([x], [y])
            dot.set_visible(True)
            lines_txt.append(f"{s.label} = {y:.4f}")
            anchor = anchor or (x, y)
        if anchor is None:
            self._hide_tip()
            return
        x0, x1 = self.ax.get_xlim()
        right_half = anchor[0] > (x0 + x1) / 2
        self._vline.set_xdata([anchor[0], anchor[0]])
        self._vline.set_visible(True)
        self._tip.xy = anchor
        self._tip.set_text("\n".join([f"x = {anchor[0]:.4f}", *lines_txt]))
        self._tip.set_position((-16, 16) if right_half else (16, 16))
        self._tip.set_ha("right" if right_half else "left")
        self._tip.set_visible(True)
        self.draw_idle()

    def _hide_tip(self) -> None:
        if self._tip is None:
            return
        self._tip.set_visible(False)
        self._vline.set_visible(False)
        for dot in self._dots:
            dot.set_visible(False)
        self.draw_idle()

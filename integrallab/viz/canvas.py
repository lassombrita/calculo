"""Módulo de visualización con Matplotlib para la interfaz Qt.

Responsabilidad:
Proporcionar un widget Qt (FigureCanvasQTAgg) para renderizar gráficas matemáticas 2D
a partir de datos numéricos ya calculados (CurveData), sin dependencias simbólicas ni SymPy.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PySide6.QtCore import QEasingCurve, QVariantAnimation

from integrallab.core.sampling import CurveData
from integrallab.viz.style import (
    EDGE, PANEL, TEXT, apply_mpl_theme, glow, style_axes, style_legend,
)

# Ciclo de color semántico: f(x) cian, g(x) violeta, luego ámbar / menta / rosa.
CURVE_COLORS: tuple[str, ...] = ("#5CE1FF", "#9D8CFF", "#FFB454", "#6BF0B2", "#FF6B8A")
REVEAL_MS: int = 900


class PlotCanvas(FigureCanvasQTAgg):
    """Widget de visualización 2D embebido en Qt mediante Matplotlib.

    Recibe exclusivamente datos procesados (CurveData) y gestiona la estética
    y el renderizado de los ejes, grilla y leyendas. Estilo "premium": fondo
    translúcido (vive sobre una GlassCard), glow en las curvas, tooltip con imán
    al punto más cercano y revelado animado de izquierda a derecha (``play_reveal``).
    """

    def __init__(
        self,
        parent: object | None = None,
        width: float = 6.0,
        height: float = 4.5,
        dpi: int = 100,
    ) -> None:
        """Inicializa la figura y el lienzo de Matplotlib para Qt.

        Args:
            parent: Widget padre en la jerarquía de PySide6 (opcional).
            width: Ancho inicial de la figura en pulgadas.
            height: Alto inicial de la figura en pulgadas.
            dpi: Resolución de puntos por pulgada.
        """
        apply_mpl_theme()
        # Sin ``tight_layout=True``: ese motor recalcula el layout en CADA dibujo (≈ la mitad del
        # coste de un draw). El layout se recalcula solo cuando cambia algo estructural.
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.figure.patch.set_alpha(0.0)
        super().__init__(self.figure)
        self.setStyleSheet("background: transparent;")
        if parent is not None:
            self.setParent(parent)  # type: ignore[arg-type]

        self.axes = self.figure.add_subplot(111)
        self._curve_lines: list[object] = []
        self._shade_collections: list[object] = []
        self._vline = None
        self._dots: list[object] = []
        self._tip = None
        self._layout_dirty = True
        self._draw_deferred = False
        self._tip_bg = None          # fondo para blitting del tooltip
        self._revealing = False
        self._reveal_bg = None       # fondo (sin curvas) para blitting del revelado
        self._reveal = QVariantAnimation(self)
        self._reveal.setStartValue(0.0)
        self._reveal.setEndValue(1.0)
        self._reveal.setDuration(REVEAL_MS)
        self._reveal.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reveal.valueChanged.connect(self._on_reveal)
        self._reveal.finished.connect(self._end_reveal)
        self._setup_axes_style()
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("axes_leave_event", lambda _e: self._hide_tip())
        self.mpl_connect("draw_event", self._on_draw_event)

    # ── Dibujo eficiente ────────────────────────────────────────────────────

    def _hidden_in_visible_window(self) -> bool:
        """True si la ventana está a la vista pero este lienzo no (otra pestaña activa)."""
        win = self.window()
        return win is not None and win.isVisible() and not self.isVisible()

    def _can_blit(self) -> bool:
        return self.isVisible() and self.get_width_height()[0] > 0

    def draw(self) -> None:  # noqa: D102 - sobrescribe FigureCanvasQTAgg.draw
        # Un lienzo oculto en otra pestaña no se dibuja: se pospone hasta que se muestre.
        if self._hidden_in_visible_window():
            self._draw_deferred = True
            return
        if self._layout_dirty:
            self._layout_dirty = False
            try:
                self.figure.tight_layout()
            except Exception:  # noqa: BLE001 - un layout imposible no debe impedir el dibujo
                pass
        super().draw()

    def draw_idle(self) -> None:  # noqa: D102
        if self._hidden_in_visible_window():
            self._draw_deferred = True
            return
        super().draw_idle()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._draw_deferred:
            self._draw_deferred = False
            self.draw_idle()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._layout_dirty = True
        self._tip_bg = None
        super().resizeEvent(event)

    def _on_draw_event(self, _event) -> None:
        """Tras cada dibujo completo, guarda el fondo para el blitting (tooltip y revelado)."""
        if not self._can_blit():
            return
        try:
            bg = self.copy_from_bbox(self.figure.bbox)
        except Exception:  # noqa: BLE001
            return
        if self._revealing:
            self._reveal_bg = bg
            return
        self._tip_bg = bg
        # Un dibujo completo no incluye los artistas animados: el tooltip reaparece al mover el ratón.
        if self._tip is not None and self._tip.get_visible():
            for artist in (self._vline, *self._dots, self._tip):
                if artist is not None:
                    artist.set_visible(False)  # type: ignore[attr-defined]

    def _setup_axes_style(self) -> None:
        """Configura la estética por defecto de los ejes y grilla."""
        style_axes(self.axes)
        self.axes.set_xlabel("x")
        self.axes.set_ylabel("y")
        self._vline = None
        self._dots = []
        self._tip = None
        self._tip_bg = None
        self._layout_dirty = True

    def _legend(self) -> None:
        """Crea la leyenda con el estilo de cristal oscuro."""
        style_legend(self.axes.legend(loc="best", fontsize=10))

    def _next_color(self) -> str:
        return CURVE_COLORS[len(self._curve_lines) % len(CURVE_COLORS)]

    def _plot_line(self, curve: CurveData, color: str, linestyle: str = "-") -> list[object]:
        """Traza una curva con glow y extremos redondeados."""
        kwargs: dict[str, object] = {
            "color": color,
            "linestyle": linestyle,
            "linewidth": 2.3,
            "solid_capstyle": "round",
            "solid_joinstyle": "round",
            "path_effects": glow(color, 2.3),
            "zorder": 3,
        }
        if curve.label:
            kwargs["label"] = curve.label
        return self.axes.plot(curve.x_values, curve.y_values, **kwargs)

    @property
    def curve_lines(self) -> list[object]:
        """Retorna la lista de líneas correspondientes a curvas graficadas."""
        return list(self._curve_lines)

    @property
    def shade_collections(self) -> list[object]:
        """Retorna la lista de polígonos correspondientes a regiones sombreadas."""
        return list(self._shade_collections)

    def set_y_window(self, window: tuple[float, float] | None) -> None:
        """Fija la ventana vertical visible (útil con asíntotas); None conserva el autoajuste.

        Args:
            window: ``(y_bajo, y_alto)`` o None.
        """
        if window is None:
            return
        self.axes.set_ylim(window[0], window[1])
        self._layout_dirty = True  # el ancho de las etiquetas del eje y puede cambiar
        self.draw_idle()

    def clear_canvas(self) -> None:
        """Limpia los ejes y restablece el formato básico."""
        self.axes.clear()
        self._curve_lines.clear()
        self._shade_collections.clear()
        self._setup_axes_style()
        self.draw_idle()

    def _clear_data(self) -> None:
        """Quita curvas, sombreados, tooltip y leyenda conservando los ejes ya estilizados.

        ``axes.clear()`` + ``style_axes`` regeneraba todas las marcas (mayores y menores) y su
        texto en cada gráfica nueva: era la parte más cara de pulsar «Generar».
        """
        for artist in (*self._curve_lines, *self._shade_collections, self._vline, *self._dots, self._tip):
            if artist is not None:
                try:
                    artist.remove()  # type: ignore[attr-defined]
                except (ValueError, NotImplementedError):
                    pass
        legend = self.axes.get_legend()
        if legend is not None:
            legend.remove()
        self._curve_lines.clear()
        self._shade_collections.clear()
        self._vline = None
        self._dots = []
        self._tip = None
        self._tip_bg = None
        self.axes.set_autoscale_on(True)
        self._layout_dirty = True

    def _autoscale(self) -> None:
        self.axes.relim()
        self.axes.autoscale_view()

    def plot_curve(
        self,
        curve: CurveData,
        color: str | None = None,
        linestyle: str = "-",
        clear: bool = True,
    ) -> bool:
        """Renderiza una curva numérica en el lienzo.

        Args:
            curve: Estructura CurveData con listas de puntos numéricos.
            color: Color opcional para el trazado.
            linestyle: Estilo de línea (ej. '-', '--', ':').
            clear: Si es True, limpia el gráfico antes de trazar la nueva curva.

        Returns:
            True si la curva se graficó correctamente, False si contenía errores.
        """
        if not curve.is_valid:
            return False

        if clear:
            self._clear_data()

        lines = self._plot_line(curve, color or self._next_color(), linestyle)
        self._curve_lines.extend(lines)
        if clear:
            self._autoscale()

        if curve.label:
            self._legend()

        self.draw_idle()
        return True

    def plot_curves(
        self,
        curves: Sequence[CurveData],
        clear: bool = True,
    ) -> int:
        """Renderiza múltiples curvas simultáneamente en los mismos ejes.

        Args:
            curves: Secuencia de objetos CurveData a graficar.
            clear: Si es True, limpia el lienzo previo.

        Returns:
            Cantidad de curvas graficadas con éxito.
        """
        if clear:
            self._clear_data()

        plotted_count = 0
        has_legend = False

        for curve in curves:
            if not curve.is_valid:
                continue

            if curve.label:
                has_legend = True

            lines = self._plot_line(curve, self._next_color())
            self._curve_lines.extend(lines)
            plotted_count += 1

        if has_legend:
            self._legend()
        if clear:
            self._autoscale()

        self.draw_idle()
        return plotted_count

    def shade_region(
        self,
        x_values: Sequence[float],
        y_values: Sequence[float],
        y2_values: Sequence[float] | float = 0.0,
        color: str = "#9D8CFF",
        alpha: float = 0.35,
        label: str | None = None,
    ) -> bool:
        """Sombrea la región bajo o entre curvas en el lienzo con fill_between.

        Args:
            x_values: Coordenadas en X del área a sombrear.
            y_values: Coordenadas superiores (o curva principal) en Y.
            y2_values: Coordenadas inferiores en Y (por defecto el eje y=0.0).
            color: Color de relleno hexadecimal o nombre estándar.
            alpha: Nivel de transparencia entre 0.0 y 1.0.
            label: Etiqueta opcional para incluir en la leyenda.

        Returns:
            True si se aplicó el sombreado con éxito, False si no hay suficientes puntos.
        """
        if len(x_values) < 2 or len(y_values) < 2:
            return False

        kwargs: dict[str, object] = {
            "color": color,
            "alpha": alpha,
            "linewidth": 0,
            "zorder": 2,
        }
        if label:
            kwargs["label"] = label

        poly = self.axes.fill_between(x_values, y_values, y2_values, **kwargs)
        self._shade_collections.append(poly)

        if label:
            self._legend()

        self.draw_idle()
        return True

    # ── Revelado animado ────────────────────────────────────────────────

    def play_reveal(self, duration_ms: int = REVEAL_MS) -> None:
        """Traza curvas y sombreado de izquierda a derecha.

        Usa un recorte (clip) que crece, así que los datos de las líneas no se modifican.
        Con el lienzo visible se anima por *blitting*: el fondo (ejes, rejilla, leyenda) se
        dibuja una sola vez y en cada cuadro solo se pintan las curvas. Antes cada cuadro era
        un redibujado completo de ~90 ms, así que la animación de 900 ms mostraba ~7 cuadros
        y bloqueaba la interfaz casi un segundo. Si el lienzo no está a la vista, no se anima.
        """
        self._reveal.stop()
        if self._hidden_in_visible_window() or not self._revealable():
            self._end_reveal()
            return
        self._hide_tip()
        self._revealing = self._can_blit()
        self._reveal_bg = None
        if self._revealing:
            for artist in self._revealable():
                artist.set_animated(True)  # type: ignore[attr-defined]
        self._reveal.setDuration(duration_ms)
        self._on_reveal(0.0)
        self._reveal.start()

    def _revealable(self) -> list[object]:
        return [*self._curve_lines, *self._shade_collections]

    def _on_reveal(self, value: object) -> None:
        t = float(value)  # type: ignore[arg-type]
        for artist in self._revealable():
            clip = Rectangle((0.0, 0.0), max(t, 1e-3), 1.0, transform=self.axes.transAxes)
            artist.set_clip_path(clip)  # type: ignore[attr-defined]
        if not (self._revealing and self._can_blit()):
            self.draw_idle()
            return
        if self._reveal_bg is None:
            self.draw()  # dibujo completo sin los artistas animados → fondo (vía draw_event)
            if self._reveal_bg is None:
                self.draw_idle()
                return
        self.restore_region(self._reveal_bg)
        for artist in self._revealable():
            artist.set_animated(True)  # type: ignore[attr-defined]  (también los añadidos durante el revelado)
            self.axes.draw_artist(artist)  # type: ignore[arg-type]
        self.blit(self.figure.bbox)

    def _end_reveal(self) -> None:
        self._revealing = False
        self._reveal_bg = None
        for artist in self._revealable():
            artist.set_animated(False)  # type: ignore[attr-defined]
            artist.set_clip_path(self.axes.patch)  # type: ignore[attr-defined]
        self.draw_idle()

    # ── Tooltip magnético ───────────────────────────────────────────────

    def _build_tip(self) -> None:
        # Artistas "animados": no forman parte del dibujo completo; se pintan por blitting
        # sobre el fondo guardado (≈3 ms por movimiento del ratón en lugar de ~90-140 ms).
        self._vline = self.axes.axvline(
            0, color="#FFFFFF", alpha=0.28, linewidth=1.0, linestyle=(0, (3, 3)), visible=False, zorder=4,
            animated=True,
        )
        self._dots = [
            self.axes.plot(
                [], [], "o", markersize=9, markerfacecolor="#05070D", markeredgecolor=line.get_color(),  # type: ignore[attr-defined]
                markeredgewidth=2.2, zorder=6, visible=False, animated=True,
            )[0]
            for line in self._curve_lines
        ]
        self._tip = self.axes.annotate(
            "", xy=(0, 0), xytext=(16, 16), textcoords="offset points", fontsize=10, color=TEXT,
            multialignment="left",
            bbox={"boxstyle": "round,pad=0.55,rounding_size=0.6", "fc": PANEL, "ec": EDGE, "alpha": 0.96},
            visible=False, zorder=10, annotation_clip=False, animated=True,
        )

    def _blit_tip(self) -> None:
        """Pinta el tooltip sobre el fondo guardado; si no hay fondo, redibuja normalmente."""
        if self._revealing or self._tip_bg is None or not self._can_blit():
            self.draw_idle()
            return
        self.restore_region(self._tip_bg)
        for artist in (self._vline, *self._dots, self._tip):
            if artist is not None and artist.get_visible():  # type: ignore[attr-defined]
                self.axes.draw_artist(artist)  # type: ignore[arg-type]
        self.blit(self.figure.bbox)

    def _on_move(self, event) -> None:
        if self._revealing:
            return
        if event.inaxes is not self.axes or event.xdata is None or not self._curve_lines:
            return
        if self._tip is None:
            self._build_tip()
        rows: list[str] = []
        anchor: tuple[float, float] | None = None
        for line, dot in zip(self._curve_lines, self._dots):
            xs = np.asarray(line.get_xdata(), dtype=float)  # type: ignore[attr-defined]
            ys = np.asarray(line.get_ydata(), dtype=float)  # type: ignore[attr-defined]
            if xs.size == 0 or not np.any(np.isfinite(xs)):
                continue
            i = int(np.nanargmin(np.abs(xs - event.xdata)))
            x, y = float(xs[i]), float(ys[i])
            if not np.isfinite(y):
                dot.set_visible(False)  # type: ignore[attr-defined]
                continue
            dot.set_data([x], [y])  # type: ignore[attr-defined]
            dot.set_visible(True)  # type: ignore[attr-defined]
            label = str(line.get_label())  # type: ignore[attr-defined]
            rows.append(f"{label} = {y:.4f}" if label and not label.startswith("_") else f"y = {y:.4f}")
            anchor = anchor or (x, y)
        if anchor is None:
            self._hide_tip()
            return
        x0, x1 = self.axes.get_xlim()
        right_half = anchor[0] > (x0 + x1) / 2
        self._vline.set_xdata([anchor[0], anchor[0]])  # type: ignore[union-attr]
        self._vline.set_visible(True)  # type: ignore[union-attr]
        self._tip.xy = anchor  # type: ignore[union-attr]
        self._tip.set_text("\n".join([f"x = {anchor[0]:.4f}", *rows]))  # type: ignore[union-attr]
        self._tip.set_position((-16, 16) if right_half else (16, 16))  # type: ignore[union-attr]
        self._tip.set_ha("right" if right_half else "left")  # type: ignore[union-attr]
        self._tip.set_visible(True)  # type: ignore[union-attr]
        self._blit_tip()

    def _hide_tip(self) -> None:
        if self._tip is None:
            return
        self._tip.set_visible(False)
        self._vline.set_visible(False)  # type: ignore[union-attr]
        for dot in self._dots:
            dot.set_visible(False)  # type: ignore[attr-defined]
        self._blit_tip()

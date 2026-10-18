"""Módulo de visualización con Matplotlib para la interfaz Qt.

Responsabilidad:
Proporcionar un widget Qt (FigureCanvasQTAgg) para renderizar gráficas matemáticas 2D
a partir de datos numéricos ya calculados (CurveData), sin dependencias simbólicas ni SymPy.
"""

from __future__ import annotations

from typing import Sequence

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from integrallab.core.sampling import CurveData


class PlotCanvas(FigureCanvasQTAgg):
    """Widget de visualización 2D embebido en Qt mediante Matplotlib.

    Recibe exclusivamente datos procesados (CurveData) y gestiona la estética
    y el renderizado de los ejes, grilla y leyendas.
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
        self.figure = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        super().__init__(self.figure)
        if parent is not None:
            self.setParent(parent)  # type: ignore[arg-type]

        self.axes = self.figure.add_subplot(111)
        self._curve_lines: list[object] = []
        self._shade_collections: list[object] = []
        self._setup_axes_style()

    def _setup_axes_style(self) -> None:
        """Configura la estética por defecto de los ejes y grilla."""
        self.axes.grid(True, linestyle="--", alpha=0.6)
        self.axes.axhline(0, color="black", linewidth=0.8, alpha=0.7)
        self.axes.axvline(0, color="black", linewidth=0.8, alpha=0.7)
        self.axes.set_xlabel("x")
        self.axes.set_ylabel("y")

    @property
    def curve_lines(self) -> list[object]:
        """Retorna la lista de líneas correspondientes a curvas graficadas."""
        return list(self._curve_lines)

    @property
    def shade_collections(self) -> list[object]:
        """Retorna la lista de polígonos correspondientes a regiones sombreadas."""
        return list(self._shade_collections)

    def clear_canvas(self) -> None:
        """Limpia los ejes y restablece el formato básico."""
        self.axes.clear()
        self._curve_lines.clear()
        self._shade_collections.clear()
        self._setup_axes_style()
        self.draw()

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
            self.axes.clear()
            self._curve_lines.clear()
            self._shade_collections.clear()
            self._setup_axes_style()

        plot_kwargs: dict[str, object] = {
            "linestyle": linestyle,
            "linewidth": 1.8,
        }
        if color:
            plot_kwargs["color"] = color
        if curve.label:
            plot_kwargs["label"] = curve.label

        lines = self.axes.plot(curve.x_values, curve.y_values, **plot_kwargs)
        self._curve_lines.extend(lines)

        if curve.label:
            self.axes.legend(loc="best")

        self.draw()
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
            self.axes.clear()
            self._curve_lines.clear()
            self._shade_collections.clear()
            self._setup_axes_style()

        plotted_count = 0
        has_legend = False

        for curve in curves:
            if not curve.is_valid:
                continue

            kwargs: dict[str, object] = {"linewidth": 1.8}
            if curve.label:
                kwargs["label"] = curve.label
                has_legend = True

            lines = self.axes.plot(curve.x_values, curve.y_values, **kwargs)
            self._curve_lines.extend(lines)
            plotted_count += 1

        if has_legend:
            self.axes.legend(loc="best")

        self.draw()
        return plotted_count

    def shade_region(
        self,
        x_values: Sequence[float],
        y_values: Sequence[float],
        y2_values: Sequence[float] | float = 0.0,
        color: str = "#3498db",
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
        }
        if label:
            kwargs["label"] = label

        poly = self.axes.fill_between(x_values, y_values, y2_values, **kwargs)
        self._shade_collections.append(poly)

        if label:
            self.axes.legend(loc="best")

        self.draw()
        return True

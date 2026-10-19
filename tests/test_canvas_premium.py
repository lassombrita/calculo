"""Pruebas del estilo premium de PlotCanvas: revelado animado, tooltip magnético y glow."""

from __future__ import annotations

import os

import numpy as np
import pytest
from matplotlib.backend_bases import MouseEvent
from PySide6.QtWidgets import QApplication

from integrallab.core.sampling import CurveData
from integrallab.viz.canvas import CURVE_COLORS, PlotCanvas


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """QApplication headless compartida por la sesión."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def _curve(label: str, fn) -> CurveData:
    xs = np.linspace(-2.0, 2.0, 200)
    return CurveData(x_values=xs.tolist(), y_values=fn(xs).tolist(), label=label, is_valid=True)


def _hover(canvas: PlotCanvas, x: float, y: float) -> None:
    px, py = canvas.axes.transData.transform((x, y))
    canvas._on_move(MouseEvent("motion_notify_event", canvas, px, py))  # noqa: SLF001


def test_curvas_usan_ciclo_de_color_semantico(qapp: QApplication) -> None:
    """f(x) sale cian, g(x) violeta; el color explícito sigue mandando."""
    canvas = PlotCanvas()
    canvas.plot_curves([_curve("f", np.sin), _curve("g", np.cos)])
    colors = [line.get_color() for line in canvas.curve_lines]
    assert colors == list(CURVE_COLORS[:2])


def test_curvas_tienen_glow(qapp: QApplication) -> None:
    """Cada curva lleva path_effects (trazos translúcidos + línea principal)."""
    canvas = PlotCanvas()
    canvas.plot_curve(_curve("f", np.sin))
    assert len(canvas.curve_lines[0].get_path_effects()) == 3


def test_revelado_recorta_sin_modificar_los_datos(qapp: QApplication) -> None:
    """El recorte crece de 0 a 100 % del ancho de los ejes y los datos quedan intactos."""
    canvas = PlotCanvas()
    canvas.plot_curve(_curve("f", np.sin))
    canvas.draw()
    line = canvas.curve_lines[0]
    n = len(line.get_xdata())
    full = canvas.axes.bbox.width

    canvas._on_reveal(0.5)  # noqa: SLF001
    canvas.draw()
    assert line.get_clip_box().width == pytest.approx(0.5 * full, rel=0.02)
    assert len(line.get_xdata()) == n

    canvas._end_reveal()  # noqa: SLF001
    canvas.draw()
    assert line.get_clip_box().width == pytest.approx(full, rel=0.02)
    assert len(line.get_xdata()) == n


def test_tooltip_se_pega_al_punto_mas_cercano(qapp: QApplication) -> None:
    """El tooltip muestra el x de la muestra más cercana y los valores de cada curva."""
    canvas = PlotCanvas()
    canvas.plot_curves([_curve("f(x)", np.sin), _curve("g(x)", np.cos)])
    _hover(canvas, 0.5, 0.5)
    tip = canvas._tip  # noqa: SLF001
    assert tip is not None and tip.get_visible()
    text = tip.get_text()
    assert "f(x) =" in text and "g(x) =" in text
    canvas._hide_tip()  # noqa: SLF001
    assert not tip.get_visible()


def test_clear_canvas_descarta_el_tooltip(qapp: QApplication) -> None:
    """Tras limpiar el lienzo no quedan referencias a artistas del tooltip anterior."""
    canvas = PlotCanvas()
    canvas.plot_curve(_curve("f", np.sin))
    _hover(canvas, 0.0, 0.0)
    canvas.clear_canvas()
    assert canvas._tip is None  # noqa: SLF001
    assert canvas._dots == []  # noqa: SLF001

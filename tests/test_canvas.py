"""Pruebas unitarias para el widget de visualización PlotCanvas."""

from __future__ import annotations

import os
import pytest
from PySide6.QtWidgets import QApplication

from integrallab.core.sampling import CurveData
from integrallab.viz.canvas import PlotCanvas


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Fixture de sesión para instanciar QApplication en modo headless/offscreen."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def test_canvas_instantiation(qapp: QApplication) -> None:
    """Verifica que PlotCanvas se puede instanciar correctamente con sus ejes configurados."""
    canvas = PlotCanvas()
    assert canvas.figure is not None
    assert canvas.axes is not None
    assert canvas.axes.get_xlabel() == "x"
    assert canvas.axes.get_ylabel() == "y"


def test_canvas_plot_curve_valid(qapp: QApplication) -> None:
    """Verifica el trazado de una curva válida sobre el lienzo."""
    canvas = PlotCanvas()
    curve = CurveData(
        x_values=[-1.0, 0.0, 1.0],
        y_values=[1.0, 0.0, 1.0],
        label="f(x) = x^2",
        is_valid=True,
    )

    success = canvas.plot_curve(curve)
    assert success is True
    assert len(canvas.curve_lines) == 1
    assert canvas.axes.get_legend() is not None


def test_canvas_set_y_window_fixes_the_visible_range(qapp: QApplication) -> None:
    """set_y_window fija la ventana vertical; con None se conserva el autoajuste."""
    canvas = PlotCanvas()
    curve = CurveData(
        x_values=[-1.0, 0.0, 1.0],
        y_values=[1.0, 1000.0, 1.0],
        label="f",
        is_valid=True,
    )
    canvas.plot_curve(curve)

    canvas.set_y_window((-5.0, 5.0))
    assert canvas.axes.get_ylim() == (-5.0, 5.0)

    canvas.plot_curve(curve)
    canvas.set_y_window(None)
    assert canvas.axes.get_ylim()[1] > 100.0


def test_canvas_plot_curve_invalid(qapp: QApplication) -> None:
    """Verifica que una curva inválida no sea graficada y retorne False."""
    canvas = PlotCanvas()
    curve = CurveData(
        x_values=[],
        y_values=[],
        label="invalida",
        is_valid=False,
        error_message="Error sintaxis",
    )

    success = canvas.plot_curve(curve)
    assert success is False
    assert len(canvas.curve_lines) == 0


def test_canvas_plot_multiple_curves_and_clear(qapp: QApplication) -> None:
    """Verifica el renderizado de múltiples curvas y la posterior limpieza del lienzo."""
    canvas = PlotCanvas()
    c1 = CurveData(x_values=[0.0, 1.0], y_values=[0.0, 1.0], label="c1", is_valid=True)
    c2 = CurveData(x_values=[0.0, 1.0], y_values=[1.0, 2.0], label="c2", is_valid=True)

    count = canvas.plot_curves([c1, c2])
    assert count == 2
    assert len(canvas.curve_lines) == 2

    canvas.clear_canvas()
    assert len(canvas.curve_lines) == 0


def test_canvas_shade_region_valid(qapp: QApplication) -> None:
    """Verifica que shade_region sombree un área y registre la colección de polígonos."""
    canvas = PlotCanvas()
    xs = [0.0, 1.0, 2.0]
    ys = [0.0, 1.0, 4.0]

    success = canvas.shade_region(xs, ys, label="Área bajo x^2")
    assert success is True
    assert len(canvas.shade_collections) == 1
    assert canvas.axes.get_legend() is not None

    canvas.clear_canvas()
    assert len(canvas.shade_collections) == 0


def test_canvas_shade_region_invalid_data(qapp: QApplication) -> None:
    """Verifica que shade_region rechace listas insuficientes de puntos."""
    canvas = PlotCanvas()
    success = canvas.shade_region([1.0], [1.0])
    assert success is False
    assert len(canvas.shade_collections) == 0


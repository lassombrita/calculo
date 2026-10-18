"""Pruebas unitarias para la ventana principal MainWindow."""

from __future__ import annotations

import os
import pytest

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from integrallab.ui.main_window import MainWindow
from integrallab.viz.canvas import PlotCanvas


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Fixture de sesión: QApplication en modo headless/offscreen."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


@pytest.fixture
def window(qapp: QApplication) -> MainWindow:
    """Fixture: instancia de MainWindow para cada test, sin diálogos modales."""
    w = MainWindow()
    w._show_dialogs = False  # Evita QMessageBox.exec() bloqueante en modo offscreen
    return w


def test_main_window_instantiation(window: MainWindow) -> None:
    """Verifica que MainWindow se instancie sin excepciones y con título correcto."""
    assert window is not None
    assert "IntegralLab" in window.windowTitle()


def test_main_window_has_expression_input(window: MainWindow) -> None:
    """Verifica que el campo de texto de la expresión matemática existe."""
    assert hasattr(window, "expression_input")
    assert isinstance(window.expression_input, QLineEdit)
    assert window.expression_input.placeholderText() != ""


def test_main_window_has_plot_button(window: MainWindow) -> None:
    """Verifica que el botón Graficar existe y tiene el texto correcto."""
    assert hasattr(window, "plot_button")
    assert isinstance(window.plot_button, QPushButton)
    assert window.plot_button.text() == "Graficar"


def test_main_window_has_canvas(window: MainWindow) -> None:
    """Verifica que el lienzo de visualización PlotCanvas está embebido."""
    assert hasattr(window, "canvas")
    assert isinstance(window.canvas, PlotCanvas)


def test_main_window_has_status_bar(window: MainWindow) -> None:
    """Verifica que la barra de estado existe y tiene un mensaje inicial."""
    assert window.statusBar() is not None
    assert window.statusBar().currentMessage() != ""


def test_plot_valid_expression_updates_canvas(window: MainWindow) -> None:
    """Verifica que graficar x**2 traza exactamente una curva en el canvas."""
    window.expression_input.setText("x**2")
    window._on_plot_clicked()
    assert len(window.canvas.curve_lines) == 1


def test_plot_empty_expression_no_crash(window: MainWindow) -> None:
    """Verifica que enviar una expresión vacía no lanza excepción."""
    window.expression_input.setText("")
    # No debe propagar ninguna excepción
    window._on_plot_clicked()
    assert "vacío" in window.statusBar().currentMessage()


def test_plot_invalid_expression_shows_error_in_statusbar(window: MainWindow) -> None:
    """Verifica que una expresión inválida actualiza la barra de estado con un error."""
    window.expression_input.setText("@@@")
    window._on_plot_clicked()
    msg = window.statusBar().currentMessage()
    assert "Error" in msg


def test_main_window_has_limits_and_result_label(window: MainWindow) -> None:
    """Verifica que los inputs de límites a y b y la etiqueta de resultado existan."""
    assert hasattr(window, "limit_a_input")
    assert isinstance(window.limit_a_input, QLineEdit)
    assert hasattr(window, "limit_b_input")
    assert isinstance(window.limit_b_input, QLineEdit)
    assert hasattr(window, "result_label")


def test_plot_with_definite_integral_and_shading(window: MainWindow) -> None:
    """Verifica cálculo de integral definida y sombreado de región para x^2 en [0, 3]."""
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("3")

    window._on_plot_clicked()

    assert len(window.canvas.curve_lines) == 1
    assert len(window.canvas.shade_collections) == 1
    assert "9" in window.result_label.text()


def test_plot_with_symbolic_limits(window: MainWindow) -> None:
    """Verifica límites simbólicos como pi para sin(x) en [0, pi]."""
    window.expression_input.setText("sin(x)")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("pi")

    window._on_plot_clicked()

    assert len(window.canvas.shade_collections) == 1
    assert "2" in window.result_label.text()


def test_plot_with_invalid_limits(window: MainWindow) -> None:
    """Verifica que límites inválidos no rompan la aplicación y muestren mensaje de error."""
    window.expression_input.setText("x")
    window.limit_a_input.setText("no_es_valido")
    window.limit_b_input.setText("2")

    window._on_plot_clicked()

    assert "Error" in window.result_label.text()


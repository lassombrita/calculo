"""Pruebas unitarias para la ventana principal MainWindow."""

from __future__ import annotations

import os
import pytest

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
)

from integrallab.ui.main_window import MainWindow
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D


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
    """Verifica que el botón principal existe y tiene el texto esperado."""
    assert hasattr(window, "plot_button")
    assert isinstance(window.plot_button, QPushButton)
    assert window.plot_button.text() == "Generar Gráficas y Sólido"


def test_main_window_has_canvases_and_tabs(window: MainWindow) -> None:
    """Verifica que el widget de pestañas y los lienzos 2D, 3D y visor de pasos están embebidos."""
    assert hasattr(window, "tab_widget")
    assert isinstance(window.tab_widget, QTabWidget)
    assert window.tab_widget.count() == 3
    assert window.tab_widget.tabText(0) == "Región 2D"
    assert window.tab_widget.tabText(1) == "Sólido 3D"
    assert window.tab_widget.tabText(2) == "Desarrollo"

    assert hasattr(window, "canvas")
    assert isinstance(window.canvas, PlotCanvas)
    assert hasattr(window, "canvas3d")
    assert isinstance(window.canvas3d, PlotCanvas3D)
    assert hasattr(window, "steps_text")
    assert isinstance(window.steps_text, QTextEdit)
    assert window.steps_text.isReadOnly()


def test_main_window_has_solid_configuration_controls(window: MainWindow) -> None:
    """Verifica la existencia de los controles para el sólido de revolución."""
    assert hasattr(window, "g_expression_input")
    assert isinstance(window.g_expression_input, QLineEdit)

    assert hasattr(window, "axis_combo")
    assert isinstance(window.axis_combo, QComboBox)
    assert window.axis_combo.count() >= 4

    assert hasattr(window, "axis_value_input")
    assert isinstance(window.axis_value_input, QLineEdit)

    assert hasattr(window, "method_combo")
    assert isinstance(window.method_combo, QComboBox)
    assert window.method_combo.count() >= 4

    assert hasattr(window, "results_text")
    assert isinstance(window.results_text, QTextEdit)
    assert window.results_text.isReadOnly()


def test_main_window_has_status_bar(window: MainWindow) -> None:
    """Verifica que la barra de estado existe y tiene un mensaje inicial."""
    assert window.statusBar() is not None
    assert window.statusBar().currentMessage() != ""


def test_plot_valid_expression_updates_canvas(window: MainWindow) -> None:
    """Verifica que graficar x**2 sin límites traza exactamente una curva en 2D."""
    window.expression_input.setText("x**2")
    window._on_plot_clicked()
    assert len(window.canvas.curve_lines) == 1


def test_plot_empty_expression_no_crash(window: MainWindow) -> None:
    """Verifica que enviar una expresión vacía no lanza excepción."""
    window.expression_input.setText("")
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


def test_plot_generates_solid_disks_outer_mesh(window: MainWindow) -> None:
    """Verifica generación de sólido de revolución por discos: x^2 en [0, 1] en eje X."""
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window._on_plot_clicked()

    assert len(window.canvas.curve_lines) == 1
    assert len(window.canvas.shade_collections) == 1
    assert len(window.canvas3d.surface_collections) >= 1
    report = window.results_text.toPlainText()
    assert "pi/5" in report
    assert "Discos" in report


def test_plot_generates_solid_washers_with_two_functions(window: MainWindow) -> None:
    """Verifica generación de sólido por arandelas: f(x)=sqrt(x), g(x)=x^2 en [0, 1]."""
    window.expression_input.setText("sqrt(x)")
    window.g_expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window._on_plot_clicked()

    # Dos curvas en 2D (f y g) y sombreado
    assert len(window.canvas.curve_lines) == 2
    assert len(window.canvas.shade_collections) == 1
    # Dos superficies en 3D (exterior e interior)
    assert len(window.canvas3d.surface_collections) == 2
    report = window.results_text.toPlainText()
    assert "3*pi/10" in report
    assert "Arandelas" in report


def test_plot_generates_solid_with_displaced_axis(window: MainWindow) -> None:
    """Verifica sólido con eje desplazado: f(x)=x en [0, 1] con eje y=2 -> 5*pi/3."""
    window.expression_input.setText("x")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(2)  # Horizontal (y = k)
    window.axis_value_input.setText("2")

    window._on_plot_clicked()

    report = window.results_text.toPlainText()
    assert "5*pi/3" in report
    assert len(window.canvas3d.axis_lines) >= 1


def test_plot_invalid_axis_value_handles_error(window: MainWindow) -> None:
    """Verifica que un valor no numérico en el eje desplazado se maneja amigablemente."""
    window.expression_input.setText("x")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(2)  # Horizontal (y = k)
    window.axis_value_input.setText("texto_invalido")

    window._on_plot_clicked()

    msg = window.statusBar().currentMessage()
    assert "Error" in msg


def test_plot_invalid_bounds_a_greater_equal_b(window: MainWindow) -> None:
    """Verifica que a >= b se capture como error sin lanzar excepción ni congelar."""
    window.expression_input.setText("x")
    window.limit_a_input.setText("3")
    window.limit_b_input.setText("1")

    window._on_plot_clicked()

    assert "Error" in window.result_label.text()
    msg = window.statusBar().currentMessage()
    assert "Error" in msg


def test_plot_populates_development_steps_tab(window: MainWindow) -> None:
    """Verifica que la pestaña 'Desarrollo' se llene con los pasos pedagógicos detallados."""
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window._on_plot_clicked()

    steps_text = window.steps_text.toPlainText()
    assert "Desarrollo Analítico Paso a Paso" in steps_text
    assert "Identificación geométrica" in steps_text
    assert "Planteamiento de la integral" in steps_text
    assert "Expansión" in steps_text
    assert "antiderivada" in steps_text or "Primitiva" in steps_text
    assert "Teorema Fundamental del Cálculo" in steps_text
    assert "pi/5" in steps_text


def test_plot_renders_latex_equations_in_reports(window: MainWindow) -> None:
    """Verifica que los reportes inyecten fórmulas matemáticas renderizadas como imágenes Base64."""
    window.expression_input.setText("sqrt(x)")
    window.g_expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window._on_plot_clicked()

    # Panel de resultados: debe contener la imagen en Base64 de la fórmula LaTeX
    res_html = window.results_text.toHtml()
    assert "data:image/png;base64," in res_html

    # Pestaña Desarrollo: debe contener imágenes Base64 para cada paso matemático
    steps_html = window.steps_text.toHtml()
    assert "data:image/png;base64," in steps_html
    # Múltiples fórmulas matemáticas renderizadas a lo largo del proceso
    assert steps_html.count("data:image/png;base64,") >= 4


# ── Tests Fase 9: Exportación a PDF ───────────────────────────────────────────


def test_export_pdf_button_exists_and_initially_disabled(window: MainWindow) -> None:
    """Verifica que el botón de exportación existe y está deshabilitado por defecto."""
    assert hasattr(window, "export_pdf_button")
    assert isinstance(window.export_pdf_button, QPushButton)
    assert not window.export_pdf_button.isEnabled()
    assert "PDF" in window.export_pdf_button.text()


def test_export_pdf_button_enabled_after_successful_plot(window: MainWindow) -> None:
    """Verifica que el botón de exportación se habilita tras generar un sólido."""
    assert not window.export_pdf_button.isEnabled()
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X
    window._on_plot_clicked()
    assert window.export_pdf_button.isEnabled()


def test_export_pdf_with_empty_path_returns_false(window: MainWindow) -> None:
    """Verifica que _export_to_pdf_path con ruta vacía retorna False sin excepción."""
    result = window._export_to_pdf_path("")
    assert result is False

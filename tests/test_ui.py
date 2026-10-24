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
    w._synchronous = True    # Mismo trabajo de cálculo, ejecutado en el hilo principal
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
    assert window.plot_button.text() == "⚙  Generar Gráficas y Sólido"


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
    assert "Identificación del radio" in steps_text
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


# ── Regresión: selector de método (Automático / Discos / Arandelas / Casquillos) ──


def test_method_combo_disables_methods_incompatible_with_axis(window: MainWindow) -> None:
    """Eje horizontal -> Casquillos deshabilitado; eje vertical -> Discos/Arandelas deshabilitados."""
    model = window.method_combo.model()

    window.axis_combo.setCurrentIndex(0)  # Eje X
    assert model.item(0).isEnabled()
    assert model.item(1).isEnabled()
    assert model.item(2).isEnabled()
    assert not model.item(3).isEnabled()

    window.axis_combo.setCurrentIndex(1)  # Eje Y
    assert model.item(0).isEnabled()
    assert not model.item(1).isEnabled()
    assert not model.item(2).isEnabled()
    assert model.item(3).isEnabled()


def test_axis_change_resets_incompatible_method_to_automatic(window: MainWindow) -> None:
    """Si el método elegido deja de aplicar al cambiar de eje, se vuelve a Automático."""
    window.axis_combo.setCurrentIndex(0)  # Eje X
    window.method_combo.setCurrentIndex(1)  # Discos
    assert window.method_combo.currentIndex() == 1

    window.axis_combo.setCurrentIndex(1)  # Eje Y: Discos ya no aplica
    assert window.method_combo.currentIndex() == 0


def test_programmatic_incompatible_selection_falls_back_to_automatic(window: MainWindow) -> None:
    """Seleccionar por código un método deshabilitado no deja la UI en un estado inválido."""
    window.axis_combo.setCurrentIndex(1)  # Eje Y
    window.method_combo.setCurrentIndex(1)  # Discos (deshabilitado)
    assert window.method_combo.currentIndex() == 0


def test_selecting_method_recalculates_without_pressing_button(window: MainWindow) -> None:
    """Cambiar el método recalcula solo: x^2 en [0, 1] sobre el eje Y con Casquillos -> pi/2."""
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(1)  # Eje Y

    window.method_combo.setCurrentIndex(3)  # Casquillos (sin pulsar el botón)

    report = window.results_text.toPlainText()
    assert "Casquillos" in report
    assert "pi/2" in report


def test_selecting_disks_explicitly_on_x_axis(window: MainWindow) -> None:
    """Discos explícito sobre el eje X: x^2 en [0, 1] -> pi/5."""
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window.method_combo.setCurrentIndex(1)  # Discos

    report = window.results_text.toPlainText()
    assert "Discos" in report
    assert "pi/5" in report


def test_selecting_washers_explicitly_with_two_functions(window: MainWindow) -> None:
    """Arandelas explícito: sqrt(x) y x^2 en [0, 1] sobre el eje X -> 3*pi/10."""
    window.expression_input.setText("sqrt(x)")
    window.g_expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window.method_combo.setCurrentIndex(2)  # Arandelas

    report = window.results_text.toPlainText()
    assert "Arandelas" in report
    assert "3*pi/10" in report


def test_disks_on_region_with_hole_warns_about_fallback(window: MainWindow) -> None:
    """Discos sobre una región con hueco usa Arandelas y lo avisa en la barra de estado."""
    window.expression_input.setText("sqrt(x)")
    window.g_expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)  # Eje X

    window.method_combo.setCurrentIndex(1)  # Discos

    msg = window.statusBar().currentMessage()
    assert "no aplica" in msg
    assert "Arandelas" in msg
    assert "3*pi/10" in window.results_text.toPlainText()


def test_method_change_without_data_does_not_fail(window: MainWindow) -> None:
    """Cambiar el método con la región vacía no debe lanzar errores ni calcular nada."""
    window.method_combo.setCurrentIndex(2)
    assert window.results_text.toPlainText() == ""


def test_plot_displays_curve_crossing_warning_in_results(window: MainWindow) -> None:
    """Las curvas que se cruzan en el intervalo muestran la advertencia en la tarjeta de resultados."""
    window.expression_input.setText("x**2")
    window.g_expression_input.setText("x")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("2")
    window.axis_combo.setCurrentIndex(0)  # Eje X
    window.plot_button.click()

    report_html = window.results_text.toHtml()
    assert "Nota:" in report_html
    assert "cruzan" in report_html



def test_plot_with_discrete_points_interpolation(window: MainWindow) -> None:
    """El usuario introduce puntos discretos y la UI interpola la curva y calcula el sólido."""
    window.expression_input.setText("(0, 0), (1, 1), (2, 4)")
    window.limit_a_input.clear()
    window.limit_b_input.clear()
    window.plot_button.click()

    # Los límites deben auto-completarse con el rango de los puntos [0, 2]
    assert window.limit_a_input.text() == "0.0"
    assert window.limit_b_input.text() == "2.0"
    assert len(window.canvas.curve_lines) >= 1
    assert "Interpolación" in window.statusBar().currentMessage()


def test_ui_washers_on_vertical_axis_with_inversion(window: MainWindow) -> None:
    """Con f(x)=x^2 en [0,1] sobre eje Y, Arandelas/Discos es aplicable mediante inversión a dy."""
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(1)  # Eje Y (vertical)

    # Verificar que el selector no inhabilite arandelas
    model = window.method_combo.model()
    # Índice 2: Arandelas
    item_washers = model.item(2)
    assert item_washers.isEnabled() is True

    # Seleccionar Arandelas
    window.method_combo.setCurrentIndex(2)

    # El resultado debe calcular el volumen correcto: pi / 2
    report = window.results_text.toPlainText()
    assert "pi/2" in report or "1.5708" in report

def test_ui_dual_engine_3d_selector(window: MainWindow) -> None:
    """Verifica que la UI ofrezca selector de motor 3D y conmute entre Three.js y Matplotlib."""
    assert hasattr(window, "engine_combo")
    assert window.engine_combo.count() == 2
    assert "Three.js" in window.engine_combo.itemText(0)
    assert "Matplotlib" in window.engine_combo.itemText(1)

    assert hasattr(window, "solid_stack")
    assert window.solid_stack.count() == 2
    assert hasattr(window, "threejs_viewer")

    # Conmutar a Matplotlib
    window.engine_combo.setCurrentIndex(1)
    assert window.solid_stack.currentIndex() == 1

    # Conmutar de vuelta a WebGL
    window.engine_combo.setCurrentIndex(0)
    assert window.solid_stack.currentIndex() == 0


def test_ui_3d_interactive_controls_presence_and_behavior(window: MainWindow) -> None:
    """Verifica que el panel interactivo 3D contenga los deslizadores y responda a las acciones."""
    assert hasattr(window, "revolution_slider")
    assert hasattr(window, "play_revolution_btn")
    assert hasattr(window, "reset_revolution_btn")
    assert hasattr(window, "slice_check")
    assert hasattr(window, "slice_slider")
    assert hasattr(window, "riemann_check")
    assert hasattr(window, "riemann_slider")

    # Inicialmente deshabilitados
    assert not window.revolution_slider.isEnabled()
    assert not window.play_revolution_btn.isEnabled()
    assert not window.slice_check.isEnabled()
    assert not window.riemann_check.isEnabled()

    # Generar un sólido
    window.expression_input.setText("x**2")
    window.limit_a_input.setText("0")
    window.limit_b_input.setText("1")
    window.axis_combo.setCurrentIndex(0)
    window._on_plot_clicked()

    # Tras graficar, se habilitan los controles interactivos
    assert window.revolution_slider.isEnabled()
    assert window.play_revolution_btn.isEnabled()
    assert window.slice_check.isEnabled()
    assert window.riemann_check.isEnabled()
    assert window.revolution_slider.value() == 360

    # Ajustar ángulo de rotación a 180°
    window.revolution_slider.setValue(180)
    assert window.revolution_angle_label.text() == "180°"

    # Resetear a 360°
    window.reset_revolution_btn.click()
    assert window.revolution_slider.value() == 360
    assert window.revolution_angle_label.text() == "360°"

    # Activar rebanada representativa
    window.slice_check.setChecked(True)
    assert window.slice_slider.isEnabled()
    window.slice_slider.setValue(750)
    assert "x =" in window.slice_pos_label.text()

    # Activar discos de Riemann (desactiva rebanada)
    window.riemann_check.setChecked(True)
    assert not window.slice_check.isChecked()
    assert window.riemann_slider.isEnabled()
    window.riemann_slider.setValue(15)
    assert window.riemann_count_label.text() == "N = 15"

    # Iniciar animación de giro
    window.play_revolution_btn.click()
    assert window._revolution_timer.isActive()
    assert "Pausar" in window.play_revolution_btn.text()

    # Pausar animación
    window.play_revolution_btn.click()
    assert not window._revolution_timer.isActive()
    assert "Continuar" in window.play_revolution_btn.text()

    # Mover deslizador de rebanada directamente la activa sin necesidad de clic manual previo
    window.reset_revolution_btn.click()
    assert not window.slice_check.isChecked()
    assert not window.riemann_check.isChecked()
    window.slice_slider.setValue(250)
    assert window.slice_check.isChecked()
    assert "x = 0.25" in window.slice_pos_label.text()

    # Mover deslizador de Riemann directamente conmuta a modo Riemann
    window.riemann_slider.setValue(25)
    assert window.riemann_check.isChecked()
    assert not window.slice_check.isChecked()
    assert window.riemann_count_label.text() == "N = 25"

    # Reset restaura a sólido continuo 360°
    window.reset_revolution_btn.click()
    assert not window.slice_check.isChecked()
    assert not window.riemann_check.isChecked()
    assert window.revolution_slider.value() == 360

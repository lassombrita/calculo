"""Pruebas del botón «Editor visual» y su sincronización con las casillas de texto."""

from __future__ import annotations

import os
import time

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import integrallab.ui.main_window as mw
from integrallab.ui.main_window import MainWindow
from integrallab.ui.widgets.visual_input import VisualMathEditor, visual_input_support

pytestmark = pytest.mark.skipif(
    not visual_input_support()[0], reason="El editor visual necesita QtWebEngine y MathLive."
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


@pytest.fixture
def window(qapp: QApplication):
    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    yield w
    w.visual_input_button.setChecked(False)  # la preferencia no pasa a la siguiente prueba
    w.close()


def _wait_until(qapp: QApplication, condition, timeout: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_toggle_switches_between_text_and_visual_inputs(window: MainWindow) -> None:
    window.expression_input.setText("x**2+1")
    window.limit_b_input.setText("pi/2")

    window.visual_input_button.setChecked(True)
    editor = window._visual_editor
    assert isinstance(editor, VisualMathEditor)
    assert window._text_inputs.isHidden() and not editor.isHidden()
    assert editor.latex("f") == "x^{2} + 1"
    assert editor.latex("b") == r"\frac{\pi}{2}"
    assert "texto" in window.visual_input_button.text()

    window.visual_input_button.setChecked(False)
    assert not window._text_inputs.isHidden() and editor.isHidden()
    assert window.expression_input.text() == "x**2+1"  # nada de lo escrito se pierde


def test_visual_fields_are_translated_into_the_text_model(window: MainWindow) -> None:
    window.visual_input_button.setChecked(True)
    editor = window._visual_editor
    assert editor is not None

    editor._on_field_changed("f", r"\frac{1}{x}")
    editor._on_field_changed("a", "1")
    editor._on_field_changed("b", r"\sqrt{4}")
    assert window.expression_input.text() == "((1)/(x))"
    assert window.limit_a_input.text() == "1"
    assert window.limit_b_input.text() == "sqrt(4)"


def test_incomplete_formula_blocks_the_calculation_and_keeps_last_valid_text(window: MainWindow) -> None:
    window.visual_input_button.setChecked(True)
    editor = window._visual_editor
    assert editor is not None
    editor._on_field_changed("f", "x^2")
    editor._on_field_changed("f", r"\frac{\placeholder{}}{x}")  # el estudiante pulsó «fracción»

    assert window.expression_input.text() == "x**2"
    window._on_plot_clicked()
    assert window._job is None
    assert "f(x)" in window.status_bar.currentMessage()
    assert "recuadros vacíos" in window.status_bar.currentMessage()


def test_values_filled_by_the_app_reach_the_editor(window: MainWindow) -> None:
    window.visual_input_button.setChecked(True)
    editor = window._visual_editor
    assert editor is not None
    window.limit_a_input.setText("-1")  # p. ej. los límites que rellena una interpolación
    assert editor.latex("a") == "-1"
    assert editor.text("a") == "-1"


def test_mode_is_remembered_between_sessions(qapp: QApplication) -> None:
    first = MainWindow()
    first.visual_input_button.setChecked(True)
    first.close()
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "IntegralLab", "IntegralLab")
    assert settings.value("input/visual_editor", False, type=bool) is True

    second = MainWindow()
    try:
        assert second.visual_input_button.isChecked()
        assert second._text_inputs.isHidden()
    finally:
        second.visual_input_button.setChecked(False)
        second.close()
    assert QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, "IntegralLab", "IntegralLab"
    ).value("input/visual_editor", True, type=bool) is False


def test_load_failure_falls_back_to_text(window: MainWindow) -> None:
    window.visual_input_button.setChecked(True)
    editor = window._visual_editor
    assert editor is not None
    editor.loadFailed.emit("sin motor web")
    assert not window.visual_input_button.isChecked()
    assert not window.visual_input_button.isEnabled()
    assert not window._text_inputs.isHidden()
    assert "sin motor web" in window.visual_input_button.toolTip()


def test_button_is_disabled_without_web_engine(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mw, "visual_input_support", lambda: (False, "QtWebEngine no está instalado."))
    w = MainWindow()
    try:
        assert not w.visual_input_button.isEnabled()
        assert "QtWebEngine" in w.visual_input_button.toolTip()
    finally:
        w.close()


def test_real_typing_in_mathlive_computes_the_solid(qapp: QApplication, window: MainWindow) -> None:
    """De punta a punta con MathLive real: teclado → fracción dibujada → texto → sólido."""
    window.resize(1320, 820)
    window.show()
    window.visual_input_button.setChecked(True)
    editor = window._visual_editor
    assert editor is not None
    if not _wait_until(qapp, lambda: editor.is_ready):
        pytest.skip("QtWebEngine no pudo cargar MathLive en este entorno.")

    window.limit_a_input.setText("1")
    window.limit_b_input.setText("2")
    editor.focus_field("f")
    _wait_until(qapp, lambda: False, timeout=0.3)
    target = editor.view.focusProxy() or editor.view
    for ch in "1/x":
        QTest.keyClicks(target, ch)
        _wait_until(qapp, lambda: False, timeout=0.03)
    assert _wait_until(qapp, lambda: window.expression_input.text() == "((1)/(x))", timeout=5.0)

    QTest.keyClick(target, Qt.Key.Key_Return)
    assert _wait_until(qapp, lambda: "Volumen" in window.result_label.text(), timeout=20.0)
    assert "pi/2" in window.result_label.text()  # V = π ∫₁² x⁻² dx = π/2

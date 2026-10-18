"""Pruebas del sistema de diseño: hoja de estilos, paleta Qt, GlassCard y aplicación al MainWindow."""

from __future__ import annotations

import os

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QTextEdit

from integrallab.ui.main_window import MainWindow
from integrallab.ui.theme import Palette, build_palette, build_stylesheet
from integrallab.ui.widgets.glass import GlassCard


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """QApplication headless compartida por la sesión."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def test_stylesheet_sin_tokens_sin_sustituir() -> None:
    """Todos los tokens ``$nombre`` deben estar resueltos en la hoja de estilos final."""
    qss = build_stylesheet()
    assert "$" not in qss
    assert Palette.CYAN in qss and "QGroupBox" in qss and "PrimaryButton" in qss


def test_paleta_oscura_usa_tokens() -> None:
    """La paleta Qt oscura (de la que Matplotlib toma el color de sus iconos) usa los tokens."""
    pal = build_palette()
    assert pal.color(QPalette.ColorRole.Window) == QColor(Palette.VOID)
    assert pal.color(QPalette.ColorRole.WindowText) == QColor(Palette.TEXT)


def test_glass_card_hover_anima_nivel(qapp: QApplication) -> None:
    """``set_emphasis`` dispara la animación de iluminación del borde."""
    card = GlassCard(elevated=False)
    card.set_emphasis(True)
    assert card._anim.endValue() == 1.0  # noqa: SLF001
    card.set_emphasis(False)
    assert card._anim.endValue() == 0.0  # noqa: SLF001


def test_main_window_aplica_tema_y_hojas_de_papel(qapp: QApplication) -> None:
    """La ventana se auto-tematiza y los reportes pedagógicos usan la hoja clara ``Paper``."""
    win = MainWindow()
    assert "QGroupBox" in win.styleSheet()
    assert win.plot_button.objectName() == "PrimaryButton"
    assert win.export_pdf_button.objectName() == "PrimaryButton"
    for editor in (win.results_text, win.steps_text):
        assert isinstance(editor, QTextEdit)
        assert editor.objectName() == "Paper"


def test_encabezado_del_reporte_no_usa_gradiente_css() -> None:
    """Qt ignora ``linear-gradient`` en texto enriquecido (dejaba el título blanco sobre blanco)."""
    import inspect

    from integrallab.ui import main_window

    assert "linear-gradient" not in inspect.getsource(main_window)

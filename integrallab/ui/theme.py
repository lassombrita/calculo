"""Sistema de diseño de IntegralLab: tokens de color, tipografía y hoja de estilos Qt (QSS).

Responsabilidad: ser la única fuente de verdad visual. Ningún otro módulo debe
escribir colores HEX a mano; todos importan ``Palette``.
"""
from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


class Palette:
    """Tokens de color (modo oscuro de alto contraste)."""

    VOID = "#05070D"      # fondo de ventana
    INK = "#0A0F1C"       # superficies profundas
    PANEL = "#101830"     # tooltips, leyendas
    EDGE = "#26325A"      # bordes sólidos
    TEXT = "#E8ECF8"
    MUTED = "#8B95B5"
    FAINT = "#566089"
    # Semántica matemática: cada objeto tiene SU color en toda la app.
    CYAN = "#5CE1FF"      # f(x)
    VIOLET = "#9D8CFF"    # integral / área
    AMBER = "#FFB454"     # derivada
    ROSE = "#FF6B8A"      # errores
    MINT = "#6BF0B2"      # éxito


UI_FONTS = '"Geist", "Segoe UI Variable", "Inter", "Segoe UI", sans-serif'
MONO_FONTS = '"JetBrains Mono", "Cascadia Mono", "Consolas", monospace'

_QSS = Template("""
* { font-family: $ui; color: $text; }
QWidget { background: transparent; }
QToolTip { background: rgba(16,24,48,0.96); color: $text; border: 1px solid $edge;
           border-radius: 8px; padding: 6px 10px; }

QLabel#Title { font-size: 15px; font-weight: 600; }
QLabel#Muted { color: $muted; font-size: 12px; }
QLabel#AiName { color: $cyan; font-size: 12px; font-weight: 600; }
QLabel#AiText { font-size: 14px; }
QLabel#ModelChip { background: rgba(157,140,255,0.12); border: 1px solid rgba(157,140,255,0.35);
                   border-radius: 10px; padding: 3px 10px; color: $violet; font-size: 11px; }
QLabel#UserBubble { background: rgba(157,140,255,0.10); border: 1px solid rgba(157,140,255,0.30);
                    border-radius: 14px; padding: 9px 14px; font-size: 13px; }
QLabel#ErrorText { color: $rose; font-size: 13px; }

QFrame#AiAccent { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $cyan, stop:1 rgba(157,140,255,0.15));
                  border-radius: 1px; }
QFrame#StepCard { background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.07);
                  border-radius: 12px; }
QLabel#StepTitle { color: $muted; font-size: 11px; font-weight: 600; }

QPlainTextEdit#PromptInput { background: transparent; border: none; font-size: 14px;
                             selection-background-color: rgba(92,225,255,0.28); }
QPushButton#SendButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $cyan, stop:1 $violet);
                         color: $void; border: none; border-radius: 12px; padding: 8px 20px; font-weight: 600; }
QPushButton#SendButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #8DEBFF, stop:1 #B7AAFF); }
QPushButton#SendButton[busy="true"] { background: rgba(255,107,138,0.16); color: $rose;
                                      border: 1px solid rgba(255,107,138,0.45); }

QScrollArea { border: none; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 4px 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.14); border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(92,225,255,0.45); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: transparent; }
QScrollBar:horizontal { height: 8px; background: transparent; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: rgba(120,130,160,0.35); border-radius: 3px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: rgba(92,225,255,0.45); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QMainWindow { background: $void; }
QDialog, QMessageBox { background: $ink; }

QGroupBox { background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px; margin-top: 16px; padding: 14px 12px 10px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px;
                   padding: 0 8px; color: $cyan; }

QLineEdit, QComboBox { background: rgba(5,7,13,0.55); border: 1px solid $edge; border-radius: 10px;
                       padding: 7px 10px; selection-background-color: rgba(92,225,255,0.28); }
QLineEdit:hover, QComboBox:hover { border: 1px solid #3A4673; }
QLineEdit:focus, QComboBox:focus { border: 1px solid $cyan; }
QLineEdit:disabled, QComboBox:disabled { color: $faint; border: 1px solid rgba(255,255,255,0.06); }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: $panel; border: 1px solid $edge; outline: 0;
                              selection-background-color: rgba(92,225,255,0.22); selection-color: $text; }
QComboBox QAbstractItemView::item:disabled { color: $faint; }

QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 18px; margin-right: 4px;
               border-radius: 10px; font-weight: 600; }
QTabBar::tab:selected { background: rgba(92,225,255,0.12); color: $cyan; }
QTabBar::tab:hover:!selected { color: $text; background: rgba(255,255,255,0.05); }

/* Los reportes pedagógicos (HTML + fórmulas LaTeX oscuras + PDF) viven en una "hoja de papel" clara. */
QTextEdit#Paper { background: #FFFFFF; color: #0F172A; border: 1px solid rgba(255,255,255,0.14);
                  border-radius: 12px; padding: 12px; font-size: 12px;
                  selection-background-color: rgba(2,132,199,0.28); }

QPushButton#PrimaryButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $cyan, stop:1 $violet);
                            color: $void; border: none; border-radius: 12px; padding: 10px 18px; font-weight: 700; }
QPushButton#PrimaryButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #8DEBFF, stop:1 #B7AAFF); }
QPushButton#PrimaryButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3FB8D9, stop:1 #7E6DE0); }
QPushButton#PrimaryButton:disabled { background: rgba(255,255,255,0.06); color: $faint; }
QLabel#Result { color: $text; font-size: 12px; font-weight: 600; }

/* Alternar entre texto y editor visual de fórmulas. */
QPushButton#ModeToggle { background: rgba(157,140,255,0.10); border: 1px solid rgba(157,140,255,0.35);
                         border-radius: 9px; padding: 4px 12px; color: $violet; font-size: 11px; font-weight: 600; }
QPushButton#ModeToggle:hover { background: rgba(157,140,255,0.18); }
QPushButton#ModeToggle:checked { background: rgba(92,225,255,0.12); border: 1px solid rgba(92,225,255,0.45); color: $cyan; }
QPushButton#ModeToggle:disabled { background: transparent; border: 1px solid rgba(255,255,255,0.06); color: $faint; }

QStatusBar { color: $muted; background: transparent; }
QStatusBar::item { border: none; }
QStatusBar QLabel { padding-left: 14px; }
QToolBar { background: transparent; border: none; spacing: 4px; }
QToolButton { background: transparent; border: none; border-radius: 8px; padding: 4px; }
QToolButton:hover { background: rgba(255,255,255,0.08); }
QToolButton:checked { background: rgba(92,225,255,0.18); }
""")


def build_stylesheet() -> str:
    """Devuelve la hoja de estilos global con los tokens ya sustituidos."""
    return _QSS.substitute(
        ui=UI_FONTS, void=Palette.VOID, text=Palette.TEXT, muted=Palette.MUTED,
        edge=Palette.EDGE, cyan=Palette.CYAN, violet=Palette.VIOLET, rose=Palette.ROSE,
        ink=Palette.INK, panel=Palette.PANEL, faint=Palette.FAINT,
    )


def build_palette() -> QPalette:
    """Paleta Qt oscura. Importa porque Matplotlib tiñe los iconos de su barra con ``WindowText``."""
    pal = QPalette()
    roles = (
        (QPalette.ColorRole.Window, Palette.VOID), (QPalette.ColorRole.WindowText, Palette.TEXT),
        (QPalette.ColorRole.Base, Palette.INK), (QPalette.ColorRole.AlternateBase, Palette.PANEL),
        (QPalette.ColorRole.Text, Palette.TEXT), (QPalette.ColorRole.Button, Palette.PANEL),
        (QPalette.ColorRole.ButtonText, Palette.TEXT), (QPalette.ColorRole.BrightText, Palette.ROSE),
        (QPalette.ColorRole.ToolTipBase, Palette.PANEL), (QPalette.ColorRole.ToolTipText, Palette.TEXT),
        (QPalette.ColorRole.Highlight, Palette.CYAN), (QPalette.ColorRole.HighlightedText, Palette.VOID),
        (QPalette.ColorRole.PlaceholderText, Palette.FAINT),
    )
    for role, color in roles:
        pal.setColor(role, QColor(color))
    return pal


def apply_theme(app: QApplication, fonts_dir: Path | None = None) -> None:
    """Carga fuentes empaquetadas (si existen) y aplica el estilo global."""
    if fonts_dir and fonts_dir.is_dir():
        for font_file in list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")):
            QFontDatabase.addApplicationFont(str(font_file))
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setStyleSheet(build_stylesheet())

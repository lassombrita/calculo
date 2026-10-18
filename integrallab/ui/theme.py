"""Sistema de diseño de IntegralLab: tokens de color, tipografía y hoja de estilos Qt (QSS).

Responsabilidad: ser la única fuente de verdad visual. Ningún otro módulo debe
escribir colores HEX a mano; todos importan ``Palette``.
"""
from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtGui import QFontDatabase
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
""")


def build_stylesheet() -> str:
    """Devuelve la hoja de estilos global con los tokens ya sustituidos."""
    return _QSS.substitute(
        ui=UI_FONTS, void=Palette.VOID, text=Palette.TEXT, muted=Palette.MUTED,
        edge=Palette.EDGE, cyan=Palette.CYAN, violet=Palette.VIOLET, rose=Palette.ROSE,
    )


def apply_theme(app: QApplication, fonts_dir: Path | None = None) -> None:
    """Carga fuentes empaquetadas (si existen) y aplica el estilo global."""
    if fonts_dir and fonts_dir.is_dir():
        for font_file in list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")):
            QFontDatabase.addApplicationFont(str(font_file))
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

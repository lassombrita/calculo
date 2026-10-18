"""Fondo "aurora": negro profundo con dos resplandores suaves. Da algo que atravesar al cristal."""
from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from integrallab.ui.theme import Palette


class AuroraBackground(QWidget):
    """Widget contenedor que pinta el fondo; úsalo como ``centralWidget`` de la ventana."""

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(Palette.VOID))
        for center, color, radius in (
            (QPointF(self.width() * 0.10, self.height() * 0.04), Palette.CYAN, self.width() * 0.55),
            (QPointF(self.width() * 0.96, self.height() * 0.98), Palette.VIOLET, self.width() * 0.60),
        ):
            grad = QRadialGradient(center, radius)
            c = QColor(color)
            c.setAlpha(46)
            grad.setColorAt(0.0, c)
            c.setAlpha(0)
            grad.setColorAt(1.0, c)
            p.fillRect(self.rect(), grad)
        p.end()

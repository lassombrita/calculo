"""Contenedor ``GlassCard``: cristal translúcido con borde iluminado y sombra dinámica.

Qt no ofrece ``backdrop-filter``; el efecto se logra con relleno translúcido en
degradado, borde con luz en la esquina superior izquierda y un brillo interior.
El borde y la sombra se intensifican con hover o foco (animación de 240 ms).
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QWidget

from integrallab.ui.theme import Palette


class GlassCard(QFrame):
    """Tarjeta de cristal. Usar ``elevated=False`` si contiene un canvas que se redibuja a 60 fps."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        radius: int = 20,
        glow: str = Palette.CYAN,
        elevated: bool = True,
    ) -> None:
        super().__init__(parent)
        self._radius = radius
        self._glow = QColor(glow)
        self._level = 0.0
        self._hovered = False
        self._focused = False
        self._shadow: QGraphicsDropShadowEffect | None = None
        if elevated:
            self._shadow = QGraphicsDropShadowEffect(self)
            self._shadow.setBlurRadius(36)
            self._shadow.setOffset(0, 10)
            self._shadow.setColor(QColor(0, 0, 0, 150))
            self.setGraphicsEffect(self._shadow)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_level)

    # -- API pública -------------------------------------------------
    def set_emphasis(self, active: bool) -> None:
        """Resalta la tarjeta (p. ej. cuando el campo de texto interno tiene foco)."""
        self._focused = active
        self._retarget()

    # -- animación ---------------------------------------------------
    def _retarget(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._level)
        self._anim.setEndValue(1.0 if (self._hovered or self._focused) else 0.0)
        self._anim.start()

    def _on_level(self, value: object) -> None:
        self._level = float(value)  # type: ignore[arg-type]
        if self._shadow is not None:
            self._shadow.setBlurRadius(36 + 22 * self._level)
            self._shadow.setOffset(0, 10 + 6 * self._level)
            tint = QColor(
                int(self._glow.red() * 0.35 * self._level),
                int(self._glow.green() * 0.35 * self._level),
                int(self._glow.blue() * 0.35 * self._level),
                int(150 - 30 * self._level),
            )
            self._shadow.setColor(tint)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._retarget()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._retarget()
        super().leaveEvent(event)

    # -- pintado -----------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fill.setColorAt(0.0, QColor(26, 36, 62, 205))
        fill.setColorAt(1.0, QColor(9, 13, 25, 232))
        p.fillPath(path, fill)

        border = QLinearGradient(rect.topLeft(), rect.bottomRight())
        lit = QColor(self._glow)
        lit.setAlphaF(0.28 + 0.50 * self._level)
        border.setColorAt(0.0, lit)
        border.setColorAt(0.45, QColor(255, 255, 255, 20))
        border.setColorAt(1.0, QColor(255, 255, 255, 10))
        p.setPen(QPen(QBrush(border), 1.0))
        p.drawPath(path)

        # Brillo interior superior: da sensación de grosor de cristal.
        p.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        r = self._radius
        p.drawLine(int(r), 2, int(self.width() - r), 2)
        p.end()

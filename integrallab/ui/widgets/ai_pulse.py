"""Indicador de actividad de la IA: barras tipo onda que respiran mientras se procesa."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from integrallab.ui.theme import Palette


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


class AiPulse(QWidget):
    """Siete barras cian→violeta. ``start()``/``stop()`` hacen fade de amplitud (sin cortes bruscos)."""

    BARS = 7
    BAR_W = 4
    GAP = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(self.BARS * self.BAR_W + (self.BARS - 1) * self.GAP, 26))
        self._phase = 0.0
        self._amp = 0.0
        self._phase_anim = QVariantAnimation(self)
        self._phase_anim.setStartValue(0.0)
        self._phase_anim.setEndValue(2 * math.pi)
        self._phase_anim.setDuration(1400)
        self._phase_anim.setLoopCount(-1)
        self._phase_anim.valueChanged.connect(self._on_phase)
        self._amp_anim = QVariantAnimation(self)
        self._amp_anim.setDuration(350)
        self._amp_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._amp_anim.valueChanged.connect(self._on_amp)
        self._amp_anim.finished.connect(self._halt_if_idle)

    def start(self) -> None:
        self._fade_to(1.0)
        if self._phase_anim.state() != QVariantAnimation.State.Running:
            self._phase_anim.start()

    def stop(self) -> None:
        self._fade_to(0.0)

    def _fade_to(self, target: float) -> None:
        self._amp_anim.stop()
        self._amp_anim.setStartValue(self._amp)
        self._amp_anim.setEndValue(target)
        self._amp_anim.start()

    def _halt_if_idle(self) -> None:
        if self._amp <= 0.001:
            self._phase_anim.stop()

    def _on_phase(self, value: object) -> None:
        self._phase = float(value)  # type: ignore[arg-type]
        self.update()

    def _on_amp(self, value: object) -> None:
        self._amp = float(value)  # type: ignore[arg-type]
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = float(self.height())
        base = 4.0
        c0, c1 = QColor(Palette.CYAN), QColor(Palette.VIOLET)
        for i in range(self.BARS):
            wave = math.sin(self._phase - i * 0.75) * 0.5 + 0.5
            bar_h = base + self._amp * wave * (h - base)
            color = _mix(c0, c1, i / (self.BARS - 1))
            color.setAlpha(int(90 + 165 * self._amp))
            x = i * (self.BAR_W + self.GAP)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, (h - bar_h) / 2, self.BAR_W, bar_h), 2, 2)
        p.end()

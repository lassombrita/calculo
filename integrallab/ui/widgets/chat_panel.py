"""Panel de IA inmersivo: jerarquía usuario/IA, estado de "pensando", streaming y pasos que se revelan.

Es agnóstico del proveedor: no importa Ollama ni Gemini. Se comunica solo por señales y métodos:
``prompt_submitted`` -> el controlador llama a la IA -> ``begin_stream``/``append_stream``/``add_steps``.
"""
from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from integrallab.ui.theme import Palette
from integrallab.ui.widgets.ai_pulse import AiPulse
from integrallab.ui.widgets.glass import GlassCard
# from integrallab.viz.latex import render_latex_png  # Para usar después si implementas latex.py nuevo

QWIDGETSIZE_MAX = 16777215
LATEX_DPR = 3.0
STATUS_PHRASES = ("Interpretando la expresión…", "Planteando el método…", "Verificando cada paso…")


@dataclass(frozen=True)
class StepData:
    """Un paso de la resolución: título, fórmula LaTeX opcional (sin $) y nota explicativa."""

    title: str
    latex: str | None = None
    note: str = ""


def latex_pixmap(expr: str) -> QPixmap:
    """Convierte LaTeX a QPixmap nítido (HiDPI) con tamaño natural."""
    pm = QPixmap()
    # from integrallab.viz.latex_render import render_latex_to_png_bytes
    # pm.loadFromData(render_latex_to_png_bytes(expr, fontsize=16, color=Palette.TEXT, dpi=int(96 * LATEX_DPR)))
    pm.loadFromData(b"")  # Placeholder - implementar latex.py después
    pm.setDevicePixelRatio(LATEX_DPR)
    return pm


class MathLabel(QLabel):
    """Fórmula LaTeX que se reduce para caber en el ancho disponible (sin forzar el ancho del panel)."""

    def __init__(self, expr: str) -> None:
        super().__init__()
        self._src = latex_pixmap(expr)
        self._natural = QSize(int(self._src.width() / LATEX_DPR), int(self._src.height() / LATEX_DPR))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self._natural.height())
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setPixmap(self._src)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self._natural

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self._natural.height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        avail = self.width()
        if 0 < avail < self._natural.width():
            pm = self._src.scaledToWidth(int(avail * LATEX_DPR), Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(LATEX_DPR)
            self.setPixmap(pm)
        elif self.pixmap().width() != self._src.width():
            self.setPixmap(self._src)


def reveal(widget: QWidget, delay_ms: int = 0, duration: int = 380) -> None:
    """Coreografía de entrada: el widget se despliega en altura mientras aparece (fade)."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    widget.setMaximumHeight(0)

    def start() -> None:
        lay = widget.layout()
        width = max(widget.width(), 320)
        target = lay.totalHeightForWidth(width) if lay is not None and lay.hasHeightForWidth() else 0
        target = max(target, widget.sizeHint().height(), 24)
        anim = QVariantAnimation(widget)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def tick(v: object) -> None:
            t = float(v)  # type: ignore[arg-type]
            widget.setMaximumHeight(int(target * t))
            effect.setOpacity(t)

        def done() -> None:
            widget.setMaximumHeight(QWIDGETSIZE_MAX)
            widget.setGraphicsEffect(None)

        anim.valueChanged.connect(tick)
        anim.finished.connect(done)
        anim.start()

    QTimer.singleShot(delay_ms, start)


def _rich(text: str) -> str:
    body = html.escape(text).replace("\n", "<br>")
    return f"<p style='margin:0; line-height:150%'>{body}</p>"


class PromptEdit(QPlainTextEdit):
    """Campo de prompt: Ctrl+Enter envía; avisa foco para iluminar la tarjeta contenedora."""

    submitted = Signal()
    focus_changed = Signal(bool)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.submitted.emit()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.focus_changed.emit(False)


class UserMessage(QWidget):
    """Mensaje del usuario: burbuja compacta alineada a la derecha (jerarquía baja)."""

    def __init__(self, text: str) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        bubble = QLabel(text)
        bubble.setObjectName("UserBubble")
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(380)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addStretch(1)
        row.addWidget(bubble, 0)


class StepCard(QFrame):
    """Un paso de la resolución con fórmula renderizada."""

    def __init__(self, index: int, step: StepData) -> None:
        super().__init__()
        self.setObjectName("StepCard")
        col = QVBoxLayout(self)
        col.setContentsMargins(14, 10, 14, 12)
        col.setSpacing(6)
        title = QLabel(f"Paso {index} · {step.title}")
        title.setObjectName("StepTitle")
        col.addWidget(title)
        if step.latex:
            col.addWidget(MathLabel(step.latex))
        if step.note:
            note = QLabel(step.note)
            note.setObjectName("Muted")
            note.setWordWrap(True)
            col.addWidget(note)


class AiMessage(QWidget):
    """Respuesta de la IA: sin burbuja, con barra de acento a la izquierda (jerarquía alta)."""

    def __init__(self) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        accent = QFrame()
        accent.setObjectName("AiAccent")
        accent.setFixedWidth(2)
        col = QVBoxLayout()
        col.setSpacing(10)
        name = QLabel("Asistente")
        name.setObjectName("AiName")
        self._text = QLabel()
        self._text.setObjectName("AiText")
        self._text.setWordWrap(True)
        self._text.setTextFormat(Qt.TextFormat.RichText)
        self._text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._steps = QVBoxLayout()
        self._steps.setSpacing(8)
        col.addWidget(name)
        col.addWidget(self._text)
        col.addLayout(self._steps)
        row.addWidget(accent)
        row.addLayout(col, 1)
        self._buffer = ""
        self._count = 0

    def append(self, chunk: str) -> None:
        self._buffer += chunk
        self._text.setText(_rich(self._buffer))

    def add_steps(self, steps: Sequence[StepData]) -> None:
        for i, step in enumerate(steps):
            self._count += 1
            card = StepCard(self._count, step)
            self._steps.addWidget(card)
            reveal(card, delay_ms=140 * i)

    def show_error(self, message: str) -> None:
        self._text.setObjectName("ErrorText")
        self._text.setStyleSheet("")  # fuerza re-evaluar el selector por objectName
        self._text.setText(_rich(message))


class ThinkingRow(QWidget):
    """Ondas + frases rotativas mientras el modelo procesa."""

    def __init__(self) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(14)
        self._pulse = AiPulse()
        self._label = QLabel(STATUS_PHRASES[0])
        self._label.setObjectName("Muted")
        row.addWidget(self._pulse)
        row.addWidget(self._label, 1)
        self._i = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1800)
        self._timer.timeout.connect(self._next)
        self._pulse.start()
        self._timer.start()

    def _next(self) -> None:
        self._i = (self._i + 1) % len(STATUS_PHRASES)
        self._label.setText(STATUS_PHRASES[self._i])


class ChatPanel(GlassCard):
    """Panel completo: cabecera, historial con auto-scroll y campo de prompt iluminado."""

    prompt_submitted = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, radius=22, glow=Palette.VIOLET)
        self._busy = False
        self._stick_to_bottom = True
        self._thinking: ThinkingRow | None = None
        self._current: AiMessage | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("Asistente")
        title.setObjectName("Title")
        self._chip = QLabel("Demo local")
        self._chip.setObjectName("ModelChip")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self._chip)
        root.addLayout(head)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setStyleSheet("background: transparent;")
        host = QWidget()
        self._msgs = QVBoxLayout(host)
        self._msgs.setContentsMargins(0, 0, 8, 0)
        self._msgs.setSpacing(18)
        self._empty = QLabel("Pregunta por una integral, una derivada o un límite.")
        self._empty.setObjectName("Muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msgs.addWidget(self._empty)
        self._msgs.addStretch(1)
        self._scroll.setWidget(host)
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _lo, hi: bar.setValue(hi) if self._stick_to_bottom else None)
        bar.valueChanged.connect(lambda v: setattr(self, "_stick_to_bottom", v >= bar.maximum() - 40))
        root.addWidget(self._scroll, 1)

        self._input_card = GlassCard(radius=16, glow=Palette.CYAN, elevated=False)
        box = QVBoxLayout(self._input_card)
        box.setContentsMargins(14, 10, 12, 10)
        box.setSpacing(6)
        self._input = PromptEdit()
        self._input.setObjectName("PromptInput")
        self._input.setPlaceholderText("Escribe una función o pregunta: ∫ x² sin(x) dx")
        self._input.setFixedHeight(64)
        self._input.focus_changed.connect(self._input_card.set_emphasis)
        self._input.submitted.connect(self._on_send)
        foot = QHBoxLayout()
        hint = QLabel("Ctrl + Enter para enviar")
        hint.setObjectName("Muted")
        self._send = QPushButton("Enviar")
        self._send.setObjectName("SendButton")
        self._send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send.clicked.connect(self._on_send)
        foot.addWidget(hint)
        foot.addStretch(1)
        foot.addWidget(self._send)
        box.addWidget(self._input)
        box.addLayout(foot)
        root.addWidget(self._input_card)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(440, 640)

    # -- API para el controlador -------------------------------------
    def set_backend_label(self, text: str) -> None:
        self._chip.setText(text)

    def begin_thinking(self) -> None:
        self._clear_empty()
        self._thinking = ThinkingRow()
        self._insert(self._thinking)

    def begin_stream(self) -> None:
        self._drop_thinking()
        self._current = AiMessage()
        self._insert(self._current)

    def append_stream(self, chunk: str) -> None:
        if self._current is None:
            self.begin_stream()
        assert self._current is not None
        self._current.append(chunk)

    def add_steps(self, steps: Sequence[StepData]) -> None:
        if self._current is None:
            self.begin_stream()
        assert self._current is not None
        self._current.add_steps(steps)

    def show_error(self, message: str) -> None:
        self._drop_thinking()
        msg = AiMessage()
        msg.show_error(message)
        self._insert(msg)
        self.finish()

    def finish(self) -> None:
        self._drop_thinking()
        self._current = None
        self._set_busy(False)

    # -- internos ----------------------------------------------------
    def _insert(self, widget: QWidget) -> None:
        self._msgs.insertWidget(self._msgs.count() - 1, widget)

    def _clear_empty(self) -> None:
        if self._empty is not None:
            self._empty.hide()
            self._empty.deleteLater()
            self._empty = None  # type: ignore[assignment]

    def _drop_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.hide()
            self._thinking.deleteLater()
            self._thinking = None

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._send.setText("Detener" if busy else "Enviar")
        self._send.setProperty("busy", busy)
        self._send.style().unpolish(self._send)
        self._send.style().polish(self._send)

    def _on_send(self) -> None:
        if self._busy:
            self.cancel_requested.emit()
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._clear_empty()
        self._insert(UserMessage(text))
        self._input.clear()
        self._set_busy(True)
        self.prompt_submitted.emit(text)

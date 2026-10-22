"""Panel de IA inmersivo: jerarquía usuario/IA, estado de "pensando", streaming y pasos que se revelan.

Es agnóstico del proveedor: no importa Ollama ni Gemini. Se comunica solo por señales y métodos:
``prompt_submitted`` -> el controlador llama a la IA -> ``begin_stream``/``append_stream``/``add_steps``.
"""
from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import SIGNAL, QEasingCurve, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from integrallab.ui.theme import Palette
from integrallab.ui.widgets.ai_pulse import AiPulse
from integrallab.ui.widgets.glass import GlassCard
from integrallab.viz.latex_render import render_latex_to_png_bytes

QWIDGETSIZE_MAX = 16777215
LATEX_DPR = 3.0
STATUS_PHRASES = ("Interpretando la expresión…", "Planteando el método…", "Verificando cada paso…")
# Si el controlador no responde en este tiempo, el panel sale del estado "Detener" por sí solo.
BUSY_TIMEOUT_MS = 90_000
CANCEL_TIMEOUT_MS = 5_000


@dataclass(frozen=True)
class StepData:
    """Un paso de la resolución: título, fórmula LaTeX opcional (sin $) y nota explicativa."""

    title: str
    latex: str | None = None
    note: str = ""


def latex_pixmap(expr: str) -> QPixmap:
    """Convierte LaTeX a QPixmap nítido (HiDPI) con tamaño natural.

    Antes era un marcador vacío (``loadFromData(b"")``): toda fórmula de un paso salía como
    una etiqueta de 0 px de alto. Si MathText no puede con la expresión, devuelve un pixmap
    nulo y ``MathLabel`` muestra el texto tal cual.
    """
    pm = QPixmap()
    try:
        pm.loadFromData(
            render_latex_to_png_bytes(expr, fontsize=16, color=Palette.TEXT, dpi=int(96 * LATEX_DPR))
        )
    except (ValueError, RuntimeError):
        return QPixmap()
    pm.setDevicePixelRatio(LATEX_DPR)
    return pm


class MathLabel(QLabel):
    """Fórmula LaTeX que se reduce para caber en el ancho disponible (sin forzar el ancho del panel)."""

    def __init__(self, expr: str) -> None:
        super().__init__()
        self._src = latex_pixmap(expr)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if self._src.isNull():
            # Respaldo legible: la expresión en texto (antes no se veía nada).
            self.setText(expr)
            self.setWordWrap(True)
            self._natural = QSize(self.fontMetrics().horizontalAdvance(expr), self.fontMetrics().height() + 4)
            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            return
        self._natural = QSize(int(self._src.width() / LATEX_DPR), int(self._src.height() / LATEX_DPR))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self._natural.height())
        self.setPixmap(self._src)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self._natural

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self._natural.height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._src.isNull():
            return
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
        try:
            widget.isVisible()
        except RuntimeError:
            return  # el widget se destruyó antes de que arrancara la animación
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
            try:
                widget.setMaximumHeight(int(target * t))
                effect.setOpacity(t)
            except RuntimeError:
                anim.stop()

        def done() -> None:
            try:
                widget.setMaximumHeight(QWIDGETSIZE_MAX)
                widget.setGraphicsEffect(None)
            except RuntimeError:
                pass

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
    escape_pressed = Signal()
    focus_changed = Signal(bool)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.submitted.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
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
        # setStyleSheet("") no re-evalúa el selector por objectName; unpolish/polish sí.
        self._text.style().unpolish(self._text)
        self._text.style().polish(self._text)
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
        self._cancelling = False
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_watchdog)
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
        self._input.escape_pressed.connect(self._on_escape)
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
        self._kick_watchdog()

    def append_stream(self, chunk: str) -> None:
        if self._current is None:
            self.begin_stream()
        assert self._current is not None
        self._current.append(chunk)
        self._kick_watchdog()

    def add_steps(self, steps: Sequence[StepData]) -> None:
        if self._current is None:
            self.begin_stream()
        assert self._current is not None
        self._current.add_steps(steps)
        self._kick_watchdog()

    @property
    def is_busy(self) -> bool:
        return self._busy

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
        self._cancelling = False
        self._send.setEnabled(True)
        self._send.setText("Detener" if busy else "Enviar")
        self._send.setProperty("busy", busy)
        self._send.style().unpolish(self._send)
        self._send.style().polish(self._send)
        if busy:
            self._watchdog.start(BUSY_TIMEOUT_MS)
        else:
            self._watchdog.stop()

    def _kick_watchdog(self) -> None:
        if self._busy and not self._cancelling:
            self._watchdog.start(BUSY_TIMEOUT_MS)

    def _on_watchdog(self) -> None:
        """El controlador no respondió: se libera el botón en lugar de dejarlo en "Detener"."""
        if not self._busy:
            return
        if self._cancelling:
            self.show_error("Se canceló la consulta.")
        else:
            self.cancel_requested.emit()
            self.show_error("El asistente no respondió a tiempo. Puedes intentarlo de nuevo.")

    def _on_escape(self) -> None:
        if self._busy:
            self._request_cancel()

    def _request_cancel(self) -> None:
        if self._cancelling:
            return
        self._cancelling = True
        self._send.setText("Cancelando…")
        self._send.setEnabled(False)
        self.cancel_requested.emit()
        # Si el controlador no llama a finish() en unos segundos, el panel se recupera solo.
        self._watchdog.start(CANCEL_TIMEOUT_MS)

    def _on_send(self) -> None:
        if self._busy:
            self._request_cancel()
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._clear_empty()
        self._insert(UserMessage(text))
        self._input.clear()
        if self.receivers(SIGNAL("prompt_submitted(QString)")) == 0:
            # Sin controlador conectado el botón quedaba en "Detener" para siempre.
            self.show_error("El asistente no está conectado en esta versión de IntegralLab.")
            return
        self._set_busy(True)
        self.prompt_submitted.emit(text)

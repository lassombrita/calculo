"""Editor visual de fórmulas (estilo GeoGebra o calculadora con «Natural Display»).

Responsabilidad:
Ofrecer, como alternativa al texto plano, casillas donde la fracción dibuja su raya, la raíz
su signo y la potencia su exponente. Es una página local (``resources/visual_input``) con
MathLive dentro de un ``QWebEngineView``; se comunica con Python por ``QWebChannel``.

Cada cambio de una casilla llega como LaTeX y se traduce con
``integrallab.core.latex_input.latex_to_expression`` a la sintaxis de texto del parser. Así la
ventana principal sigue trabajando con los mismos ``QLineEdit`` de siempre (que hacen de
modelo) y toda entrada, escrita o dibujada, pasa por el mismo parser seguro.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget

from integrallab.core.latex_input import LatexInputError, expression_to_latex, latex_to_expression
from integrallab.core.parser import ExpressionParseError

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - instalaciones sin QtWebEngine
    WEBENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)

RESOURCES_DIR = Path(__file__).resolve().parents[2] / "resources"
PAGE_PATH = RESOURCES_DIR / "visual_input" / "index.html"
MATHLIVE_PATH = RESOURCES_DIR / "mathlive" / "mathlive.min.js"

FIELD_NAMES: tuple[str, ...] = ("f", "g", "a", "b")
FIELD_LABELS: dict[str, str] = {"f": "f(x)", "g": "g(x)", "a": "Límite a", "b": "Límite b"}

# Primer arranque de QtWebEngine en un equipo lento: margen antes de declarar el fallo.
READY_TIMEOUT_MS = 20_000


def visual_input_support() -> tuple[bool, str]:
    """(disponible, motivo): el editor necesita QtWebEngine y los archivos de MathLive."""
    if not WEBENGINE_AVAILABLE:
        return False, "QtWebEngine no está instalado (PySide6-WebEngine)."
    if not PAGE_PATH.exists() or not MATHLIVE_PATH.exists():
        return False, "Faltan los archivos del editor visual en integrallab/resources."
    return True, ""


class _Bridge(QObject):
    """Objeto publicado en la página como ``bridge`` (nombres en camelCase para JavaScript)."""

    # Python → JavaScript
    setLatexRequested = Signal(str, str)   # (casilla, LaTeX)
    statusChanged = Signal(str, str)       # (casilla, mensaje de error o "")
    focusRequested = Signal(str)           # casilla

    def __init__(self, owner: "VisualMathEditor") -> None:
        super().__init__(owner)
        self._owner = owner

    # JavaScript → Python
    @Slot(str)
    def ready(self, _names: str) -> None:  # noqa: N802 - API de JavaScript
        self._owner._on_page_ready()

    @Slot(str, str)
    def fieldChanged(self, name: str, latex: str) -> None:  # noqa: N802
        self._owner._on_field_changed(name, latex)

    @Slot(str)
    def fieldCommitted(self, name: str) -> None:  # noqa: N802
        self._owner._show_error(name)

    @Slot()
    def submit(self) -> None:
        self._owner.submitted.emit()

    @Slot(int)
    def contentHeight(self, height: int) -> None:  # noqa: N802
        self._owner._on_content_height(height)


if WEBENGINE_AVAILABLE:

    class _ConsolePage(QWebEnginePage):  # type: ignore[misc]
        """Reenvía la consola de la página al logging de Python."""

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            lv = QWebEnginePage.JavaScriptConsoleMessageLevel
            py_level = {
                lv.InfoMessageLevel: logging.DEBUG,
                lv.WarningMessageLevel: logging.WARNING,
                lv.ErrorMessageLevel: logging.ERROR,
            }.get(level, logging.INFO)
            logger.log(py_level, "JS %s:%s %s", Path(str(source)).name, line, message)


class VisualMathEditor(QWidget):
    """Casillas visuales para f(x), g(x), a y b, con barra de plantillas.

    Señales:
        textChanged(casilla, texto): texto para el parser cada vez que la casilla queda completa
            (``""`` si se vació). Mientras está incompleta no se emite y ``error`` da el motivo.
        submitted(): el usuario pulsó Enter en una casilla.
        loadFailed(motivo): la página no cargó; la ventana debe volver al modo texto.
    """

    textChanged = Signal(str, str)
    submitted = Signal()
    loadFailed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ok, reason = visual_input_support()
        if not ok:
            raise RuntimeError(reason)

        self._ready = False
        self._failed = False
        self._latex: dict[str, str] = {name: "" for name in FIELD_NAMES}
        self._texts: dict[str, str] = {name: "" for name in FIELD_NAMES}
        self._errors: dict[str, str | None] = {name: None for name in FIELD_NAMES}
        self._shown: dict[str, str] = {name: "" for name in FIELD_NAMES}
        self._pending_focus: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._view = QWebEngineView(self)
        page = _ConsolePage(self._view)
        self._view.setPage(page)
        page.setBackgroundColor(Qt.GlobalColor.transparent)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._view.setMinimumHeight(230)
        layout.addWidget(self._view)

        self._bridge = _Bridge(self)
        self._channel = QWebChannel(page)
        self._channel.registerObject("bridge", self._bridge)
        page.setWebChannel(self._channel)

        self._view.loadFinished.connect(self._on_load_finished)
        self._view.load(QUrl.fromLocalFile(str(PAGE_PATH)))
        QTimer.singleShot(READY_TIMEOUT_MS, self._check_ready)

    # ── API pública ─────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True cuando MathLive y el puente están listos en la página."""
        return self._ready

    @property
    def view(self) -> QWidget:
        """Vista web interna (para pruebas y foco)."""
        return self._view

    def text(self, name: str) -> str:
        """Último texto válido de la casilla ``name`` para el parser (``""`` si está vacía)."""
        return self._texts[name]

    def latex(self, name: str) -> str:
        """Último LaTeX conocido de la casilla ``name``."""
        return self._latex[name]

    def error(self, name: str) -> str | None:
        """Motivo por el que la casilla no se pudo traducir, o ``None``."""
        return self._errors[name]

    def first_error(self) -> tuple[str, str] | None:
        """(casilla, mensaje) del primer error, en el orden f, g, a, b."""
        for name in FIELD_NAMES:
            message = self._errors[name]
            if message:
                return name, message
        return None

    def show_errors(self) -> None:
        """Muestra bajo cada casilla su error (se ocultan mientras se escribe)."""
        for name in FIELD_NAMES:
            self._show_error(name)

    def set_text(self, name: str, text: str) -> None:
        """Carga en la casilla una expresión escrita en texto (p. ej., al activar el editor)."""
        text = text.strip()
        self._texts[name] = text
        self._errors[name] = None
        status = ""
        try:
            latex = expression_to_latex(text)
        except ExpressionParseError:
            # El texto no era válido: se muestra tal cual para que se corrija en el editor.
            latex = text
            status = "Este texto no es una expresión válida; corrígelo aquí."
        self._latex[name] = latex
        if self._ready:
            self._bridge.setLatexRequested.emit(name, latex)
        self._set_status(name, status)

    def focus_field(self, name: str = "f") -> None:
        """Pone el cursor en la casilla ``name``."""
        if self._ready:
            self._view.setFocus()
            self._bridge.focusRequested.emit(name)
        else:
            self._pending_focus = name

    # ── Eventos de la página ────────────────────────────────────────────────

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            self._fail("No se pudo cargar el editor visual (visual_input/index.html).")

    def _check_ready(self) -> None:
        if not self._ready:
            self._fail("El editor visual no respondió; se sigue en modo texto.")

    def _fail(self, reason: str) -> None:
        if not self._failed:
            self._failed = True
            logger.warning("Editor visual no disponible: %s", reason)
            self.loadFailed.emit(reason)

    def _on_page_ready(self) -> None:
        self._ready = True
        for name in FIELD_NAMES:
            self._bridge.setLatexRequested.emit(name, self._latex[name])
            self._bridge.statusChanged.emit(name, self._shown[name])
        if self._pending_focus is not None:
            name, self._pending_focus = self._pending_focus, None
            self.focus_field(name)

    def _on_field_changed(self, name: str, latex: str) -> None:
        if name not in self._latex:
            return
        self._latex[name] = latex
        try:
            text, error = latex_to_expression(latex), None
        except LatexInputError as exc:
            text, error = "", str(exc)
        self._errors[name] = error
        if error is not None:
            return  # incompleta: se conserva el último texto válido; el aviso sale al salir de la casilla
        if self._shown[name]:
            self._set_status(name, "")  # se corrigió: se retira el aviso al instante
        if text != self._texts[name]:
            self._texts[name] = text
            self.textChanged.emit(name, text)

    def _on_content_height(self, height: int) -> None:
        self._view.setFixedHeight(max(120, min(int(height), 640)))

    def _show_error(self, name: str) -> None:
        if name in self._errors:
            self._set_status(name, self._errors[name] or "")

    def _set_status(self, name: str, message: str) -> None:
        self._shown[name] = message
        if self._ready:
            self._bridge.statusChanged.emit(name, message)

"""Vista interactiva del desarrollo paso a paso («estilo Photomath»).

Responsabilidad:
Mostrar el árbol ``VolumeResult.step_tree`` (``integrallab.core.steps.StepNode``) en una página
local con MathJax 3 sin conexión (``resources/steps``). Las partes de cada fórmula marcadas con
``\\class{step-ID}{…}`` se vuelven botones: al tocarlas se despliega, justo debajo, el paso que
explica cómo se obtuvieron (y ese paso puede tener a su vez partes clicables).

Flujo de eventos:

- Python → JavaScript: ``set_tree`` serializa el árbol a JSON y llama ``IntegralSteps.render``.
  Si la página aún carga, el árbol queda pendiente y se envía cuando MathJax avisa ``ready``.
- JavaScript → Python (``QWebChannel``, objeto ``bridge``): ``ready()``, ``rendered(n)`` y
  ``stepToggled(id, abierto)``; este último se reexpone como la señal ``stepToggled``.

La vista no importa SymPy: recibe nodos ya construidos por el dominio. Todo texto se inserta en
la página con ``textContent`` y la navegación fuera de ``resources/`` está bloqueada.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:  # la vista no importa el dominio en tiempo de ejecución (ni SymPy)
    from integrallab.core.steps.model import StepNode

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - instalaciones sin QtWebEngine
    WEBENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)

RESOURCES_DIR = Path(__file__).resolve().parents[2] / "resources"
PAGE_PATH = RESOURCES_DIR / "steps" / "index.html"
MATHJAX_PATH = RESOURCES_DIR / "mathjax" / "tex-svg-full.js"

READY_TIMEOUT_MS = 20_000


def steps_view_support() -> tuple[bool, str]:
    """(disponible, motivo): la vista necesita QtWebEngine, la página y MathJax."""
    if not WEBENGINE_AVAILABLE:
        return False, "QtWebEngine no está instalado (PySide6-WebEngine)."
    if not PAGE_PATH.exists() or not MATHJAX_PATH.exists():
        return False, "Faltan los archivos del desglose interactivo en integrallab/resources."
    return True, ""


class _StepsBridge(QObject):
    """Objeto publicado en la página como ``bridge`` (nombres en camelCase para JavaScript)."""

    def __init__(self, owner: StepsView) -> None:
        super().__init__(owner)
        self._owner = owner

    @Slot()
    def ready(self) -> None:
        self._owner._on_ready()

    @Slot(int)
    def rendered(self, count: int) -> None:
        self._owner.rendered.emit(int(count))

    @Slot(str, bool)
    def stepToggled(self, node_id: str, is_open: bool) -> None:  # noqa: N802 - API de JavaScript
        self._owner.stepToggled.emit(node_id, bool(is_open))


if WEBENGINE_AVAILABLE:

    class _LocalPage(QWebEnginePage):  # type: ignore[misc]
        """Página que solo navega dentro de ``resources/`` y reenvía la consola al logging."""

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
            local = url.isLocalFile() and Path(url.toLocalFile()).resolve().is_relative_to(RESOURCES_DIR)
            return bool(local or url.scheme() in ("qrc", "data", "about"))

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            lv = QWebEnginePage.JavaScriptConsoleMessageLevel
            py_level = {
                lv.InfoMessageLevel: logging.DEBUG,
                lv.WarningMessageLevel: logging.WARNING,
                lv.ErrorMessageLevel: logging.ERROR,
            }.get(level, logging.INFO)
            logger.log(py_level, "JS %s:%s %s", Path(str(source)).name, line, message)


class StepsView(QWidget):
    """Desglose interactivo del cálculo.

    Señales:
        ready(): la página y MathJax están listos.
        rendered(n): se mostró un árbol de ``n`` nodos (0 si se limpió la vista).
        stepToggled(id, abierto): el estudiante desplegó o plegó un paso.
        loadFailed(motivo): la página no cargó; la ventana debe usar la vista imprimible.
    """

    ready = Signal()
    rendered = Signal(int)
    stepToggled = Signal(str, bool)
    loadFailed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_ready = False
        self._pending: dict[str, Any] | None = None
        self._failed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        available, reason = steps_view_support()
        if not available:
            self.view = None
            self._failed = True
            QTimer.singleShot(0, lambda: self.loadFailed.emit(reason))
            return

        self.view = QWebEngineView(self)
        self._page = _LocalPage(self.view)
        self.view.setPage(self._page)
        self._bridge = _StepsBridge(self)
        self._channel = QWebChannel(self._page)
        self._channel.registerObject("bridge", self._bridge)
        self._page.setWebChannel(self._channel)
        self.view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.view)

        self._ready_timer = QTimer(self)
        self._ready_timer.setSingleShot(True)
        self._ready_timer.timeout.connect(self._on_ready_timeout)
        self._ready_timer.start(READY_TIMEOUT_MS)
        self.view.load(QUrl.fromLocalFile(str(PAGE_PATH)))

    # ── API pública ─────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def failed(self) -> bool:
        return self._failed

    def set_tree(self, tree: StepNode | None, *, title: str = "", meta: str = "", message: str = "") -> None:
        """Muestra un árbol (o un mensaje si ``tree`` es ``None``)."""
        payload: dict[str, Any] = {
            "tree": tree.to_dict() if tree is not None else None,
            "title": title,
            "meta": meta,
            "message": message,
        }
        if not self._is_ready:
            self._pending = payload
            return
        self._send(payload)

    def clear(self, message: str = "") -> None:
        self.set_tree(None, message=message)

    def reveal(self, node_id: str) -> None:
        """Despliega un paso (y sus antepasados) y lo lleva a la vista."""
        self._run(f"IntegralSteps.reveal({json.dumps(node_id)})")

    def expand_all(self, expanded: bool = True) -> None:
        self._run("IntegralSteps.expandAll()" if expanded else "IntegralSteps.collapseAll()")

    def run_javascript(self, code: str, callback: Any = None) -> None:
        """Acceso de bajo nivel para pruebas (consultar el estado de la página)."""
        if self.view is None:
            return
        if callback is None:
            self._page.runJavaScript(code)
        else:
            self._page.runJavaScript(code, 0, callback)

    # ── Interno ─────────────────────────────────────────────────────────────

    def _run(self, code: str) -> None:
        if self.view is not None and self._is_ready:
            self._page.runJavaScript(code)

    def _send(self, payload: dict[str, Any]) -> None:
        # JSON es un subconjunto de JavaScript: el árbol viaja como literal, sin eval de texto.
        self._page.runJavaScript(f"IntegralSteps.render({json.dumps(payload, ensure_ascii=False)})")

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            self._fail("No se pudo cargar la página del desglose interactivo.")

    def _on_ready(self) -> None:
        if self._is_ready:
            return
        self._is_ready = True
        self._ready_timer.stop()
        self.ready.emit()
        if self._pending is not None:
            payload, self._pending = self._pending, None
            self._send(payload)

    def _on_ready_timeout(self) -> None:
        if not self._is_ready:
            self._fail("MathJax no terminó de cargar a tiempo.")

    def _fail(self, reason: str) -> None:
        if self._failed:
            return
        self._failed = True
        logger.warning("Desglose interactivo no disponible: %s", reason)
        self.loadFailed.emit(reason)

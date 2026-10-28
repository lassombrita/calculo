"""Desglose interactivo en la pestaña «Desarrollo» (QtWebEngine + MathJax sin conexión).

Simula lo que hace el estudiante: tocar una parte resaltada de una fórmula y ver que el paso que
la explica se despliega debajo; volver a tocarla lo pliega. Se usa ``runJavaScript`` para hacer
clic y consultar el estado de la página.
"""

from __future__ import annotations

import os
import time

import pytest
from PySide6.QtWidgets import QApplication

from integrallab.core.parser import parse_math_expression
from integrallab.core.solids import Region2D, RevolutionAxis, SolidMethod, calculate_revolution_volume
from integrallab.ui.main_window import MainWindow
from integrallab.ui.views.steps_view import StepsView, steps_view_support

pytestmark = pytest.mark.skipif(not steps_view_support()[0], reason="Se necesita QtWebEngine y MathJax.")


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def _wait_until(qapp: QApplication, condition, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


def _js(qapp: QApplication, view: StepsView, code: str):
    box: dict[str, object] = {}
    view.run_javascript(code, lambda result: box.setdefault("r", result))
    assert _wait_until(qapp, lambda: "r" in box, 10.0), code
    return box["r"]


@pytest.fixture
def tree():
    res = calculate_revolution_volume(
        Region2D(parse_math_expression("x**2 + 1"), None, "0", "1"), RevolutionAxis.x_axis(), SolidMethod.DISKS
    )
    assert res.step_tree is not None
    return res.step_tree


def test_click_on_formula_part_expands_its_step(qapp: QApplication, tree) -> None:
    view = StepsView()
    view.resize(800, 900)
    view.show()
    toggles: list[tuple[str, bool]] = []
    view.stepToggled.connect(lambda node_id, is_open: toggles.append((node_id, is_open)))
    assert _wait_until(qapp, lambda: view.is_ready), "MathJax no cargó sin conexión"

    rendered: list[int] = []
    view.rendered.connect(rendered.append)
    view.set_tree(tree, title="Método de Discos", meta="Eje y = 0")
    assert _wait_until(qapp, lambda: rendered and _js(qapp, view, "IntegralSteps.anchorCount()") > 0)
    assert rendered[-1] == tree.count()

    # La primera parte clicable es el radio R(x) del planteamiento.
    setup = next(n for n in tree.children if n.rule == "Setup")
    target = _js(qapp, view, "document.querySelector('.step-anchor').getAttribute('data-target')")
    assert target == setup.children[0].id
    assert _js(qapp, view, f"IntegralSteps.isOpen('{target}')") is False

    click = "document.querySelector('.step-anchor').dispatchEvent(new MouseEvent('click', {bubbles: true}))"
    _js(qapp, view, click)
    assert _wait_until(qapp, lambda: _js(qapp, view, f"IntegralSteps.isOpen('{target}')") is True)
    assert (target, True) in toggles  # el clic llega a Python por QWebChannel

    _js(qapp, view, click)  # volver a tocar lo pliega
    assert _wait_until(qapp, lambda: _js(qapp, view, f"IntegralSteps.isOpen('{target}')") is False)

    # Desplegar un paso profundo abre también todos sus antepasados.
    depth: dict[str, int] = {tree.id: 0}
    for node in tree.walk():
        for child in node.children:
            depth[child.id] = depth[node.id] + 1
    deep = tree.find(max(depth, key=depth.get))
    assert depth[deep.id] >= 3
    view.reveal(deep.id)
    assert _wait_until(qapp, lambda: _js(qapp, view, f"IntegralSteps.isOpen('{deep.id}')") is True)
    assert _js(qapp, view, "document.querySelectorAll('mjx-merror').length") == 0
    view.close()


def test_text_is_inserted_as_text_not_html(qapp: QApplication) -> None:
    from integrallab.core.steps import StepNode

    evil = StepNode("s1", "Volume", "<img src=x onerror=alert(1)>", "<b>no es HTML</b>", "x", ())
    view = StepsView()
    assert _wait_until(qapp, lambda: view.is_ready)
    view.set_tree(evil)
    assert _wait_until(qapp, lambda: _js(qapp, view, "document.querySelectorAll('section.step').length") == 1)
    assert _js(qapp, view, "document.querySelectorAll('img, b').length") == 0
    view.close()


def test_main_window_shows_interactive_view_in_development_tab(qapp: QApplication) -> None:
    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    try:
        assert w.steps_mode_button.isChecked()  # interactivo por defecto
        w.expression_input.setText("x**2")
        w.limit_a_input.setText("0")
        w.limit_b_input.setText("1")
        w._on_plot_clicked()
        assert w.steps_view is None  # se crea al abrir la pestaña, no antes
        w.tab_widget.setCurrentWidget(w._dev_widget)
        assert w.steps_view is not None and w.steps_stack.currentWidget() is w.steps_view
        assert _wait_until(qapp, lambda: w.steps_view.is_ready)
        assert _wait_until(qapp, lambda: _js(qapp, w.steps_view, "IntegralSteps.anchorCount()") > 0)
        # La vista imprimible (base del PDF) sigue llena y se puede elegir.
        assert "Planteamiento de la integral" in w.steps_text.toPlainText()
        w.steps_mode_button.setChecked(False)
        assert w.steps_stack.currentWidget() is w.steps_text
    finally:
        w.steps_mode_button.setChecked(True)
        w.close()

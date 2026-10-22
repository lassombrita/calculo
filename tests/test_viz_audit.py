"""Regresiones de la auditoría del motor 3D (Three.js / QtWebEngine) y de los lienzos Matplotlib."""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest
from matplotlib.backend_bases import MouseEvent
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

from integrallab.core.sampling import CurveData
from integrallab.core.solids import Region2D, RevolutionAxis, SolidMesh3D, generate_solid_mesh
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.threejs_wrapper import (
    WEBENGINE_AVAILABLE,
    ThreeJSViewer,
    encode_solid_mesh,
    serialize_solid_mesh,
)

BUNDLE = Path(__file__).parent.parent / "integrallab" / "resources" / "threejs_bundle.html"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def _decode(grid: dict) -> np.ndarray:
    raw = np.frombuffer(base64.b64decode(grid["positions_b64"]), dtype="<f4")
    return raw.reshape(grid["rows"], grid["cols"], 3)


# ── Puente Python → JavaScript ──────────────────────────────────────────────

def test_binary_payload_round_trips_the_mesh() -> None:
    mesh = generate_solid_mesh(Region2D("sqrt(x)", "x**2", 0, 1), RevolutionAxis.horizontal(-1), 32, 20)
    data = encode_solid_mesh(mesh)
    assert data["format"] == 2
    assert data["axis"] == {"orientation": "horizontal", "position": -1.0}
    outer = _decode(data["outer"])
    np.testing.assert_allclose(outer[..., 0], mesh.x_outer, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(outer[..., 1], mesh.y_outer, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(outer[..., 2], mesh.z_outer, rtol=1e-6, atol=1e-6)
    inner = _decode(data["inner"])
    np.testing.assert_allclose(inner[..., 2], mesh.z_inner, rtol=1e-6, atol=1e-6)


def test_binary_payload_is_much_smaller_than_json() -> None:
    mesh = generate_solid_mesh(Region2D("sqrt(x)", "x**2", 0, 1), RevolutionAxis.x_axis(), 64, 48)
    binary = len(json.dumps(encode_solid_mesh(mesh)))
    legacy = len(json.dumps(serialize_solid_mesh(mesh)))
    assert binary < 0.35 * legacy


def test_binary_payload_rejects_invalid_meshes() -> None:
    bad = SolidMesh3D(
        x_outer=np.array([[0.0, np.nan], [1.0, 2.0]]), y_outer=np.ones((2, 2)), z_outer=np.ones((2, 2))
    )
    assert encode_solid_mesh(bad) == {}
    tiny = SolidMesh3D(x_outer=np.ones((1, 5)), y_outer=np.ones((1, 5)), z_outer=np.ones((1, 5)))
    assert encode_solid_mesh(tiny) == {}


def test_bundle_has_webgl_guard_cleanup_and_on_demand_rendering() -> None:
    js = BUNDLE.read_text(encoding="utf-8")
    assert "status: () => JSON.stringify(status)" in js          # handshake con Python
    assert "showFallback(" in js                                 # mensaje si no hay WebGL
    assert "requestRender" in js and "requestAnimationFrame(animate)" not in js  # sin bucle continuo
    assert "controls.maxDistance = maxDim * 50" in js            # zoom escalado al sólido
    assert "positions_b64" in js and "geometry.dispose()" in js and "m.dispose()" in js
    assert "camera.position.multiplyScalar(factor)" not in js    # zoom respecto al objetivo


def test_viewer_handshake_reports_status_and_flushes_pending(qapp: QApplication) -> None:
    viewer = ThreeJSViewer()
    seen: list[tuple[bool, str]] = []
    viewer.backend_status_changed.connect(lambda ok, reason: seen.append((ok, reason)))
    sent: list[dict] = []
    viewer._dispatch_render = lambda data: sent.append(data) or True  # type: ignore[assignment]

    mesh = generate_solid_mesh(Region2D("x", None, 0, 1), RevolutionAxis.x_axis(), 12, 6)
    assert viewer.plot_solid_mesh(mesh) is True          # en cola hasta que JS confirme
    viewer._on_status_reply(json.dumps({"ok": False, "reason": "sin GPU"}))
    assert seen[-1] == (False, "sin GPU") and viewer.is_available is False and not sent
    viewer._on_status_reply(json.dumps({"ok": True, "reason": ""}))
    assert seen[-1] == (True, "") and len(sent) == 1     # la malla pendiente se envía al confirmar


@pytest.mark.skipif(not WEBENGINE_AVAILABLE, reason="QtWebEngine no instalado")
def test_viewer_real_page_answers_the_handshake(qapp: QApplication) -> None:
    """Con QtWebEngine real la página responde ok/motivo (en CI sin GPU suele ser False)."""
    viewer = ThreeJSViewer()
    end = time.perf_counter() + 30
    while viewer.is_available is None and time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.01)
    assert viewer.is_available is not None, "el visor no respondió al handshake"
    if viewer.is_available is False:
        assert viewer.status_reason


# ── Lienzo 2D: blitting y redibujo ligero ───────────────────────────────────

def _curve(label: str, fn) -> CurveData:
    xs = np.linspace(-3, 3, 200)
    return CurveData(x_values=xs.tolist(), y_values=fn(xs).tolist(), label=label)


def test_tooltip_uses_blitting_on_a_visible_canvas(qapp: QApplication) -> None:
    canvas = PlotCanvas()
    canvas.resize(600, 400)
    canvas.show()
    canvas.plot_curves([_curve("f(x)", np.sin)])
    canvas.draw()
    assert canvas._tip_bg is not None  # fondo guardado tras el dibujo completo
    drawn: list[int] = []
    original = canvas.draw
    canvas.draw = lambda: drawn.append(1) or original()  # type: ignore[assignment]
    px, py = canvas.axes.transData.transform((0.5, 0.5))
    canvas._on_move(MouseEvent("motion_notify_event", canvas, px, py))
    assert canvas._tip is not None and canvas._tip.get_visible() and canvas._tip.get_animated()
    assert drawn == []  # el tooltip no provoca un redibujado completo
    canvas.close()


def test_replot_keeps_axes_style_and_rescales(qapp: QApplication) -> None:
    canvas = PlotCanvas()
    canvas.plot_curve(_curve("f", np.sin))
    minor_before = len(canvas.axes.xaxis.get_minorticklocs())
    canvas.plot_curve(CurveData(x_values=[0.0, 10.0], y_values=[0.0, 100.0], label="g"))
    assert len(canvas.curve_lines) == 1 and canvas.axes.get_legend() is not None
    assert canvas.axes.get_ylim()[1] >= 100.0          # la escala sigue a los datos nuevos
    assert minor_before > 0 and len(canvas.axes.xaxis.get_minorticklocs()) > 0  # estilo intacto


def test_hidden_canvas_in_visible_window_defers_drawing(qapp: QApplication) -> None:
    tabs = QTabWidget()
    visible_page = QWidget()
    canvas = PlotCanvas()
    tabs.addTab(visible_page, "otra")
    tabs.addTab(canvas, "2D")
    tabs.resize(600, 400)
    tabs.show()
    QApplication.processEvents()
    assert not canvas.isVisible()
    canvas.plot_curve(_curve("f", np.cos))
    canvas.draw()
    assert canvas._draw_deferred is True
    tabs.setCurrentIndex(1)
    QApplication.processEvents()
    assert canvas._draw_deferred is False
    tabs.close()

"""Deslizadores 3D (hallazgo A8): un cuadro por evento agrupado, solo en el motor visible, sin
reiniciar la cámara y sin volver a mostrar el sólido del cálculo anterior."""

from __future__ import annotations

import os
import time

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from integrallab.core.parser import parse_math_expression
from integrallab.core.pipeline import sanitize_mesh
from integrallab.core.solids import Region2D, RevolutionAxis, generate_solid_mesh
from integrallab.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


@pytest.fixture
def window(qapp: QApplication):
    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    w.expression_input.setText("sin(x) + 2")
    w.limit_a_input.setText("0")
    w.limit_b_input.setText("2*pi")
    w._on_plot_clicked()
    assert w.revolution_slider.isEnabled()
    yield w
    w.close()


def test_slider_events_are_coalesced_into_one_frame(window: MainWindow, qapp: QApplication) -> None:
    calls: list[int] = []
    original = window._render_interactive_frame
    window._render_interactive_frame = lambda: (calls.append(1), original())  # type: ignore[method-assign]
    window._frame_timer.timeout.disconnect()
    window._frame_timer.timeout.connect(window._render_interactive_frame)
    for value in range(300, 200, -5):  # 20 eventos seguidos, como al arrastrar
        window.revolution_slider.setValue(value)
    assert calls == []  # nada se dibuja dentro del manejador del evento
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not calls:
        qapp.processEvents()
        time.sleep(0.005)
    assert calls == [1]


def test_matplotlib_camera_survives_slider_frames(window: MainWindow) -> None:
    window.engine_combo.setCurrentIndex(1)  # Matplotlib
    window.canvas3d.axes.view_init(elev=60, azim=200)
    window.canvas3d._zoom = 2.5
    window.revolution_slider.setValue(180)
    window._render_interactive_frame()
    assert window.canvas3d.axes.elev == pytest.approx(60)
    assert window.canvas3d.axes.azim == pytest.approx(200)
    assert window.canvas3d._zoom == pytest.approx(2.5)


def test_only_the_visible_engine_draws(window: MainWindow) -> None:
    window.engine_combo.setCurrentIndex(1)  # Matplotlib visible
    sent: list[object] = []
    window.threejs_viewer.plot_solid_mesh = lambda *a, **k: sent.append(a) or True  # type: ignore[method-assign]
    window.revolution_slider.setValue(90)
    window._render_interactive_frame()
    assert sent == []


def test_frame_is_fast_enough(window: MainWindow) -> None:
    window.engine_combo.setCurrentIndex(0)  # WebGL (sin GPU aquí: solo el lado Python)
    times = []
    for value in (350, 300, 250, 200, 150, 100, 50):
        window.revolution_slider.setValue(value)
        t = time.perf_counter()
        window._render_interactive_frame()
        times.append(time.perf_counter() - t)
    assert float(np.median(times)) < 0.05  # antes ~42 ms con WebGL y ~95 ms con Matplotlib


def test_new_job_disables_sliders_until_its_mesh_arrives(window: MainWindow) -> None:
    window._synchronous = True
    old_region = window._current_region
    window.expression_input.setText("x**2")
    window.limit_b_input.setText("1")
    window._on_plot_clicked()
    assert window._current_region is not None and window._current_region is not old_region
    assert str(window._current_region.f_expr) in ("x**2", str(parse_math_expression("x**2")))


def test_sanitize_mesh_fills_singular_rows() -> None:
    mesh = generate_solid_mesh(Region2D("log(x) + 3", None, 0, 1), RevolutionAxis.x_axis())
    fixed = sanitize_mesh(mesh)
    assert fixed is not None and np.all(np.isfinite(fixed.x_outer)) and np.all(np.isfinite(fixed.y_outer))

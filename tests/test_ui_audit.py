"""Regresiones de la auditoría interactiva de la interfaz (PySide6).

Los defectos se reprodujeron ejecutando la aplicación real (Qt sobre X11 virtual):
- Primer clic con límites → ``AttributeError: _worker``: el sólido no se calculaba nunca.
- Cerrar la ventana con un cálculo en curso abortaba el proceso (SIGABRT).
- Cambiar el método en el combo calculaba en el hilo de la interfaz (2,7 s congelada).
- Tras un fallo quedaban el sólido, el desarrollo y «Exportar a PDF» del caso anterior.
- Sin WebGL, el visor 3D quedaba negro sin explicación.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import integrallab.ui.main_window as mw
from integrallab.core.solids import SolidMethod, SolutionStep, VolumeResult, RevolutionAxis
from integrallab.ui.main_window import MainWindow
from integrallab.ui.widgets.chat_panel import ChatPanel, MathLabel


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


@pytest.fixture
def sync_window(qapp: QApplication) -> MainWindow:
    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    return w


@pytest.fixture
def thread_window(qapp: QApplication) -> MainWindow:
    """Ventana asíncrona real con el respaldo de hilo (sin proceso aparte)."""
    w = MainWindow()
    w._show_dialogs = False
    w._backend_failed = True
    return w


def _fill(w: MainWindow, f: str, a: str, b: str, g: str = "") -> None:
    w.expression_input.setText(f)
    w.g_expression_input.setText(g)
    w.limit_a_input.setText(a)
    w.limit_b_input.setText(b)


def _wait_idle(w: MainWindow, timeout: float = 60.0) -> None:
    end = time.perf_counter() + timeout
    while w._job is not None and time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.005)
    QApplication.processEvents()
    assert w._job is None, "el cálculo no terminó a tiempo"


# ── Ciclo de vida de los trabajos ───────────────────────────────────────────

def test_worker_state_exists_and_escape_without_job_is_safe(qapp: QApplication) -> None:
    w = MainWindow()
    assert w._worker is None and w._job is None
    QTest.keyClick(w, Qt.Key.Key_Escape)  # antes: AttributeError en keyPressEvent


def test_async_click_computes_solid_and_restores_button(thread_window: MainWindow) -> None:
    w = thread_window
    _fill(w, "x**2", "0", "1")
    w.plot_button.click()
    assert not w.plot_button.isEnabled()  # ocupado mientras calcula
    _wait_idle(w)
    assert w.plot_button.isEnabled()
    assert w.plot_button.text() == mw._PLOT_BUTTON_TEXT
    assert "pi/5" in w.result_label.text()
    assert w.export_pdf_button.isEnabled()


def test_process_backend_computes_and_shuts_down(qapp: QApplication) -> None:
    w = MainWindow()
    w._show_dialogs = False
    _fill(w, "sqrt(x)", "0", "1", g="x**2")
    w.plot_button.click()
    assert w._job is not None and w._job.in_process
    _wait_idle(w, timeout=90)
    assert "3*pi/10" in w.results_text.toPlainText()
    backend = w._backend
    assert backend is not None
    w.close()
    assert backend._proc is None


def test_method_change_is_not_computed_on_the_ui_thread(thread_window: MainWindow, monkeypatch) -> None:
    """Antes _refresh_if_ready desactivaba los diálogos y eso activaba la rama síncrona."""
    started: list[int] = []
    monkeypatch.setattr(mw.CalculationWorker, "start", lambda self: started.append(self.job_id))
    w = thread_window
    _fill(w, "x**2", "0", "1")
    w.method_combo.setCurrentIndex(1)  # Discos
    assert started, "el cambio de método debe lanzar un trabajo en segundo plano"
    assert w.result_label.text() == "Área / Integral: —"  # aún sin resultado: no se calculó en línea


def test_results_of_replaced_jobs_are_discarded(thread_window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(mw.CalculationWorker, "start", lambda self: None)
    w = thread_window
    _fill(w, "x**2", "0", "1")
    w.plot_button.click()
    old_id = w._job.job_id
    assert not w.plot_button.isEnabled()  # el botón queda bloqueado; Enter sigue disponible
    _fill(w, "x", "0", "1")
    QTest.keyClick(w.expression_input, Qt.Key.Key_Return)
    new_id = w._job.job_id
    assert new_id != old_id

    stale = mw.run_calculation(mw.CalculationRequest(
        f=mw.parse_math_expression("x**2"), g=None, a_text="0", b_text="1",
        axis=RevolutionAxis.x_axis(), method=None,
    ))
    w._on_job_finished(old_id, stale)
    assert "pi/5" not in w.result_label.text()  # el resultado viejo no se pinta
    fresh = mw.run_calculation(mw.CalculationRequest(
        f=mw.parse_math_expression("x"), g=None, a_text="0", b_text="1",
        axis=RevolutionAxis.x_axis(), method=None,
    ))
    w._on_job_finished(new_id, fresh)
    assert "pi/3" in w.result_label.text()


def test_repeated_enter_does_not_duplicate_the_running_job(thread_window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(mw.CalculationWorker, "start", lambda self: None)
    monkeypatch.setattr(mw.CalculationWorker, "isRunning", lambda self: True)
    w = thread_window
    _fill(w, "x**2", "0", "1")
    QTest.keyClick(w.expression_input, Qt.Key.Key_Return)
    first = w._job_seq
    for _ in range(4):
        QTest.keyClick(w.expression_input, Qt.Key.Key_Return)
    assert w._job_seq == first
    assert "Ya se está calculando" in w.status_bar.currentMessage()


def test_escape_cancels_and_clears_partial_outputs(thread_window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(mw.CalculationWorker, "start", lambda self: None)
    w = thread_window
    _fill(w, "x**2", "0", "1")
    w.plot_button.click()
    assert w._job is not None
    QTest.keyClick(w, Qt.Key.Key_Escape)
    assert w._job is None and w.plot_button.isEnabled()
    assert "cancelado" in w.status_bar.currentMessage()
    assert not w.export_pdf_button.isEnabled()


def test_failure_after_success_does_not_leave_stale_outputs(sync_window: MainWindow) -> None:
    w = sync_window
    _fill(w, "x**2", "0", "1")
    w.plot_button.click()
    assert w.export_pdf_button.isEnabled() and w.canvas3d.surface_collections

    _fill(w, "1/(x-1)", "0", "2")  # integral divergente
    w.plot_button.click()
    assert "Error" in w.result_label.text()
    assert not w.export_pdf_button.isEnabled()
    assert w.canvas3d.surface_collections == []
    assert "Método de Discos" not in w.steps_text.toPlainText()


# ── Entradas que antes se desviaban o fallaban ──────────────────────────────

@pytest.mark.parametrize(
    ("f", "expected"),
    [("max(1,2)*x", "Volumen 3D"), ("log(x,2)", "Volumen 3D"), ("0,5*(x+1)", "Volumen 3D")],
)
def test_multi_argument_functions_reach_the_solid(sync_window: MainWindow, f: str, expected: str) -> None:
    w = sync_window
    _fill(w, f, "1", "2")
    w.plot_button.click()
    assert expected in w.result_label.text(), w.status_bar.currentMessage()


def test_five_points_build_a_spline_solid(sync_window: MainWindow) -> None:
    w = sync_window
    _fill(w, "(0,0),(1,1),(2,4),(3,9),(4,16)", "", "")
    w.plot_button.click()
    msg = w.status_bar.currentMessage()
    assert "Interpolación (Spline)" in msg and "Sólido generado" in msg
    assert w.canvas3d.surface_collections
    assert "spline cúbico natural (5 puntos)" in w.canvas.curve_lines[0].get_label()


# ── Motor 3D y vista ────────────────────────────────────────────────────────

def test_webgl_unavailable_falls_back_to_matplotlib(sync_window: MainWindow) -> None:
    w = sync_window
    assert w.engine_combo.currentIndex() == 0
    w._on_webgl_status(False, "GPU en lista negra")
    assert w.engine_combo.currentIndex() == 1
    assert w.solid_stack.currentIndex() == 1
    item = w.engine_combo.model().item(0)
    assert not item.isEnabled() and "GPU en lista negra" in item.toolTip()
    w._on_webgl_status(True, "")
    assert item.isEnabled()


def test_view_controls_exist_and_drive_both_engines(sync_window: MainWindow) -> None:
    w = sync_window
    _fill(w, "x**2", "0", "1")
    w.plot_button.click()
    assert w.canvas3d._rotation_timer.isActive()
    w.auto_rotate_check.setChecked(False)
    assert not w.canvas3d._rotation_timer.isActive()
    w.canvas3d._zoom = 3.0
    w.fit_view_button.click()
    assert w.canvas3d._zoom == 1.0


def test_hidden_matplotlib_canvas_does_not_animate(qapp: QApplication) -> None:
    """Con el motor WebGL activo, el lienzo Matplotlib oculto no debe gastar CPU girando."""
    w = MainWindow()
    w._show_dialogs = False
    w._synchronous = True
    w.show()
    w.tab_widget.setCurrentIndex(1)
    QApplication.processEvents()
    assert w.engine_combo.currentIndex() == 0 and not w.canvas3d.isVisible()
    _fill(w, "x**2", "0", "1")
    w.plot_button.click()
    assert w.canvas3d.surface_collections
    assert not w.canvas3d._rotation_timer.isActive()
    w.close()


# ── Reportes ────────────────────────────────────────────────────────────────

def test_reports_escape_dynamic_text(sync_window: MainWindow) -> None:
    w = sync_window
    vol = VolumeResult(
        method=SolidMethod.DISKS, exact_plain_text="a<b", numeric_value=1.0,
        steps=[SolutionStep(1, "Paso <b>1</b>", "si x < 2 & y > 3", "x<2", "")],
        warnings=["<script>alert(1)</script>"],
    )
    w._display_steps_report(vol, None, RevolutionAxis.x_axis(), "0", "<1>")
    plain = w.steps_text.toPlainText()
    assert "Paso <b>1</b>" in plain and "si x < 2 & y > 3" in plain and "[0, <1>]" in plain
    w._display_pedagogical_report(None, vol, None, RevolutionAxis.x_axis())
    assert "<script>alert(1)</script>" in w.results_text.toPlainText()


# ── Cierre con cálculo en curso (antes: SIGABRT) ────────────────────────────

@pytest.mark.parametrize("backend", ["thread", "process"])
def test_closing_during_a_calculation_exits_cleanly(backend: str) -> None:
    script = textwrap.dedent(f"""
        import sys
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from integrallab.ui.main_window import MainWindow
        app = QApplication(sys.argv)
        w = MainWindow(); w._show_dialogs = False; w._backend_failed = {backend == "thread"}
        w.expression_input.setText("log(x+1)*x + 1"); w.limit_a_input.setText("0"); w.limit_b_input.setText("2")
        w.axis_combo.setCurrentIndex(3)
        def go():
            w._on_plot_clicked()
            assert w._job_running()
            QTimer.singleShot(200, lambda: (w.close(), app.quit()))
        QTimer.singleShot(300, go)
        app.exec()
        del w
        print("OK")
    """)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QTWEBENGINE_DISABLE_SANDBOX="1")
    env["PYTHONPATH"] = os.pathsep.join([os.getcwd(), env.get("PYTHONPATH", "")])
    proc = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK" in proc.stdout
    assert "Destroyed while thread" not in proc.stderr


# ── Panel de chat ───────────────────────────────────────────────────────────

def test_chat_panel_without_controller_does_not_stay_busy(qapp: QApplication) -> None:
    panel = ChatPanel()
    panel._input.setPlainText("¿integral de x?")
    panel._on_send()
    assert not panel.is_busy and panel._send.text() == "Enviar"


def test_chat_panel_recovers_if_controller_never_finishes(qapp: QApplication) -> None:
    panel = ChatPanel()
    cancels: list[bool] = []
    panel.prompt_submitted.connect(lambda _t: None)
    panel.cancel_requested.connect(lambda: cancels.append(True))
    panel._input.setPlainText("hola")
    panel._on_send()
    assert panel.is_busy and panel._send.text() == "Detener"
    panel._on_escape()
    assert cancels and panel._send.text() == "Cancelando…"
    panel._on_watchdog()  # el controlador no llamó a finish()
    assert not panel.is_busy and panel._send.text() == "Enviar"


def test_math_label_renders_formula(qapp: QApplication) -> None:
    label = MathLabel(r"\int_0^1 x^2\,dx")
    assert label.height() > 10  # antes: pixmap vacío de 0 px
    assert MathLabel(r"\badcommand{").text() == r"\badcommand{"

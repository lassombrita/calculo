"""Fórmulas LaTeX de los reportes pedagógicos y su pre-renderizado fuera de la interfaz.

Responsabilidad:
Definir en un solo lugar qué fórmulas muestran los reportes (tarjeta de resultados y
pestaña «Desarrollo») para que el proceso de cálculo pueda renderizarlas a PNG con
Matplotlib (MathText) y la interfaz solo tenga que insertarlas. Renderizarlas en el hilo
de Qt costaba 150–300 ms por cálculo (un tirón visible justo cuando el sólido empieza a
girar). Este módulo no importa Qt.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from integrallab.core.solids import SolutionStep, VolumeResult
from integrallab.viz.latex_render import latex_to_base64_html


class FormulaSpec(NamedTuple):
    """Parámetros exactos de ``latex_to_base64_html`` para una fórmula de un reporte."""

    latex: str
    fontsize: int
    color: str
    fallback: str


def volume_formula(vol_res: VolumeResult) -> FormulaSpec:
    latex = f"V = {vol_res.exact_latex}" if vol_res.exact_latex else f"V = {vol_res.exact_plain_text}"
    return FormulaSpec(latex, 13, "#27ae60", f"V = {vol_res.exact_plain_text}")


def setup_formula(vol_res: VolumeResult) -> FormulaSpec | None:
    latex = vol_res.integral_setup_latex or vol_res.integrand_latex
    if not latex:
        return None
    return FormulaSpec(latex, 12, "#1e3a8a", vol_res.integrand_plain_text)


def step_formula(step: SolutionStep) -> FormulaSpec | None:
    if not step.expression_latex:
        return None
    return FormulaSpec(step.expression_latex, 12, "#0f172a", step.expression_plain_text)


def final_formula(vol_res: VolumeResult) -> FormulaSpec:
    latex = f"V = {vol_res.exact_latex}" if vol_res.exact_latex else f"V = {vol_res.exact_plain_text}"
    return FormulaSpec(latex, 14, "#047857", f"V = {vol_res.exact_plain_text}")


def report_formulas(vol_res: VolumeResult) -> list[FormulaSpec]:
    """Todas las fórmulas que usan los dos reportes de un volumen."""
    specs: list[FormulaSpec | None] = [volume_formula(vol_res), setup_formula(vol_res)]
    specs.extend(step_formula(step) for step in vol_res.steps)
    specs.append(final_formula(vol_res))
    return [s for s in specs if s is not None]


def render_formula(spec: FormulaSpec) -> str:
    """Etiqueta ``<img>`` (o texto de respaldo) para una fórmula."""
    return latex_to_base64_html(spec.latex, fontsize=spec.fontsize, color=spec.color, fallback_text=spec.fallback)


def prerender_report(output: Any) -> dict[FormulaSpec, str]:
    """Renderiza de antemano las fórmulas de un ``CalculationOutput`` exitoso."""
    vol_res = getattr(output, "vol_res", None)
    if vol_res is None or not vol_res.is_success:
        return {}
    return {spec: render_formula(spec) for spec in report_formulas(vol_res)}


def serve_calculations(conn: Any) -> None:
    """Punto de entrada del proceso de cálculo: pipeline + pre-renderizado de fórmulas."""
    import contextlib
    import multiprocessing
    import os
    import sys
    import threading

    from integrallab.core.pipeline import serve_requests
    from integrallab.viz.style import apply_mpl_theme

    parent = multiprocessing.parent_process()
    if parent is not None and sys.platform.startswith("linux"):
        # Refuerzo en Linux: el núcleo mata este proceso al morir el hilo que lo creó (el hilo
        # de Qt), aunque el hilo vigía no consiga el GIL a tiempo. Windows/macOS: solo el vigía.
        with contextlib.suppress(Exception):
            import ctypes
            import signal

            ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG
            if not parent.is_alive():  # el padre murió antes del prctl
                os._exit(0)
    if parent is not None:
        def _exit_with_parent() -> None:
            # Si la interfaz muere de golpe (kill -9, «Finalizar tarea», cuelgue de Qt) este
            # proceso no recibe nada mientras calcula y seguía al 95 % de CPU como huérfano.
            parent.join()
            os._exit(0)

        threading.Thread(target=_exit_with_parent, name="vigila-padre", daemon=True).start()

    apply_mpl_theme()  # misma tipografía matemática (STIX) que en el proceso de la interfaz
    serve_requests(conn, postprocess=prerender_report)

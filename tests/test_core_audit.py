"""Regresiones de la auditoría UI/3D sobre módulos del núcleo (parser, interpolación, sólidos, pipeline).

Cada prueba documenta un defecto encontrado ejecutando la aplicación real:
- La interfaz desviaba ``max(1,2)*x``, ``log(x,2)`` o ``0,5*(x+1)`` al lector de puntos.
- El spline (≥ 5 puntos) no se podía usar: su texto ``Piecewise`` no es parseable y
  ``sympy.solve`` sobre un ``Piecewise`` no terminaba.
- ``interpolate_newton`` perdía las diferencias divididas pequeñas (< 1e-7).
- ``recommend_method`` tardaba ~36 s con ``sin(x)**2*cos(x)**3 + 2`` por un ``solve`` innecesario.
"""

from __future__ import annotations

import math
import threading
import time
from multiprocessing import Pipe

import numpy as np
import pytest

from integrallab.core.interpolation import (
    interpolate_cubic_spline,
    interpolate_lagrange,
    interpolate_newton,
)
from integrallab.core.operations import integrate_definite, subtract_expressions
from integrallab.core.parser import is_points_input, parse_math_expression
from integrallab.core.pipeline import (
    CalculationCancelled,
    CalculationOutput,
    CalculationRequest,
    run_calculation,
    serve_requests,
)
from integrallab.core.solids import (
    Region2D,
    RevolutionAxis,
    SolidMethod,
    _scan_interior_roots,
    calculate_revolution_volume,
    find_curve_crossings,
    recommend_method,
)

import sympy

X = sympy.Symbol("x")
_trapz = getattr(np, "trapezoid", None) or np.trapz  # NumPy 1.x / 2.x


# ── Detección estricta de puntos ────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    ["(0, 1), (1, 2)", "[0, 1]; [2, 3]", "0, 1; 2, 3", "(1, 2)", "(0,0);(1,1)", "1e3, 2; 3, 4.5", "0 1\n1 3"],
)
def test_points_input_still_detects_point_lists(text: str) -> None:
    assert is_points_input(text) is True


@pytest.mark.parametrize(
    "text",
    ["max(1,2)*x", "min(x,1)", "log(x,2)", "atan2(x,1)", "root(x,3)", "0,5*(x+1)", "x*(1,5)", "(1,5)*x", "sin(x)"],
)
def test_expressions_with_commas_are_not_points(text: str) -> None:
    """Antes bastaba con '(' + ',' para tratar la entrada como puntos y fallar."""
    assert is_points_input(text) is False
    assert parse_math_expression(text).sympy_expr is not None


# ── Interpolación ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", [12, 16])
def test_newton_keeps_small_divided_differences(n: int) -> None:
    """Con datos suaves las diferencias de orden alto son < 1e-7 y antes se truncaban a 0."""
    pts = [(i * 0.5, math.sin(i * 0.5)) for i in range(n)]
    res = interpolate_newton(pts)
    assert res.is_success
    poly = sympy.Poly(sympy.expand(res.sympy_expr), X)
    assert poly.degree() == n - 1
    worst = max(abs(res.evaluate(x) - y) for x, y in pts)
    assert worst < 1e-6


def test_newton_with_large_abscissas_interpolates() -> None:
    """Abscisas grandes (años) producen diferencias divididas diminutas."""
    pts = [(2000.0, 1.0), (2010.0, 3.0), (2020.0, 2.0), (2030.0, 5.0), (2040.0, 4.0)]
    res = interpolate_newton(pts)
    assert res.is_success
    assert max(abs(res.evaluate(x) - y) for x, y in pts) < 1e-6


def test_spline_to_parsed_expression_feeds_the_domain() -> None:
    res = interpolate_cubic_spline([(0, 0), (1, 1), (2, 4), (3, 9), (4, 16)])
    parsed = res.to_parsed_expression("(0,0),(1,1),(2,4),(3,9),(4,16)")
    assert parsed.sympy_expr.has(sympy.Piecewise)
    assert parsed.variables == ["x"]
    area = integrate_definite(parsed, 0, 4)
    assert area.is_success
    # ∫ S(x) dx con S el spline natural: comparar con una cuadratura numérica fina.
    xs = np.linspace(0, 4, 40001)
    ys = np.array([res.evaluate(float(v)) for v in xs[::100]])
    approx = _trapz(ys, xs[::100])
    assert area.value == pytest.approx(approx, rel=1e-4)


def test_spline_solid_volume_is_computed_without_hanging() -> None:
    """Antes ``sympy.solve`` sobre el Piecewise no terminaba (> 40 s)."""
    res = interpolate_cubic_spline([(0, 0), (1, 1), (2, 4), (3, 9), (4, 16)])
    parsed = res.to_parsed_expression()
    start = time.perf_counter()
    vol = calculate_revolution_volume(Region2D(parsed, None, 0, 4), RevolutionAxis.x_axis(), SolidMethod.DISKS)
    assert time.perf_counter() - start < 20
    assert vol.is_success
    f = sympy.lambdify(X, res.sympy_expr, "numpy")
    xs = np.linspace(0, 4, 200001)
    expected = math.pi * _trapz(f(xs) ** 2, xs)
    assert vol.numeric_value == pytest.approx(expected, rel=1e-6)


def test_lagrange_small_sets_unchanged() -> None:
    res = interpolate_lagrange([(0, 0), (1, 1), (2, 4)])
    assert res.is_success and res.evaluate(3.0) == pytest.approx(9.0)


# ── Operaciones ─────────────────────────────────────────────────────────────

def test_subtract_expressions_matches_reparsing() -> None:
    f, g = parse_math_expression("sqrt(x)"), parse_math_expression("x**2")
    diff = subtract_expressions(f, g)
    assert diff.sympy_expr == parse_math_expression("(sqrt(x)) - (x**2)").sympy_expr
    assert diff.plain_text == parse_math_expression("(sqrt(x)) - (x**2)").plain_text


# ── Barrido numérico previo a sympy.solve ───────────────────────────────────

def test_scan_classifies_roots() -> None:
    assert _scan_interior_roots(X**2 + 1, X, -2.0, 2.0)[0] == "none"
    status, roots = _scan_interior_roots(X - sympy.sqrt(2), X, 0.0, 3.0)
    assert status == "roots" and roots == pytest.approx([math.sqrt(2)], abs=1e-9)
    assert _scan_interior_roots((X - 0.5) ** 2, X, 0.0, 1.0)[0] == "unknown"   # tangencia
    assert _scan_interior_roots(sympy.sqrt(X), X, -1.0, 1.0)[0] == "unknown"     # fuera de dominio


def test_recommend_is_fast_when_curves_do_not_cross() -> None:
    """Antes ~36 s: sympy.solve(sin²x·cos³x + 2 = 0) para un aviso que no aplica."""
    region = Region2D("sin(x)**2*cos(x)**3 + 2", None, "0", "pi")
    start = time.perf_counter()
    rec = recommend_method(region, RevolutionAxis.x_axis())
    assert time.perf_counter() - start < 3.0
    assert rec.is_decidable and rec.recommended_method == SolidMethod.DISKS


def test_symbolic_crossings_are_kept_exact() -> None:
    """Cuando sí hay cruce se sigue usando sympy.solve (bordes exactos de la partición)."""
    crossings = find_curve_crossings(X**2, sympy.sqrt(X), X, 0.0, 0.0, 2.0)
    assert len(crossings) == 1
    assert crossings[0][0] == pytest.approx(1.0)
    assert crossings[0][1] == 1


# ── Pipeline único ──────────────────────────────────────────────────────────

def _request(f: str, g: str | None, a: str, b: str, axis: RevolutionAxis, method=None) -> CalculationRequest:
    return CalculationRequest(
        f=parse_math_expression(f), g=parse_math_expression(g) if g else None,
        a_text=a, b_text=b, axis=axis, method=method, mesh_radial=24, mesh_axial=18,
    )


def test_pipeline_delivers_mesh_before_volume() -> None:
    events: list[str] = []
    out = run_calculation(
        _request("x**2", None, "0", "1", RevolutionAxis.x_axis()),
        on_mesh=lambda mesh: events.append(f"mesh:{mesh.x_outer.shape}"),
    )
    assert events == ["mesh:(18, 24)"]
    assert out.vol_res.is_success and out.vol_res.numeric_value == pytest.approx(math.pi / 5)
    assert out.res_2d.exact_plain_text == "1/3"


def test_pipeline_rejects_axis_inside_region_before_heavy_work() -> None:
    events: list[str] = []
    out = run_calculation(
        _request("x", None, "0", "1", RevolutionAxis.horizontal(0.5), SolidMethod.DISKS),
        on_mesh=lambda mesh: events.append("mesh"),
    )
    assert events == []  # no se muestra un sólido que luego se rechaza
    assert not out.vol_res.is_success and "atraviesa" in (out.vol_res.error_message or "")


def test_pipeline_is_cancellable_between_steps() -> None:
    with pytest.raises(CalculationCancelled):
        run_calculation(_request("x**2", None, "0", "1", RevolutionAxis.x_axis()), is_cancelled=lambda: True)


def test_serve_requests_protocol() -> None:
    """El bucle del proceso de cálculo responde malla, extras y resultado; termina con None."""
    parent, child = Pipe()
    worker = threading.Thread(target=serve_requests, args=(child, lambda out: {"ok": True}), daemon=True)
    worker.start()
    parent.send((7, _request("x", None, "0", "1", RevolutionAxis.x_axis())))
    kinds = []
    while True:
        kind, job_id, payload = parent.recv()
        assert job_id == 7
        kinds.append(kind)
        if kind == "done":
            assert isinstance(payload, CalculationOutput) and payload.vol_res.is_success
            break
    assert kinds == ["mesh", "assets", "done"]
    parent.send(None)
    worker.join(timeout=5)
    assert not worker.is_alive()

"""Inversión a dy por franjas horizontales y tramos de signo constante (hallazgos A1, A6, A5, M4).

Cada volumen se compara con su forma cerrada y con la cuadratura independiente
``numeric_volume`` (prueba de propiedades, hallazgo M13): así un error que se cancela por
casualidad en un ejemplo no pasa en los demás.
"""

from __future__ import annotations

import math

import pytest
import sympy

from integrallab.core.operations import area_between, integrate_definite
from integrallab.core.parser import parse_math_expression
from integrallab.core.solids import (
    Region2D,
    RevolutionAxis,
    SolidMethod,
    calculate_revolution_volume,
    can_invert_for_method,
    numeric_volume,
)
from integrallab.core.volume import horizontal_strips, real_branch, sign_cut_points
from integrallab.core.volume.pieces import real_root_form

pi = math.pi
X, Y = RevolutionAxis.x_axis(), RevolutionAxis.y_axis()


@pytest.mark.parametrize(
    ("f", "a", "b", "axis", "method", "expected"),
    [
        # Los 7 casos de la auditoría (antes: 3π/5, 7,5π, 6,4π, 0,8π, 5π/3, ≈6,807, ≈6,702).
        ("x**3", 0, 1, Y, SolidMethod.DISKS, 2 * pi / 5),
        ("4 - x**2", 1, 2, Y, SolidMethod.DISKS, 4.5 * pi),
        ("sqrt(x)", 0, 4, Y, SolidMethod.WASHERS, 25.6 * pi),
        ("x**2", 0, 1, X, SolidMethod.SHELLS, 0.2 * pi),
        ("x + 1", 0, 1, X, SolidMethod.SHELLS, 7 * pi / 3),
        ("x**2", 0, 1, RevolutionAxis.vertical(2), SolidMethod.WASHERS, 5 * pi / 6),
        ("x**2", 0, 1, RevolutionAxis.horizontal(-1), SolidMethod.SHELLS, 13 * pi / 15),
        # Casos que ya daban bien (no deben romperse).
        ("x**2", 0, 1, Y, SolidMethod.WASHERS, pi / 2),
        ("4 - x**2", 0, 2, Y, SolidMethod.DISKS, 8 * pi),
        ("4 - x**2", 0, 2, X, SolidMethod.SHELLS, 256 * pi / 15),
        ("exp(x)", 0, 1, X, SolidMethod.SHELLS, pi * (math.e**2 - 1) / 2),
        # Franja con y < 0: la rama real de ∛y (SymPy la da como compleja) se reescribe −(−y)^(1/3).
        ("x**3", -1, 0, RevolutionAxis.vertical(1), SolidMethod.DISKS, 0.9 * pi),
    ],
)
def test_inverted_volumes_match_closed_form(f, a, b, axis, method, expected) -> None:
    region = Region2D(parse_math_expression(f), None, a, b)
    res = calculate_revolution_volume(region, axis, method)
    assert res.is_success, res.error_message
    assert res.numeric_value == pytest.approx(expected, rel=1e-10)
    assert res.numeric_value == pytest.approx(numeric_volume(region, axis), rel=1e-8)
    assert "despeje" in res.steps[0].title.lower()
    assert res.steps[1].title.startswith("2. ")  # numeración continua tras el despeje (M8)


def test_strips_use_the_real_boundaries() -> None:
    """4 − x² en [1, 2]: una franja y ∈ [0, 3] con bordes x = 1 (recta) y x = √(4 − y)."""
    x, y = sympy.symbols("x y")
    strips = horizontal_strips(4 - x**2, sympy.Integer(0), x, y, 1.0, 2.0, sympy.Integer(1), sympy.Integer(2), [])
    assert len(strips) == 1
    (left, right), = strips[0].intervals
    assert (strips[0].y0, strips[0].y1) == (0, 3)
    assert left.kind == "a" and left.expr == 1
    assert right.kind == "f" and sympy.simplify(right.expr - sympy.sqrt(4 - y)) == 0


def test_two_curves_between_sqrt_and_x() -> None:
    region = Region2D("sqrt(x)", "x", 0, 1)
    res = calculate_revolution_volume(region, Y, SolidMethod.WASHERS)
    assert res.numeric_value == pytest.approx(2 * pi / 15, rel=1e-12)


def test_can_invert_for_method_uses_strips() -> None:
    assert can_invert_for_method(Region2D("x**3", None, 0, 1), Y, SolidMethod.DISKS)
    assert can_invert_for_method(Region2D("x**2", None, 0, 1), X, SolidMethod.SHELLS)


@pytest.mark.parametrize(
    ("f", "g", "a", "b", "axis", "method"),
    [
        ("x", "x**2", 0, 2, X, SolidMethod.DISKS),       # M4: antes −11,73 (negativo)
        ("x", "x**2", 0, 2, X, SolidMethod.WASHERS),
        ("x", "x**2", 0, 2, Y, SolidMethod.SHELLS),
        ("x**3", None, -1, 1, X, SolidMethod.DISKS),     # el radio cambia de signo en 0
        ("cbrt(x) + 2", None, -1, 1, X, SolidMethod.DISKS),
        ("abs(x - 1) + 1", None, 0, 3, Y, SolidMethod.SHELLS),
        ("sin(x) + 2", "1", 0, "2*pi", RevolutionAxis.horizontal(-1), SolidMethod.WASHERS),
        ("x*exp(-x)", None, 0, 3, RevolutionAxis.vertical(-1), SolidMethod.SHELLS),
    ],
)
def test_direct_methods_match_quadrature(f, g, a, b, axis, method) -> None:
    region = Region2D(parse_math_expression(f), parse_math_expression(g) if g else None, a, b)
    res = calculate_revolution_volume(region, axis, method)
    assert res.is_success, res.error_message
    assert res.numeric_value == pytest.approx(numeric_volume(region, axis), rel=1e-8)


def test_disks_with_a_hole_become_piecewise_washers() -> None:
    res = calculate_revolution_volume(Region2D("x", "x**2", 0, 2), X, SolidMethod.DISKS)
    assert res.method == SolidMethod.WASHERS
    assert res.numeric_value == pytest.approx(4 * pi, rel=1e-12)
    assert any("cruzan" in w for w in res.warnings)


def test_real_branch_and_cuts() -> None:
    x = sympy.Symbol("x")
    cuts = sign_cut_points((sympy.cbrt(x) + sympy.Abs(x - 2),), x, -1.0, 3.0)
    assert [c[1] for c in cuts] == [0, 2]
    assert real_branch(sympy.cbrt(x), x, -1.0, 0.0) == -(-x) ** sympy.Rational(1, 3)
    assert real_branch(sympy.Abs(x - 2), x, 0.0, 2.0) == 2 - x
    fn = sympy.lambdify(x, real_root_form(sympy.cbrt(x)), "mpmath")
    assert float(fn(-8)) == pytest.approx(-2.0)


@pytest.mark.parametrize(
    ("f", "a", "b", "integral", "area"),
    [
        ("sin(x)", "0", "2*pi", 0, 4),                  # A5: la etiqueta mostraba 0 bajo un área de 4
        ("cbrt(x)", "-1", "1", 0, sympy.Rational(3, 2)),  # A6: antes «resultado complejo»
        ("x**(2/3)", "-1", "1", sympy.Rational(6, 5), sympy.Rational(6, 5)),
    ],
)
def test_integral_and_area_are_different_quantities(f, a, b, integral, area) -> None:
    res = integrate_definite(f, a, b)
    assert res.is_success, res.error_message
    assert sympy.simplify(sympy.sympify(res.exact_plain_text) - integral) == 0
    ar = area_between(f, None, a, b)
    assert ar.is_success and sympy.simplify(sympy.sympify(ar.exact_plain_text) - area) == 0


def test_area_between_two_curves_splits_at_crossing() -> None:
    ar = area_between("x", "x**2", "0", "2")
    assert ar.exact_plain_text == "1"  # 1/6 + 5/6; la integral con signo es −2/3

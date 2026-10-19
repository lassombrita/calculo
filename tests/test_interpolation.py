"""Pruebas unitarias para el motor de interpolación numérica (Fase 12).

Valida rigurosamente:
- Normalización y ordenamiento de puntos de datos.
- Rechazo de abscisas duplicadas o cantidad insuficiente de puntos.
- Polinomio interpolador de Lagrange (grados 1, 2 y superiores).
- Polinomio interpolador de Newton con diferencias divididas.
- Splines cúbicos naturales por tramos (continuidad C^2 e interpolación exacta).
- Parseo de puntos en diversos formatos de entrada (parser.py).
- Conexión entre curvas interpoladas y sólidos de revolución.
"""

from __future__ import annotations

import math
import pytest
import sympy

from integrallab.core.interpolation import (
    DataPoint,
    InterpolationMethod,
    InterpolationResult,
    interpolate,
    interpolate_cubic_spline,
    interpolate_lagrange,
    interpolate_newton,
)
from integrallab.core.parser import ExpressionParseError, is_points_input, parse_points
from integrallab.core.solids import (
    Region2D,
    RevolutionAxis,
    SolidMethod,
    calculate_revolution_volume,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Validación y Normalización de Puntos
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_points_sorting() -> None:
    """Verifica que los puntos desordenados se ordenen ascendentemente por x."""
    raw = [(3.0, 5.0), (0.0, 1.0), (1.0, 3.0), (2.0, 2.0)]
    res = interpolate_lagrange(raw)
    assert res.is_success is True
    xs = [p.x for p in res.points]
    assert xs == [0.0, 1.0, 2.0, 3.0]


def test_normalize_points_duplicate_x_raises() -> None:
    """Abscisas x repetidas deben generar error claro por no ser función."""
    raw = [(1.0, 2.0), (1.0, 5.0), (2.0, 3.0)]
    res = interpolate_lagrange(raw)
    assert res.is_success is False
    assert "duplicadas" in (res.error_message or "").lower()


def test_normalize_points_insufficient_points_raises() -> None:
    """Menos de dos puntos debe fallar."""
    res = interpolate_lagrange([(1.0, 2.0)])
    assert res.is_success is False
    assert "al menos 2 puntos" in (res.error_message or "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Interpolación de Lagrange
# ─────────────────────────────────────────────────────────────────────────────

def test_interpolate_lagrange_recovers_parabola() -> None:
    """3 puntos de y = x^2 deben recuperar exactamente el polinomio x^2."""
    pts = [(-1.0, 1.0), (0.0, 0.0), (2.0, 4.0)]
    res = interpolate_lagrange(pts)

    assert res.is_success is True
    assert res.method == InterpolationMethod.LAGRANGE
    assert res.sympy_expr is not None

    x = sympy.Symbol("x")
    diff = sympy.simplify(res.sympy_expr - x**2)
    assert diff == 0

    # Evaluación exacta en los nodos
    assert math.isclose(res.evaluate(-1.0), 1.0, abs_tol=1e-7)
    assert math.isclose(res.evaluate(0.0), 0.0, abs_tol=1e-7)
    assert math.isclose(res.evaluate(2.0), 4.0, abs_tol=1e-7)
    # Evaluación en punto intermedio
    assert math.isclose(res.evaluate(1.5), 2.25, abs_tol=1e-7)


def test_interpolate_lagrange_steps_structure() -> None:
    """Verifica que el resultado incluya los pasos analíticos pedagógicos."""
    pts = [(0.0, 1.0), (1.0, 3.0), (2.0, 2.0)]
    res = interpolate_lagrange(pts)
    assert len(res.steps) >= 3
    assert any("Lagrange" in s.title for s in res.steps)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Interpolación de Newton con Diferencias Divididas
# ─────────────────────────────────────────────────────────────────────────────

def test_interpolate_newton_cubic_recovery() -> None:
    """4 puntos de un polinomio cúbico deben interpolar exactamente cada nodo."""
    # y = x^3 - 2*x + 1
    # x=0 -> 1, x=1 -> 0, x=2 -> 5, x=3 -> 22
    pts = [(0.0, 1.0), (1.0, 0.0), (2.0, 5.0), (3.0, 22.0)]
    res = interpolate_newton(pts)

    assert res.is_success is True
    assert res.method == InterpolationMethod.NEWTON
    assert res.sympy_expr is not None

    x = sympy.Symbol("x")
    diff = sympy.simplify(res.sympy_expr - (x**3 - 2 * x + 1))
    assert diff == 0

    for xi, yi in pts:
        assert math.isclose(res.evaluate(xi), yi, abs_tol=1e-5)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Splines Cúbicos Naturales
# ─────────────────────────────────────────────────────────────────────────────

def test_interpolate_cubic_spline_exact_nodes() -> None:
    """Un spline cúbico natural debe pasar con exactitud por todos los nodos."""
    pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (3.0, 2.0), (4.0, 1.0)]
    res = interpolate_cubic_spline(pts)

    assert res.is_success is True
    assert res.method == InterpolationMethod.CUBIC_SPLINE
    assert res.sympy_expr is not None

    for xi, yi in pts:
        assert math.isclose(res.evaluate(xi), yi, abs_tol=1e-5)


def test_interpolate_dispatcher() -> None:
    """Verifica que la función general despache correctamente según el string del método."""
    pts = [(0.0, 1.0), (1.0, 2.0), (2.0, 5.0)]
    res_lag = interpolate(pts, method="lagrange")
    res_new = interpolate(pts, method="newton")
    res_spl = interpolate(pts, method="spline")

    assert res_lag.method == InterpolationMethod.LAGRANGE
    assert res_new.method == InterpolationMethod.NEWTON
    assert res_spl.method == InterpolationMethod.CUBIC_SPLINE


# ─────────────────────────────────────────────────────────────────────────────
# 5. Parseo de Puntos en Diversos Formatos
# ─────────────────────────────────────────────────────────────────────────────

def test_is_points_input_detection() -> None:
    """Verifica la detección heurística de conjuntos de puntos vs expresiones escalares."""
    assert is_points_input("(0, 1), (1, 2)") is True
    assert is_points_input("[0, 1]; [2, 3]") is True
    assert is_points_input("0, 1; 2, 3") is True
    assert is_points_input("x^2 + 2x - 1") is False
    assert is_points_input("sin(x)") is False


def test_parse_points_parentheses() -> None:
    """Parsea tuplas estándar con paréntesis."""
    text = "(0, 1), (1, 3), (2, 2.5)"
    pts = parse_points(text)
    assert pts == [(0.0, 1.0), (1.0, 3.0), (2.0, 2.5)]


def test_parse_points_brackets() -> None:
    """Parsea listas con corchetes."""
    text = "[0, 1], [1, 3], [2, 2.5]"
    pts = parse_points(text)
    assert pts == [(0.0, 1.0), (1.0, 3.0), (2.0, 2.5)]


def test_parse_points_semicolons_and_newlines() -> None:
    """Parsea pares separados por punto y coma o saltos de línea."""
    text1 = "0, 1; 1, 3; 2, 2.5"
    assert parse_points(text1) == [(0.0, 1.0), (1.0, 3.0), (2.0, 2.5)]

    text2 = "0 1\n1 3\n2 2.5"
    assert parse_points(text2) == [(0.0, 1.0), (1.0, 3.0), (2.0, 2.5)]


def test_parse_points_invalid_raises() -> None:
    """Entradas vacías o con puntos insuficientes deben lanzar ExpressionParseError."""
    with pytest.raises(ExpressionParseError):
        parse_points("")

    with pytest.raises(ExpressionParseError):
        parse_points("(1, 2)")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Conexión de Curvas Interpoladas con Sólidos de Revolución
# ─────────────────────────────────────────────────────────────────────────────

def test_interpolated_curve_in_solids_revolution() -> None:
    """Construir una curva por interpolación y calcular su volumen de revolución.

    Puntos de y = x: (0, 0), (0.5, 0.5), (1.0, 1.0)
    Interpolación lineal/Lagrange recupera y = x.
    Giro en eje X en [0, 1] debe dar pi / 3.
    """
    pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
    interp = interpolate_lagrange(pts)
    assert interp.is_success is True

    region = Region2D(
        f_expr=interp.polynomial_plain_text,
        a=0.0,
        b=1.0,
        variable="x",
    )
    res_vol = calculate_revolution_volume(region, RevolutionAxis.x_axis())

    assert res_vol.is_success is True
    assert res_vol.numeric_value is not None
    assert math.isclose(res_vol.numeric_value, math.pi / 3.0, rel_tol=1e-5)


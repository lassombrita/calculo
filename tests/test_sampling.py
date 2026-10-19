"""Tests unitarios para el muestreo numérico de curvas."""

from __future__ import annotations

import math

import numpy as np

from integrallab.core.sampling import CurveData, robust_y_window, sample_expression


def test_sample_expression_range() -> None:
    """Verifica que el muestreo genere la cantidad correcta de puntos en el rango."""
    curve = sample_expression("x^2", x_min=-2.0, x_max=2.0, num_points=5)
    assert curve.is_valid
    assert len(curve.x_values) == 5
    assert len(curve.y_values) == 5
    assert math.isclose(curve.x_values[0], -2.0)
    assert math.isclose(curve.x_values[-1], 2.0)
    assert math.isclose(curve.y_values[0], 4.0)
    assert math.isclose(curve.y_values[-1], 4.0)


def test_sample_expression_invalid_bounds() -> None:
    """Verifica validación cuando x_min >= x_max."""
    curve = sample_expression("x", x_min=5.0, x_max=2.0)
    assert not curve.is_valid
    assert "menor que x_max" in (curve.error_message or "")


def test_sample_expression_singularity_handled() -> None:
    """Verifica que singularidades (división por cero) no arrojen excepción y produzcan nan."""
    curve = sample_expression("1/x", x_min=-1.0, x_max=1.0, num_points=3)
    assert curve.is_valid
    # El punto medio x=0 debe ser math.nan
    assert math.isnan(curve.y_values[1])


def test_sample_expression_default_is_uniform_and_unchanged() -> None:
    """Sin adaptive=True el muestreo sigue siendo la malla uniforme de siempre."""
    curve = sample_expression("sin(x)", x_min=0.0, x_max=1.0, num_points=11)

    assert len(curve.x_values) == 11
    assert np.allclose(np.diff(curve.x_values), 0.1)


def test_sample_expression_adaptive_refines_oscillation() -> None:
    """Con adaptive=True una función oscilante recibe más puntos que la malla inicial."""
    uniform = sample_expression("sin(50*x)", x_min=0.0, x_max=2.0, num_points=80)
    adaptive = sample_expression(
        "sin(50*x)", x_min=0.0, x_max=2.0, num_points=80, adaptive=True
    )

    assert adaptive.is_valid
    assert len(adaptive.x_values) > len(uniform.x_values)
    assert adaptive.x_values[0] == 0.0
    assert adaptive.x_values[-1] == 2.0


def test_sample_expression_adaptive_cuts_tan_at_poles() -> None:
    """tan(x) adaptativo deja nan junto a los polos en lugar de un trazo vertical falso."""
    curve = sample_expression("tan(x)", x_min=-2.0, x_max=2.0, num_points=200, adaptive=True)
    xs = np.asarray(curve.x_values)
    ys = np.asarray(curve.y_values)

    assert curve.is_valid
    assert np.any(np.isnan(ys[np.abs(xs - math.pi / 2) < 0.05]))
    assert np.any(np.isnan(ys[np.abs(xs + math.pi / 2) < 0.05]))


def test_sample_expression_adaptive_matches_uniform_for_smooth_function() -> None:
    """Una parábola no necesita refinado: los valores devueltos son los de la función."""
    curve = sample_expression("x^2", x_min=-2.0, x_max=2.0, num_points=50, adaptive=True)

    assert curve.is_valid
    xs = np.asarray(curve.x_values)
    assert np.allclose(curve.y_values, xs**2)


def test_robust_y_window_only_for_extreme_values() -> None:
    """Hay ventana sugerida con asíntotas; sin ellas (parábola) se mantiene el autoajuste."""
    tan_curve = sample_expression("tan(x)", x_min=-10.0, x_max=10.0, num_points=400, adaptive=True)
    parabola = sample_expression("x^2", x_min=-10.0, x_max=10.0, num_points=400, adaptive=True)

    assert robust_y_window([tan_curve]) is not None
    assert robust_y_window([parabola]) is None
    assert robust_y_window([CurveData(is_valid=False)]) is None


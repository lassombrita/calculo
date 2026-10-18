"""Tests unitarios para el muestreo numérico de curvas."""

from __future__ import annotations

import math
from integrallab.core.sampling import sample_expression


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


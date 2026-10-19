"""Tests unitarios para derivadas e integrales."""

from __future__ import annotations

import math
import pytest

from integrallab.core.operations import (
    differentiate,
    integrate_definite,
    integrate_indefinite,
)


def test_differentiate_polynomial() -> None:
    """Verifica derivada de primer y segundo orden para un polinomio."""
    res1 = differentiate("x^3 - 4*x^2 + 5*x + 1")
    assert res1.is_success
    assert res1.plain_text == "3*x**2 - 8*x + 5"

    res2 = differentiate("x^3 - 4*x^2 + 5*x + 1", order=2)
    assert res2.is_success
    assert res2.plain_text in ("6*x - 8", "2*(3*x - 4)")


def test_differentiate_invalid_order() -> None:
    """Verifica validación de orden de derivada."""
    res = differentiate("x^2", order=0)
    assert not res.is_success
    assert "entero positivo" in (res.error_message or "")


def test_integrate_indefinite_basic() -> None:
    """Verifica la integral indefinida con constante de integración."""
    res = integrate_indefinite("3*x^2 + 2*x")
    assert res.is_success
    assert "x**3 + x**2 + C" == res.plain_text


def test_integrate_definite_polynomial() -> None:
    """Verifica el cálculo de integral definida entre límites numéricos."""
    # Integral de x^2 entre 0 y 3 es 3^3 / 3 = 9.0
    res = integrate_definite("x^2", 0, 3)
    assert res.is_success
    assert res.value is not None
    assert math.isclose(res.value, 9.0, rel_tol=1e-5)
    assert res.exact_plain_text == "9"

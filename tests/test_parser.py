"""Tests unitarios para el parser de expresiones matemáticas."""

from __future__ import annotations

import pytest

from integrallab.core.parser import ExpressionParseError, parse_math_expression


def test_parse_simple_polynomial() -> None:
    """Verifica el parseo de un polinomio simple y soporte para ^."""
    expr = parse_math_expression("x^2 + 3*x - 5")
    assert expr.plain_text == "x**2 + 3*x - 5"
    assert "x" in expr.variables


def test_parse_implicit_multiplication() -> None:
    """Verifica que la multiplicación implícita (ej. 2x, 3cos(x)) sea interpretada."""
    expr = parse_math_expression("2x + 3sin(x)")
    assert "2*x" in expr.plain_text
    assert "sin(x)" in expr.plain_text


def test_parse_empty_string_raises_error() -> None:
    """Verifica que strings vacíos generen ExpressionParseError."""
    with pytest.raises(ExpressionParseError, match="no puede estar vacía"):
        parse_math_expression("   ")


def test_parse_invalid_syntax_raises_error() -> None:
    """Verifica que sintaxis rota genere ExpressionParseError amigable."""
    with pytest.raises(ExpressionParseError, match="Error de sintaxis"):
        parse_math_expression("x +++ * 3")


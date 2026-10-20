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



def test_parser_blocks_rce_payload() -> None:
    """Verifica que intentos de inyección de código sean rechazados (C1 audit)."""
    attacks = [
        "__import__('os').system('touch /tmp/x')",
        "__builtins__",
        "open('/etc/passwd')",
        "eval('1+1')",
        "exec('import os')",
        "x.system('ls')",
        "(lambda x: x)(1)",
    ]
    for attack in attacks:
        with pytest.raises(ExpressionParseError):
            parse_math_expression(attack)


def test_parser_normalizes_spanish_colombian_syntax() -> None:
    """Verifica el normalizador de modismos y notación en español (C6 audit)."""
    # sen(x) -> sin(x)
    expr_sen = parse_math_expression("sen(x)")
    assert "sin(x)" in expr_sen.plain_text

    # tg(x) -> tan(x)
    expr_tg = parse_math_expression("tg(x)")
    assert "tan(x)" in expr_tg.plain_text

    # Coma decimal 0,5*x -> 0.5*x
    expr_coma = parse_math_expression("0,5*x")
    assert "0.5*x" in expr_coma.plain_text or "x/2" in expr_coma.plain_text

    # Superíndice x²
    expr_sup = parse_math_expression("x² + 1")
    assert "x**2" in expr_sup.plain_text

    # Símbolo pi π
    expr_pi = parse_math_expression("π*x")
    assert "pi*x" in expr_pi.plain_text

    # Raíz cuadrada √
    expr_raiz = parse_math_expression("√x")
    assert "sqrt(x)" in expr_raiz.plain_text

    # Barras de valor absoluto |x|
    expr_abs = parse_math_expression("|x - 3|")
    assert "Abs(x - 3)" in expr_abs.plain_text

    # Constante de Euler e^(2x)
    expr_e = parse_math_expression("e^(2x)")
    assert "exp(2*x)" in expr_e.plain_text or "E**(2*x)" in expr_e.plain_text


def test_parser_handles_extended_aliases_and_log10() -> None:
    """Verifica que arcsin, arccot, ctg, cotg y log10 no se dividan en productos de letras (item 2)."""
    expr_arcsin = parse_math_expression("arcsin(x)")
    assert "asin(x)" in expr_arcsin.plain_text

    expr_arccot = parse_math_expression("arccot(x)")
    assert "acot(x)" in expr_arccot.plain_text

    expr_ctg = parse_math_expression("ctg(x)")
    assert "cot(x)" in expr_ctg.plain_text

    expr_cotg = parse_math_expression("cotg(x)")
    assert "cot(x)" in expr_cotg.plain_text

    expr_log10 = parse_math_expression("log10(x)")
    assert "log(x)" in expr_log10.plain_text and "10" in expr_log10.plain_text


def test_parser_blocks_unknown_functions_instead_of_silent_split() -> None:
    """Verifica que funciones desconocidas lancen ExpressionParseError en vez de multiplicarse (item 2)."""
    with pytest.raises(ExpressionParseError, match="no reconocida"):
        parse_math_expression("foobar(x)")

    with pytest.raises(ExpressionParseError, match="no reconocida"):
        parse_math_expression("qwerty(2*x)")


def test_parser_blocks_spaced_attribute_access() -> None:
    """Verifica que accesos a atributos con espacios (. real) sean bloqueados (item 3)."""
    with pytest.raises(ExpressionParseError):
        parse_math_expression("Integer(1). real")

    with pytest.raises(ExpressionParseError):
        parse_math_expression("x. __class__")

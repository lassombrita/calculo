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


# ─────────────────────────────────────────────────────────────────────────────
# Regresión: congelamiento de la UI con potencias y literales gigantes
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    [
        "9**9**9**9",
        "10**10**10",
        "x**(10**5)",
        "x**999999",
        "1e99999999",
        "x*1e99999999",
        "1e-99999999",
        "x+" * 600 + "x",
    ],
)
def test_parse_rejects_huge_inputs_quickly(text: str) -> None:
    """Entradas que antes congelaban la app deben rechazarse de inmediato."""
    import time

    start = time.perf_counter()
    with pytest.raises(ExpressionParseError):
        parse_math_expression(text)
    assert time.perf_counter() - start < 2.0


@pytest.mark.parametrize("text", ["2**3**2", "x**100", "10**400", "1e300", "2.5e-3*x", "x^x^x"])
def test_parse_accepts_reasonable_powers_and_literals(text: str) -> None:
    """Los límites de tamaño no deben bloquear entradas legítimas."""
    assert parse_math_expression(text).sympy_expr is not None


# ─────────────────────────────────────────────────────────────────────────────
# Regresión: la coma decimal no debe corromper funciones con varios argumentos
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("max(1,2)*x", "2*x"),
        ("min(3,4)*x", "3*x"),
        ("root(8,3)", "2"),
        ("log(8,2)", "3"),
        ("0,5*x", "0.5*x"),
        ("2,5x", "2.5*x"),
        ("x^2 + 3,5", "x**2 + 3.5"),
        ("x*(1,5)", "1.5*x"),
    ],
)
def test_decimal_comma_vs_function_arguments(text: str, expected: str) -> None:
    assert parse_math_expression(text).plain_text == expected


def test_comma_separated_number_list_is_rejected() -> None:
    """'1,2,3' ya no produce un valor sin sentido (0.36): es una expresión inválida."""
    with pytest.raises(ExpressionParseError):
        parse_math_expression("1,2,3")

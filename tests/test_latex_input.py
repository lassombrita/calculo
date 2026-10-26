"""Pruebas del conversor entre el editor visual (LaTeX) y el texto del parser."""

from __future__ import annotations

import pytest
import sympy

from integrallab.core.latex_input import (
    MAX_LATEX_LENGTH,
    LatexInputError,
    expression_to_latex,
    latex_to_expression,
)
from integrallab.core.parser import is_points_input, parse_math_expression


def _same(text_a: str, text_b: str) -> bool:
    a = parse_math_expression(text_a).sympy_expr
    b = parse_math_expression(text_b).sympy_expr
    return a == b or sympy.simplify(a - b) == 0


# LaTeX tal como lo emite MathLive al escribir con el teclado o con los botones (verificado en
# QtWebEngine) → expresión equivalente en texto.
@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"x^2+1", "x**2 + 1"),
        (r"\frac{1}{x}", "1/x"),
        (r"\frac13", "1/3"),
        (r"\frac{\sqrt{x}+1}{x^2-1}", "(sqrt(x) + 1)/(x**2 - 1)"),
        (r"\sqrt{\left(x\right)}", "sqrt(x)"),
        (r"\sqrt[3]{x}", "root(x, 3)"),
        (r"x^{\left(\frac13\right)}", "x**(1/3)"),
        (r"2x", "2*x"),
        (r"x\cdot y", "x*y"),
        (r"5\cdot10^3", "5000"),
        (r"x(x+1)", "x*(x + 1)"),
        (r"2\left(x+1\right)", "2*(x + 1)"),
        (r"e^{x}", "exp(x)"),
        (r"\mathrm{e}^{2x}", "exp(2*x)"),
        (r"e^{\left(-x^2\right)}", "exp(-x**2)"),
        (r"\pi x", "pi*x"),
        (r"-x^2", "-x**2"),
        (r"2^{-x}", "2**(-x)"),
        (r"x!", "x!"),
        (r"0,5x", "0.5*x"),
        (r"3.5x", "3.5*x"),
    ],
)
def test_algebra_templates(latex: str, expected: str) -> None:
    assert _same(latex_to_expression(latex), expected)


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"\sin\left(x\right)", "sin(x)"),
        (r"\sin x", "sin(x)"),
        (r"\sin 2x", "sin(2*x)"),            # el argumento es todo el producto
        (r"\sin x^2", "sin(x**2)"),
        (r"x\sin x\cos x", "x*sin(x)*cos(x)"),  # otra función corta el argumento
        (r"\sin^{2}x", "sin(x)**2"),
        (r"\tan\left(x\right)^2", "tan(x)**2"),
        (r"\sin^{-1}x", "asin(x)"),
        (r"\arcsin\left(x\right)", "asin(x)"),
        (r"sen\left(x\right)", "sin(x)"),     # alias es-CO escrito letra a letra
        (r"senx", "sin(x)"),
        (r"tg\left(x\right)", "tan(x)"),
        (r"abs\left(x\right)", "Abs(x)"),
        (r"\ln\left(x\right)", "log(x)"),
        (r"\ln|x|", "log(Abs(x))"),
        (r"\log\left(x\right)", "log(x, 10)"),  # convención de calculadora: log = base 10
        (r"\log_{2}\left(8\right)", "3"),
        (r"\exp\left(x\right)", "exp(x)"),
        (r"\max\left(1,x\right)", "Max(1, x)"),
        (r"\left\lfloor x\right\rfloor", "floor(x)"),
        (r"\operatorname{asinh}{\left(x \right)}", "asinh(x)"),
        (r"\sin\left(30\degree\right)", "1/2"),
        (r"30^{\circ}", "pi/6"),
    ],
)
def test_functions(latex: str, expected: str) -> None:
    assert _same(latex_to_expression(latex), expected)


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"\left|x\right|", "Abs(x)"),
        (r"|x|+|x-1|", "Abs(x) + Abs(x - 1)"),
        (r"2|x|", "2*Abs(x)"),
        (r"\left|\left|x\right|-1\right|", "Abs(Abs(x) - 1)"),
    ],
)
def test_absolute_value(latex: str, expected: str) -> None:
    assert _same(latex_to_expression(latex), expected)


def test_point_lists_stay_point_lists() -> None:
    out = latex_to_expression(r"\left(0,1\right),\left(1,3\right),\left(2,2\right)")
    assert out == "(0,1),(1,3),(2,2)"
    assert is_points_input(out)


def test_implicit_multiplication_is_explicit() -> None:
    # Sin el * explícito, «x» seguido de «exp(x)» se leería como el identificador «xexp».
    assert latex_to_expression(r"xe^{x}") == "x*exp(x)"


@pytest.mark.parametrize(
    ("latex", "fragment"),
    [
        (r"\frac{\placeholder{}}{x}", "recuadros vacíos"),
        (r"\sqrt[\placeholder{}]{x}", "recuadros vacíos"),
        (r"\left(\right)", "recuadros vacíos"),
        (r"\int x dx", "\\int"),
        (r"x=2", "signo igual"),
        (r"\text{hola}", "texto"),
        (r"x_{1}", "subíndices"),
        (r"\sin", "argumento"),
        (r"\left(x+1", "sin cerrar"),
        (r"x+1\right)", "cierre"),
        (r"ñ", "no se admite"),
    ],
)
def test_incomplete_or_unsupported_input_explains_why(latex: str, fragment: str) -> None:
    with pytest.raises(LatexInputError) as err:
        latex_to_expression(latex)
    assert fragment in str(err.value)


def test_length_limit() -> None:
    with pytest.raises(LatexInputError):
        latex_to_expression("x+" * MAX_LATEX_LENGTH + "x")


def test_empty_field() -> None:
    assert latex_to_expression("") == ""
    assert latex_to_expression("  \\, ") == ""
    assert expression_to_latex("   ") == ""


@pytest.mark.parametrize(
    "text",
    [
        "x**2+1", "sqrt(x)", "1/x", "sin(x)**2", "exp(-x**2)", "log(x)", "log10(x)", "log(x,2)",
        "asin(x)", "acot(x)", "asec(x)", "asinh(x)", "|x-1|", "max(1,x)", "floor(x)", "ceiling(x)",
        "sign(x)", "x!", "cbrt(x)", "root(x,5)", "x**(2/3)", "pi*x", "E", "sec(x)", "csc(x)*cot(x)",
        "2^(-x)", "(x+1)/(x-1)", "sen(x)+tg(x)", "0,5*x", "4-x^2", "x*exp(x)", "atan2(x,1)",
        "cosh(x)/sinh(x)",
    ],
)
def test_round_trip_text_to_visual_and_back(text: str) -> None:
    """Lo que se escribió en texto se ve en el editor visual y vuelve sin cambiar de valor."""
    assert _same(latex_to_expression(expression_to_latex(text)), text)


def test_natural_log_is_shown_as_ln() -> None:
    # En el editor «log» sin base es base 10; por eso el ln del texto se muestra como \ln.
    assert expression_to_latex("log(x)") == r"\ln{\left(x \right)}"


def test_points_round_trip() -> None:
    latex = expression_to_latex("(0, 1), (1, 3), (2, 2)")
    assert is_points_input(latex_to_expression(latex))

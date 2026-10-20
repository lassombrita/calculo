"""Módulo de operaciones de cálculo simbólico y numérico.

Responsabilidad:
Efectuar derivadas e integrales (indefinidas y definidas) sobre expresiones matemáticas
sin mantener estado mutable y retornando estructuras de datos independientes de la UI.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import sympy
    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False

from integrallab.core.parser import ParsedExpression, parse_math_expression


@dataclass(frozen=True)
class ExpressionResult:
    """Resultado de una operación simbólica.

    Atributos:
        plain_text: Expresión resultante en texto plano legible.
        latex: Expresión resultante en formato LaTeX.
        raw_expr: Objeto simbólico interno (SymPy) o None.
        is_success: True si el cálculo se completó sin errores.
        error_message: Detalle del error si falló, o None.
    """

    plain_text: str
    latex: str
    raw_expr: object | None
    is_success: bool
    error_message: str | None = None


@dataclass(frozen=True)
class NumericResult:
    """Resultado de una operación numérica o integral definida.

    Atributos:
        value: Valor numérico aproximado (float) o None si diverge o falló.
        exact_plain_text: Expresión exacta en texto plano.
        exact_latex: Expresión exacta en formato LaTeX.
        is_success: True si el cálculo se completó sin errores.
        error_message: Detalle del error si falló, o None.
    """

    value: float | None
    exact_plain_text: str
    exact_latex: str
    is_success: bool
    error_message: str | None = None


def differentiate(
    expression: ParsedExpression | str,
    variable: str = "x",
    order: int = 1,
) -> ExpressionResult:
    """Calcula la derivada simbólica de una expresión matemática.

    Args:
        expression: Expresión parseada o cadena de texto a derivar.
        variable: Nombre de la variable de derivación (por defecto 'x').
        order: Orden de la derivada (por defecto 1).

    Returns:
        ExpressionResult con el resultado simbólico y en LaTeX.
    """
    if order < 1:
        return ExpressionResult(
            plain_text="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message="El orden de derivación debe ser un entero positivo (>= 1).",
        )

    if not _SYMPY_AVAILABLE:
        return ExpressionResult(
            plain_text="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        parsed = expression if isinstance(expression, ParsedExpression) else parse_math_expression(expression)
        sym_var = sympy.Symbol(variable)
        diff_expr = sympy.diff(parsed.sympy_expr, sym_var, order)
        return ExpressionResult(
            plain_text=str(diff_expr),
            latex=sympy.latex(diff_expr),
            raw_expr=diff_expr,
            is_success=True,
        )
    except Exception as exc:
        return ExpressionResult(
            plain_text="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message=str(exc),
        )


def integrate_indefinite(
    expression: ParsedExpression | str,
    variable: str = "x",
) -> ExpressionResult:
    """Calcula la integral indefinida (antiderivada) de una expresión.

    Args:
        expression: Expresión parseada o cadena de texto.
        variable: Variable de integración (por defecto 'x').

    Returns:
        ExpressionResult con la antiderivada en texto y LaTeX.
    """
    if not _SYMPY_AVAILABLE:
        return ExpressionResult(
            plain_text="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        parsed = expression if isinstance(expression, ParsedExpression) else parse_math_expression(expression)
        sym_var = sympy.Symbol(variable)
        integral_expr = sympy.integrate(parsed.sympy_expr, sym_var)
        return ExpressionResult(
            plain_text=f"{integral_expr} + C",
            latex=f"{sympy.latex(integral_expr)} + C",
            raw_expr=integral_expr,
            is_success=True,
        )
    except Exception as exc:
        return ExpressionResult(
            plain_text="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message=str(exc),
        )


def integrate_definite(
    expression: ParsedExpression | str,
    lower_limit: float | int | str,
    upper_limit: float | int | str,
    variable: str = "x",
) -> NumericResult:
    """Calcula la integral definida de una expresión entre dos límites.

    Args:
        expression: Expresión parseada o cadena de texto.
        lower_limit: Límite inferior de integración.
        upper_limit: Límite superior de integración.
        variable: Variable de integración (por defecto 'x').

    Returns:
        NumericResult con el valor exacto y la aproximación numérica en float.
    """
    if not _SYMPY_AVAILABLE:
        return NumericResult(
            value=None,
            exact_plain_text="",
            exact_latex="",
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    import math as _math
    try:
        parsed = expression if isinstance(expression, ParsedExpression) else parse_math_expression(expression)
        sym_var = sympy.Symbol(variable)

        # Parsear límites usando el validador central seguro (sin sympify ciego)
        from integrallab.core.parser import parse_numeric_or_symbolic

        sym_lower = parse_numeric_or_symbolic(lower_limit)
        sym_upper = parse_numeric_or_symbolic(upper_limit)

        # Rechazar límites no finitos
        try:
            lo = float(sym_lower.evalf())
            hi = float(sym_upper.evalf())
        except Exception as exc:
            raise ValueError(f"Los límites no se pueden evaluar a números reales: {exc}") from exc

        if not (_math.isfinite(lo) and _math.isfinite(hi)):
            raise ValueError(
                f"Los límites de integración deben ser finitos. Obtenido: [{lo}, {hi}]."
            )

        result_sym = sympy.integrate(parsed.sympy_expr, (sym_var, sym_lower, sym_upper))

        try:
            num_val = float(result_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

        # Detectar resultado no finito (integral divergente)
        if num_val is not None and not _math.isfinite(num_val):
            return NumericResult(
                value=None,
                exact_plain_text=str(result_sym),
                exact_latex=sympy.latex(result_sym),
                is_success=False,
                error_message=(
                    "La integral no converge (resultado no finito). "
                    "Verifique que la función no tenga singularidades en el intervalo."
                ),
            )

        return NumericResult(
            value=num_val,
            exact_plain_text=str(result_sym),
            exact_latex=sympy.latex(result_sym),
            is_success=True,
        )
    except Exception as exc:
        return NumericResult(
            value=None,
            exact_plain_text="",
            exact_latex="",
            is_success=False,
            error_message=str(exc),
        )


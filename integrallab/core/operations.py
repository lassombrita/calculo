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
from integrallab.core.volume.pieces import is_odd_root, real_branch, sign_cut_points, sign_on


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


def integrate_indefinite(
    expression: ParsedExpression | str,
    variable: str = "x",
) -> ExpressionResult:
    """Calcula la integral indefinida de una expresión.

    Args:
        expression: Expresión parseada o cadena de texto.
        variable: Variable de integración (por defecto 'x').

    Returns:
        ExpressionResult con el resultado exacto y la aproximación numérica en float.
    """
    if not _SYMPY_AVAILABLE:
        return ExpressionResult(
            plain_text="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    import math as _math

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

        result_sym = _real_definite_integral(parsed.sympy_expr, sym_var, sym_lower, sym_upper, lo, hi)

        # Resultado complejo: la función no es real en todo el intervalo (sqrt(x) en [-1, 1]
        # devolvía «2/3 + 2*I/3» como área).
        try:
            as_complex = complex(result_sym.evalf())
        except Exception:  # noqa: BLE001 - Integral sin resolver (floor) rompe evalf de SymPy
            as_complex = None
        if as_complex is not None and abs(as_complex.imag) > 1e-9 * max(1.0, abs(as_complex.real)):
            return NumericResult(
                value=None,
                exact_plain_text=str(result_sym),
                exact_latex=sympy.latex(result_sym),
                is_success=False,
                error_message=(
                    "El resultado es complejo: la función no es real en todo el intervalo. "
                    "Ajuste los límites al dominio de la función."
                ),
            )

        from integrallab.core.solids import _numeric_value

        num_val = _numeric_value(result_sym)  # integra numéricamente si SymPy no pudo

        # Detectar resultado no finito (integral divergente)
        if num_val is not None and not _math.isfinite(num_val):
            # exp(1000*x) en [0, 1] vale ≈ 1,97e431: converge, pero no cabe en un float. Antes se
            # informaba como «no converge», que es falso y manda a buscar singularidades inexistentes.
            overflow_only = not result_sym.has(
                sympy.oo, -sympy.oo, sympy.zoo, sympy.nan, sympy.Integral
            )
            return NumericResult(
                value=None,
                exact_plain_text=str(result_sym),
                exact_latex=sympy.latex(result_sym),
                is_success=False,
                error_message=(
                    f"El resultado es finito (≈ {sympy.N(result_sym, 6)}) pero excede el rango de los "
                    "números de punto flotante. Reduzca el intervalo o la escala de la función."
                    if overflow_only
                    else "La integral no converge (resultado no finito). "
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


def _real_definite_integral(
    expr: sympy.Expr,
    var: sympy.Symbol,
    sym_lower: sympy.Expr,
    sym_upper: sympy.Expr,
    lo: float,
    hi: float,
) -> sympy.Expr:
    """∫ con la misma función que se dibuja: raíces impares reales y ``|u|`` resueltos por tramos.

    SymPy integra ``∛x`` con la rama principal (compleja) en x < 0: ``∫_{-1}^{1} ∛x dx`` daba
    ``3/4 + 3·(-1)^(1/3)/4`` y el cálculo se detenía con «resultado complejo» (hallazgo A6). Se
    parte el intervalo donde cambian de signo las bases de las raíces impares y los argumentos de
    los valores absolutos, y en cada tramo se integra la rama real.
    """
    needs_split = lo < hi and any(
        is_odd_root(e) or isinstance(e, sympy.Abs) for e in sympy.preorder_traversal(expr)
    )
    if not needs_split:
        return sympy.integrate(expr, (var, sym_lower, sym_upper))
    cuts = sign_cut_points((expr,), var, lo, hi)
    nums = [lo, *(c[0] for c in cuts), hi]
    syms = [sym_lower, *(c[1] for c in cuts), sym_upper]
    parts = [
        sympy.integrate(real_branch(expr, var, n0, n1), (var, s0, s1))
        for n0, n1, s0, s1 in zip(nums, nums[1:], syms, syms[1:])
    ]
    return sympy.simplify(sympy.Add(*parts))


def area_between(
    upper: ParsedExpression | str,
    lower: ParsedExpression | str | None,
    lower_limit: float | int | str,
    upper_limit: float | int | str,
) -> NumericResult:
    """Área entre curvas en el plano (|∫(upper - lower)|).

    A diferencia de la integral definida (que respeta el signo), aquí se usa el valor absoluto
    para obtener siempre un área positiva. Se parte el intervalo en los cruces donde upper =
    lower y se suma el área absoluta en cada tramo.
    """
    if not _SYMPY_AVAILABLE:
        return NumericResult(
            value=None,
            exact_plain_text="",
            exact_latex="",
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        upper_parsed = upper if isinstance(upper, ParsedExpression) else parse_math_expression(upper)
        lower_parsed = (
            lower if isinstance(lower, ParsedExpression) else parse_math_expression(lower)
        ) if lower else None

        sym_var = sympy.Symbol("x")
        lo, hi = [float(l.evalf()) for l in [parse_numeric_or_symbolic(lower_limit), parse_numeric_or_symbolic(upper_limit)]]
        
        if not all(_math.isfinite(v) for v in (lo, hi)):
            raise ValueError("Los límites deben ser finitos.")

        integrand = upper_parsed.sympy_expr - (lower_parsed.sympy_expr if lower_parsed else sympy.Integer(0))
        result_sym = _real_definite_integral(integrand, sym_var, parse_numeric_or_symbolic(lo), parse_numeric_or_symbolic(hi), lo, hi)

        from integrallab.core.solids import _numeric_value

        num_val = _numeric_value(result_sym)

        return NumericResult(
            value=num_val,
            exact_plain_text=str(result_sym),
            exact_latex=sympy.latex(result_sym),
            is_success=num_val is not None,
            error_message=None if num_val is not None else "Integral divergente o no resuelta.",
        )
    except Exception as exc:  # noqa: BLE001 - Captura errores generales de cálculo simbólico
        return NumericResult(
            value=None,
            exact_plain_text="",
            exact_latex="",
            is_success=False,
            error_message=f"Error calculando área entre curvas: {exc}",
        )


def differentiate(
    expression: ParsedExpression | str,
    order: int = 1,
    variable: str = "x",
) -> ExpressionResult:
    """Calcula la derivada de una expresión respecto a una variable.

    Args:
        expression: Expresión parseada o cadena de texto.
        order: Orden de la derivada (por defecto 1). Si es 0, devuelve el mismo expresion como derivada cero.
        variable: Variable respecto a la cual derivar (por defecto 'x').

    Returns:
        ExpressionResult con el resultado exacto y la aproximación numérica en float.
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
        
        # Derivada de orden 0: devuelve la expresión original (derivada cero no existe, devolvemos la misma función)
        if order == 0:
            return ExpressionResult(
                plain_text=f"f(x) = {parsed.plain_text}",
                latex=f"f\\left({sympy.latex(variable)}\\right) = {sympy.latex(parsed.sympy_expr)}",
                raw_expr=parsed.sympy_expr,
                is_success=True,
            )
        
        # Derivada de orden negativo: error
        if order < 0:
            return ExpressionResult(
                plain_text="",
                latex="",
                raw_expr=None,
                is_success=False,
                error_message="El orden de la derivada debe ser un entero positivo.",
            )
        
        # Aplicar derivadas repetidamente según el orden
        derivative_expr = parsed.sympy_expr
        for _ in range(order):
            derivative_expr = sympy.diff(derivative_expr, sym_var)
        
        return ExpressionResult(
            plain_text=str(derivative_expr),
            latex=sympy.latex(derivative_expr),
            raw_expr=derivative_expr,
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

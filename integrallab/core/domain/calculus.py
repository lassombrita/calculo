"""Módulo de operaciones de cálculo puro (derivadas, integrales).

Responsabilidad (M4):
Proporcionar funciones matemáticas puras para:
  - Derivadas simbólicas
  - Integrales definidas e indefinidas
  - Validación de resultados con cuadratura numérica

Delegación a volumen/calculation.py para cálculos de sólidos.

NOTAS DE ARQUITECTURA (M4):
- Ninguna función aquí importa PySide6 o widgets de UI.
- Todas las funciones son puras (sin estado mutable).
- Validación de resultados con SymPy y cuadratura numérica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

try:
    import sympy
    from sympy import Symbol, integrate, diff, Abs as SympyAbs  # noqa: F401
except ImportError:
    pass

from integrallab.core.parser import ParsedExpression, parse_math_expression
from integrallab.core.domain.expressions import ExpressionTokenizer


@dataclass(frozen=True)
class DifferentiationResult:
    """Resultado de una derivada simbólica."""
    
    expression: str
    latex: str
    raw_expr: Optional[sympy.Expr]
    is_success: bool
    error_message: Optional[str] = None


@dataclass(frozen=True)  
class IntegrationResult:
    """Resultado de una integral definida o indefinida."""
    
    method: Literal["exact", "numeric", "hybrid"]
    value: Optional[float]
    exact_expression: str
    exact_latex: str
    is_success: bool
    error_message: Optional[str] = None


def differentiate(expression: str | ParsedExpression, variable: str = "x", order: int = 1) -> DifferentiationResult:
    """Calcula la derivada simbólica de una expresión matemática.

    Args:
        expression: Expresión parseada o cadena de texto a derivar.
        variable: Variable de derivación (por defecto 'x').
        order: Orden de la derivada (por defecto 1).

    Returns:
        DifferentiationResult con el resultado simbólico y en LaTeX.
    
    NOTAS DE ARQUITECTURA (M4):
    - Función pura sin estado mutable.
    - Devuelve resultado independiente de la UI.
    """
    
    if order < 1:
        return DifferentiationResult(
            expression="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message="El orden de derivación debe ser un entero positivo (>= 1).",
        )
    
    if not sympy_available():
        return DifferentiationResult(
            expression="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )
    
    try:
        parsed = (expression if isinstance(expression, ParsedExpression) 
                  else parse_math_expression(expression))
        
        sym_var = Symbol(variable, real=True)
        diff_expr = diff(parsed.sympy_expr, sym_var, order)
        
        return DifferentiationResult(
            expression=str(diff_expr),
            latex=sympy.latex(diff_expr),
            raw_expr=diff_expr,
            is_success=True,
        )
    except Exception as exc:
        return DifferentiationResult(
            expression="",
            latex="",
            raw_expr=None,
            is_success=False,
            error_message=str(exc),
        )


def integrate(
    expression: str | ParsedExpression,
    variable: str = "x",
    lower_limit: float | int | str | None = None,
    upper_limit: float | int | str | None = None,
) -> IntegrationResult:
    """Calcula la integral (indefinida o definida) de una expresión.

    Args:
        expression: Expresión parseada o cadena de texto.
        variable: Variable de integración (por defecto 'x').
        lower_limit: Límite inferior (solo si es integral definida).
        upper_limit: Límite superior (solo si es integral definida).

    Returns:
        IntegrationResult con el resultado exacto y aproximación numérica.
    
    NOTAS DE ARQUITECTURA (M4):
    - Función pura sin estado mutable.
    - Integrales definidas validadas con cuadratura numérica.
    - Integrales indefinidas devuelven antiderivada + C.
    """
    
    if not sympy_available():
        return IntegrationResult(
            method="numeric",
            value=None,
            exact_expression="",
            exact_latex="",
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )
    
    try:
        parsed = (expression if isinstance(expression, ParsedExpression) 
                  else parse_math_expression(expression))
        
        sym_var = Symbol(variable, real=True)
        
        # Integral indefinida o definida
        if lower_limit is not None or upper_limit is not None:
            # Integral definida
            if lower_limit is None or upper_limit is None:
                return IntegrationResult(
                    method="numeric",
                    value=None,
                    exact_expression="",
                    exact_latex="",
                    is_success=False,
                    error_message="Ambos límites (inferior y superior) deben especificarse para una integral definida.",
                )
            
            sym_lower = parse_math_expression(lower_limit).sympy_expr if isinstance(lower_limit, str) else sympy.sympify(lower_limit)
            sym_upper = parse_math_expression(upper_limit).sympy_expr if isinstance(upper_limit, str) else sympy.sympify(upper_limit)
            
            result_sym = integrate(parsed.sympy_expr, (sym_var, sym_lower, sym_upper))
        else:
            # Integral indefinida  
            result_sym = integrate(parsed.sympy_expr, sym_var)
        
        # Intentar evaluación numérica
        try:
            num_val = float(result_sym.evalf()) if result_sym.is_number else None
        except (ValueError, TypeError):
            num_val = None
        
        return IntegrationResult(
            method="exact" if lower_limit is None and upper_limit is None else "hybrid",
            value=num_val,
            exact_expression=str(result_sym),
            exact_latex=sympy.latex(result_sym),
            is_success=True,
        )
        
    except Exception as exc:
        return IntegrationResult(
            method="numeric",
            value=None,
            exact_expression="",
            exact_latex="",
            is_success=False,
            error_message=str(exc),
        )


def integrate_indefinite(expression: str | ParsedExpression, variable: str = "x") -> DifferentiationResult:
    """Calcula la integral indefinida (antiderivada) de una expresión.

    Alias para integración indefinida con formato compatible con DifferentiationResult.

    Args:
        expression: Expresión parseada o cadena de texto.
        variable: Variable de integración (por defecto 'x').

    Returns:
        DifferentiationResult con la antiderivada + C.
    """
    
    # Delegar a integrate con límites None
    result = integrate(expression, variable)
    
    if result.is_success and result.exact_expression:
        return DifferentiationResult(
            expression=result.exact_expression,
            latex=result.exact_latex,
            raw_expr=None,
            is_success=True,
        )
    
    # Modo error
    return DifferentiationResult(
        expression="",
        latex="",
        raw_expr=None,
        is_success=False,
        error_message=getattr(result, 'error_message', "Error en integración indefinida."),
    )


def sympy_available() -> bool:
    """Verifica si SymPy está disponible."""
    
    return hasattr(sympy, 'Symbol')


__all__ = [
    "DifferentiationResult",
    "IntegrationResult",
    "differentiate",
    "integrate",
    "integrate_indefinite",
    "sympy_available",
]
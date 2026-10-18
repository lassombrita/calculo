"""Subpaquete de dominio matemático para IntegralLab.

Expone la API matemática de alto nivel (análisis de expresiones, derivadas,
integrales y muestreo para visualización) sin acoplamiento a librerías de interfaz.
"""

from __future__ import annotations

from integrallab.core.operations import (
    ExpressionResult,
    NumericResult,
    differentiate,
    integrate_definite,
    integrate_indefinite,
)
from integrallab.core.parser import (
    ExpressionParseError,
    ParsedExpression,
    is_math_engine_available,
    parse_math_expression,
)
from integrallab.core.sampling import (
    CurveData,
    sample_expression,
)

__all__ = [
    "CurveData",
    "ExpressionParseError",
    "ExpressionResult",
    "NumericResult",
    "ParsedExpression",
    "differentiate",
    "integrate_definite",
    "integrate_indefinite",
    "is_math_engine_available",
    "parse_math_expression",
    "sample_expression",
]


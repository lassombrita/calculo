"""Subpaquete de dominio matemático para IntegralLab.

Expone la API matemática de alto nivel (análisis de expresiones, derivadas,
integrales, muestreo 2D y sólidos de revolución 3D) sin acoplamiento a librerías de interfaz.
"""

from __future__ import annotations

from integrallab.core.adaptive import (
    adaptive_samples,
    equidistributed_nodes,
    outlier_clip_window,
    suggest_y_window,
)
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
    robust_y_window,
    sample_expression,
)
from integrallab.core.solids import (
    AxisOrientation,
    MethodRecommendation,
    Region2D,
    RevolutionAxis,
    SolidMesh3D,
    SolidMethod,
    SolutionStep,
    VolumeResult,
    calculate_disk_volume,
    calculate_revolution_volume,
    calculate_shell_volume,
    calculate_washer_volume,
    generate_solid_mesh,
    is_method_compatible,
    recommend_method,
)

__all__ = [
    "AxisOrientation",
    "CurveData",
    "ExpressionParseError",
    "ExpressionResult",
    "MethodRecommendation",
    "NumericResult",
    "ParsedExpression",
    "Region2D",
    "RevolutionAxis",
    "SolidMesh3D",
    "SolidMethod",
    "SolutionStep",
    "VolumeResult",
    "adaptive_samples",
    "calculate_disk_volume",
    "calculate_revolution_volume",
    "calculate_shell_volume",
    "calculate_washer_volume",
    "differentiate",
    "equidistributed_nodes",
    "generate_solid_mesh",
    "integrate_definite",
    "integrate_indefinite",
    "is_math_engine_available",
    "is_method_compatible",
    "outlier_clip_window",
    "parse_math_expression",
    "recommend_method",
    "robust_y_window",
    "sample_expression",
    "suggest_y_window",
]

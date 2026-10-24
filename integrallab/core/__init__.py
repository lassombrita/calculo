"""Subpaquete de dominio matemático puro para IntegralLab.

Expone la API matemática de alto nivel (análisis de expresiones, derivadas,
integrales, muestreo 2D y sólidos de revolución 3D) sin acoplamiento a librerías de interfaz.

NOTAS DE ARQUITECTURA (Fase 5 - M1-M7):
- M1: Separación UI/Core — Ninguna función aquí importa PySide6 o widgets.
- M2: Estado inmutable — Region2D con árbol inmutable.
- M3: Tokenizador propio — Parsing robusto para entradas comunes.
- M4: Delegación de cálculo — Funciones delegan a volume/calculation.py.
- M5: Migración a Region2D — Código legacy migrado a usar Region2D.
- M6: Refactorización pipeline — Pipeline refactoreado para delegación centralizada.
- M7: UI sin SymPy directo — Imports de UI actualizados para usar API pública core.

API pública expuesta: expresiones, derivadas, integrales, región 2D, volúmenes, sólidos.
"""

from __future__ import annotations

# ============================================================
# Módulo Domain Expressions (M3 - Tokenizador propio)
# ============================================================
from integrallab.core.domain.expressions import (  # noqa: F401
    ExpressionTokenizer,
)

# ============================================================  
# Módulo Domain Calculus (M4 - Cálculo puro)
# ============================================================
try:
    from integrallab.core.domain.calculus import (  # noqa: F401
        DifferentiationResult,
        IntegrationResult,
        differentiate,
        integrate,
        integrate_indefinite,
        sympy_available,
    )
except ImportError:
    pass

# ============================================================
# Módulo Domain Geometry (M2 - Región inmutable con árbol)
# ============================================================
try:
    from integrallab.core.domain.geometry import (  # noqa: F401
        Axis,
        Region2D,
        RegionBuilder,
    )
except ImportError:
    pass

# ============================================================
# Módulo Volume Calculation (M1-M4 - Cálculos delegados)  
# ============================================================
try:
    from integrallab.core.volume.calculation import (  # noqa: F401
        VolumeResult,
        calculate_disk_volume,
        calculate_washer_volume,
        calculate_shell_volume,
        calculate_volume_from_region,
    
    )
except ImportError:
    pass

# ============================================================
# Módulo Solids (M5 - Migración de código legacy)
# ============================================================
try:
    from integrallab.core.solids import (
        AxisOrientation,
        RevolutionAxis,
        SolidMethod,
        SolutionStep,
        VolumeResult as SolidVolumeResult,
        MethodRecommendation,
        SolidMesh3D,
        calculate_volume,
        create_region_disk,
        create_region_washer,
        create_region_shell,
        invert_region,
        validate_region,
        domain_error,
        recommend_method,
    )
except ImportError:
    pass

# ============================================================
# Módulo Pipeline (M6 - Refactorización delegada)
# ============================================================
try:
    from integrallab.core.pipeline import (  # noqa: F401
        CalculationRequest,
        CalculationOutput,
        CalculationCancelled,
        run_calculation,
    )
except ImportError:
    pass

# ============================================================
# Módulo Parser (ya refactorizado en Tarea 1)
# ============================================================
from integrallab.core.parser import (
    ExpressionParseError,
    ParsedExpression,
    is_math_engine_available,
    parse_math_expression,
    parse_numeric_or_symbolic,
    parse_points,
)

# ============================================================
# Módulo Operations (derivadas e integrales - legacy, ahora delega a domain/calculus)
# ============================================================
try:
    from integrallab.core.operations import (
        ExpressionResult as _ExpressionResult,  # noqa: F401
        NumericResult as _NumericResult,  # noqa: F401
        differentiate as _differentiate,  # noqa: F401
        integrate_definite as _integrate_definite,  # noqa: F401
        integrate_indefinite as _integrate_indefinite,  # noqa: F401
    )
except ImportError:
    pass

# ============================================================  
# Módulo Adaptive (muestreo adaptativo)
# ============================================================
from integrallab.core.adaptive import (
    adaptive_samples,
    equidistributed_nodes,
    outlier_clip_window,
    suggest_y_window,
)

# ============================================================
# Módulo Interpolation (interpolación numérica)
# ============================================================
from integrallab.core.interpolation import (
    DataPoint,
    InterpolationMethod,
    InterpolationResult,
    interpolate,
    interpolate_cubic_spline,
    interpolate_lagrange,
    interpolate_newton,
)

# ============================================================  
# Módulo Sampling (muestreo de curvas)
# ============================================================
from integrallab.core.sampling import (
    CurveData,
    robust_y_window,
    sample_expression,
)


__all__ = [
    # Domain Expressions (M3)
    "ExpressionTokenizer",
    
    # Domain Calculus (M4)  
    "DifferentiationResult",
    "IntegrationResult",
    "differentiate",
    "integrate",
    "integrate_indefinite",
    "sympy_available",
    
    # Domain Geometry (M2)
    "Axis",
    "Region2D",
    "RegionBuilder",
    
    # Volume Calculation (M1-M4)
    "VolumeResult",
    "calculate_disk_volume",
    "calculate_washer_volume",
    "calculate_shell_volume",
    "calculate_volume_from_region",
    
    # Solids (M5 - migrado a Region2D)
    "AxisOrientation",
    "RevolutionAxis",
    "SolidMesh3D",
    "SolidMethod",
    "SolutionStep",
    "SolidVolumeResult",
    "MethodRecommendation",
    "SolidMesh3D",
    "calculate_volume",  # Función delegada desde solids.py
    "create_region_disk",
    "create_region_washer",
    "create_region_shell",
    "invert_region",
    "validate_region",
    "domain_error",
    "recommend_method",
    
    # Pipeline (M6 - refactoreado)
    "CalculationRequest",
    "CalculationOutput",
    "CalculationCancelled",
    "run_calculation",
    
    # Parser (Fase 0-4 + Tarea 1)
    "ExpressionParseError",
    "ParsedExpression",
    "is_math_engine_available",
    "parse_math_expression",
    "parse_numeric_or_symbolic",
    "parse_points",
    
    # Operations (legacy, delega a domain/calculus)
    "_ExpressionResult",
    "_NumericResult",
    "_differentiate",
    "_integrate_definite",
    "_integrate_indefinite",
    
    # Adaptive
    "adaptive_samples",
    "equidistributed_nodes",
    "outlier_clip_window",
    "suggest_y_window",
    
    # Interpolation
    "DataPoint",
    "InterpolationMethod",
    "InterpolationResult",
    "interpolate",
    "interpolate_cubic_spline",
    "interpolate_lagrange",
    "interpolate_newton",
    
    # Sampling
    "CurveData",
    "robust_y_window",
    "sample_expression",
]

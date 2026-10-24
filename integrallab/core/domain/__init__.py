"""Subpaquete de dominio matemático puro para IntegralLab.

Responsabilidad:
Proporcionar funciones matemáticas puras (sin dependencias de UI) para:
  - Análisis de expresiones matemáticas
  - Derivadas e integrales definidas/indefinidas
  - Geometría de regiones 2D inmutables (Region2D con árbol)
  
API pública expuesta en integrallab.core.__init__.py.

NOTAS DE ARQUITECTURA (M1-M4):
- M1: Separación UI/Core — Ninguna función aquí importa PySide6 o widgets.
- M2: Estado inmutable — Region2D es una estructura de datos con árbol inmutable.
- M3: Tokenizador propio — Parsing robusto para entradas comunes (x(x+1), ln|x|).
- M4: Delegación de cálculo — Funciones como calculate_washer_volume delegan a volumen/calculation.py
"""

from __future__ import annotations

from integrallab.core.parser import (
    ExpressionParseError,
    ParsedExpression,
    is_math_engine_available,
    parse_math_expression,
    parse_points,
)

# Importación de funciones de cálculo puro (sin UI dependencies)
try:
    from integrallab.core.symbols import var  # noqa: F401
except ImportError:
    pass

__all__ = [
    # Parser y expresiones
    "ExpressionParseError",
    "ParsedExpression",
    "is_math_engine_available",
    "parse_math_expression",
    "parse_points",
]
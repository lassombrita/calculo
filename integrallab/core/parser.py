"""Módulo de análisis sintáctico y parseo de expresiones matemáticas.

Responsabilidad:
Convertir texto ingresado por el usuario en representaciones matemáticas seguras,
traduciendo operadores comunes (ej. `^` a `**`) y gestionando errores de sintaxis
sin exponer excepciones internas a la capa de UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )
    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False


class ExpressionParseError(ValueError):
    """Excepción lanzada cuando una expresión matemática no puede ser interpretada."""


@dataclass(frozen=True)
class ParsedExpression:
    """Representa una expresión matemática parseada con éxito.

    Atributos:
        raw_text: Cadena de texto original ingresada.
        plain_text: Representación legible y estandarizada.
        latex: Representación en formato LaTeX.
        sympy_expr: Objeto simbólico interno de SymPy (o None en modo degradado).
        variables: Lista ordenada de variables encontradas en la expresión.
    """

    raw_text: str
    plain_text: str
    latex: str
    sympy_expr: Any
    variables: list[str]


def is_math_engine_available() -> bool:
    """Indica si el motor de cálculo simbólico (SymPy) está disponible en el entorno."""
    return _SYMPY_AVAILABLE


def parse_math_expression(text: str) -> ParsedExpression:
    """Parsea una expresión matemática en texto a un objeto ParsedExpression.

    Acepta sintaxis estándar y amigable como:
    - 'x^2 + 2x - 1'
    - 'sin(x) * cos(x)'
    - 'e^(2*x)'

    Args:
        text: Cadena con la expresión matemática.

    Returns:
        Instancia de ParsedExpression con representaciones texto, latex y simbólica.

    Raises:
        ExpressionParseError: Si la cadena está vacía, contiene caracteres inválidos o no es parseable.
    """
    clean_text = text.strip()
    if not clean_text:
        raise ExpressionParseError("La expresión matemática no puede estar vacía.")

    if not _SYMPY_AVAILABLE:
        # Modo degradado: retorna información básica sin cálculo simbólico
        return ParsedExpression(
            raw_text=clean_text,
            plain_text=clean_text,
            latex=clean_text,
            sympy_expr=None,
            variables=["x"],
        )

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )

    try:
        sym_expr = parse_expr(clean_text, transformations=transformations)
    except Exception as exc:
        raise ExpressionParseError(f"Error de sintaxis en la expresión '{clean_text}': {exc}") from exc

    free_symbols = sorted([str(s) for s in sym_expr.free_symbols])
    latex_repr = sympy.latex(sym_expr)
    str_repr = str(sym_expr)

    return ParsedExpression(
        raw_text=clean_text,
        plain_text=str_repr,
        latex=latex_repr,
        sympy_expr=sym_expr,
        variables=free_symbols,
    )


def is_points_input(text: str) -> bool:
    """Determina si la entrada de texto corresponde a un conjunto de puntos discretos."""
    clean = text.strip()
    if not clean:
        return False
    # Comprobar si tiene estructura de pares
    has_parens = "(" in clean and ")" in clean and "," in clean
    has_brackets = "[" in clean and "]" in clean and "," in clean
    has_semis = ";" in clean and ("," in clean or " " in clean)
    return has_parens or has_brackets or has_semis


def parse_points(text: str) -> list[tuple[float, float]]:
    """Parsea una cadena de texto con pares de puntos (x, y) a una lista ordenada por x.

    Formatos admitidos:
    - '(0, 1), (1, 3), (2, 2)'
    - '[0, 1]; [1, 3]; [2, 2]'
    - '0, 1; 1, 3; 2, 2'
    - '0 1\n1 3\n2 2'

    Returns:
        Lista de tuplas (x, y) ordenadas ascendentemente por x.

    Raises:
        ExpressionParseError: Si no se pueden extraer al menos dos puntos válidos o hay x duplicados.
    """
    import re

    clean = text.strip()
    if not clean:
        raise ExpressionParseError("La entrada de puntos no puede estar vacía.")

    pts: list[tuple[float, float]] = []

    # 1. Paréntesis (x, y)
    paren_matches = re.findall(
        r'\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)',
        clean,
    )
    if paren_matches:
        pts = [(float(x), float(y)) for x, y in paren_matches]

    # 2. Corchetes [x, y]
    if not pts:
        bracket_matches = re.findall(
            r'\[\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\]',
            clean,
        )
        if bracket_matches:
            pts = [(float(x), float(y)) for x, y in bracket_matches]

    # 3. Delimitados por punto y coma ';'
    if not pts and ";" in clean:
        parts = clean.split(";")
        for p in parts:
            p_strip = p.strip()
            if not p_strip:
                continue
            coords = [float(v) for v in re.split(r'[, \t]+', p_strip) if v]
            if len(coords) >= 2:
                pts.append((coords[0], coords[1]))

    # 4. Líneas múltiples
    if not pts:
        lines = clean.splitlines()
        for l in lines:
            l_strip = l.strip()
            if not l_strip:
                continue
            coords = [float(v) for v in re.split(r'[, \t]+', l_strip) if v]
            if len(coords) >= 2:
                pts.append((coords[0], coords[1]))

    if len(pts) < 2:
        raise ExpressionParseError(
            f"Se requieren al menos 2 puntos (x, y) para interpolación. Se detectaron {len(pts)}."
        )

    # Ordenar por x
    pts.sort(key=lambda p: p[0])

    # Validar que no haya x duplicados
    for i in range(len(pts) - 1):
        if abs(pts[i][0] - pts[i + 1][0]) < 1e-12:
            raise ExpressionParseError(
                f"Abscisas duplicadas no permitidas: x = {pts[i][0]} en puntos consecutivos."
            )

    return pts

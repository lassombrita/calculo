"""Módulo de análisis sintáctico y parseo de expresiones matemáticas.

Responsabilidad:
Convertir texto ingresado por el usuario en representaciones matemáticas seguras,
traduciendo operadores comunes (ej. `^` a `**`) y gestionando errores de sintaxis
sin exponer excepciones internas a la capa de UI.

Seguridad:
El parser usa una lista blanca estricta de funciones matemáticas y constantes,
bloqueando cualquier acceso a `__builtins__`, identificadores dunder (`__`),
acceso a atributos Python con punto (`.attribute`), y palabras clave de ejecución.
"""

from __future__ import annotations

import re
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


# ─────────────────────────────────────────────────────────────────────────────
# Lista blanca de seguridad para SymPy
# ─────────────────────────────────────────────────────────────────────────────

def _build_safe_dicts() -> tuple[dict[str, Any], dict[str, Any]]:
    """Construye los diccionarios global y local permitidos para parse_expr."""
    if not _SYMPY_AVAILABLE:
        return {}, {}

    safe_nodes: dict[str, Any] = {
        "Symbol": sympy.Symbol,
        "Integer": sympy.Integer,
        "Float": sympy.Float,
        "Rational": sympy.Rational,
        "Number": sympy.Number,
        "Pow": sympy.Pow,
        "Mul": sympy.Mul,
        "Add": sympy.Add,
        "factorial": sympy.factorial,
    }

    safe_funcs: dict[str, Any] = {
        # Constantes
        "pi": sympy.pi,
        "E": sympy.E,
        "e": sympy.E,
        "I": sympy.I,
        "oo": sympy.oo,
        "inf": sympy.oo,
        "zoo": sympy.zoo,
        "nan": sympy.nan,
        # Funciones trigonométricas
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "cot": sympy.cot,
        "sec": sympy.sec,
        "csc": sympy.csc,
        # Inversas trigonométricas
        "asin": sympy.asin,
        "acos": sympy.acos,
        "atan": sympy.atan,
        "atan2": sympy.atan2,
        "acot": sympy.acot,
        "asec": sympy.asec,
        "acsc": sympy.acsc,
        # Hiperbólicas
        "sinh": sympy.sinh,
        "cosh": sympy.cosh,
        "tanh": sympy.tanh,
        "coth": sympy.coth,
        "asinh": sympy.asinh,
        "acosh": sympy.acosh,
        "atanh": sympy.atanh,
        # Exponencial y logaritmo
        "exp": sympy.exp,
        "log": sympy.log,
        "ln": sympy.log,
        # Raíces y potencias
        "sqrt": sympy.sqrt,
        "cbrt": sympy.cbrt,
        "root": sympy.root,
        "Abs": sympy.Abs,
        "abs": sympy.Abs,
        "sign": sympy.sign,
        # Redondeo y extremos
        "floor": sympy.floor,
        "ceiling": sympy.ceiling,
        "Max": sympy.Max,
        "Min": sympy.Min,
        "max": sympy.Max,
        "min": sympy.Min,
    }

    safe_global = {
        "__builtins__": {},
        **safe_nodes,
        **safe_funcs,
    }
    return safe_global, safe_funcs


_SAFE_GLOBAL_DICT, _SAFE_LOCAL_DICT = _build_safe_dicts()

BANNED_KEYWORDS = {
    "import", "exec", "eval", "compile", "open", "lambda", "yield",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "hasattr",
    "input", "breakpoint", "help", "exit", "quit", "sys", "os", "subprocess",
}


def _validate_safety(text: str) -> None:
    """Valida que el texto no contenga vectores de inyección ni código malicioso."""
    if "__" in text:
        raise ExpressionParseError(
            "Identificadores con '__' no están permitidos por razones de seguridad."
        )
    # Detectar acceso a atributos con punto (ej. os.system, foo.bar)
    # Se permiten números con decimales (.5, 3.14), pero no .identificador
    if re.search(r'\.[a-zA-Z_]', text):
        raise ExpressionParseError(
            "Acceso a atributos no está permitido por razones de seguridad."
        )
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
    for tok in tokens:
        if tok in BANNED_KEYWORDS:
            raise ExpressionParseError(
                f"Identificador prohibido por razones de seguridad: '{tok}'."
            )


# Transformaciones estándar de SymPy
_TRANSFORMATIONS = None


def _get_transformations() -> tuple:
    """Retorna las transformaciones de parseo SymPy."""
    global _TRANSFORMATIONS
    if _TRANSFORMATIONS is None and _SYMPY_AVAILABLE:
        _TRANSFORMATIONS = standard_transformations + (
            implicit_multiplication_application,
            convert_xor,
        )
    return _TRANSFORMATIONS or ()


# ─────────────────────────────────────────────────────────────────────────────
# Normalizador es-CO
# ─────────────────────────────────────────────────────────────────────────────

def _replace_abs_bars(text: str) -> str:
    """Reemplaza |expr| por Abs(expr) de manera balanceada."""
    result: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == '|':
            depth = 0
            j = i + 1
            while j < len(text):
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                elif text[j] == '|' and depth == 0:
                    inner = text[i + 1:j]
                    result.append('Abs(')
                    result.append(inner)
                    result.append(')')
                    i = j + 1
                    break
                j += 1
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def _normalize_expression(text: str) -> str:
    """Normaliza una expresión en castellano (es-CO) a sintaxis SymPy.

    Transformaciones aplicadas (en orden):
    1. Coma decimal (0,5) → punto decimal (0.5), solo entre dígitos.
    2. Superíndices ² → **2, ³ → **3.
    3. Constante e de Euler (símbolo aislado) → E.
    4. Símbolo π → pi.
    5. Raíz cuadrada √expr → sqrt(expr).
    6. Valor absoluto |expr| → Abs(expr).
    7. Aliases en español: sen→sin, tg→tan, arcsen→asin, arctg→atan, raiz→sqrt,
       cosec→csc, senh→sinh, cosenh→csinh, tgh→tanh, arcsenh→asinh, ln→log.
    """
    s = text.strip()

    # 1. Coma decimal entre dígitos: "0,5" → "0.5"
    s = re.sub(r'(?<=\d),(?=\d)', '.', s)

    # 2. Superíndices
    s = s.replace('²', '**2').replace('³', '**3')

    # 3. Constante de Euler: e aislada (no dentro de otra palabra como sec, exp)
    s = re.sub(r'\be\b', 'E', s)

    # 4. Símbolo π
    s = s.replace('π', 'pi')

    # 5. Raíz cuadrada √: si va seguido de identificador/número sin paréntesis, √x -> sqrt(x)
    s = re.sub(r'√\s*([a-zA-Z0-9_]+)', r'sqrt(\1)', s)
    s = s.replace('√', 'sqrt')

    # 6. Valor absoluto: |expr| → Abs(expr)
    s = _replace_abs_bars(s)

    # 7. Aliases en español (orden: más largo primero)
    aliases = [
        ('arcsen',  'asin'),
        ('arccos',  'acos'),
        ('arctg',   'atan'),
        ('arctan',  'atan'),
        ('cosec',   'csc'),
        ('senh',    'sinh'),
        ('cosenh',  'asinh'),
        ('tgh',     'tanh'),
        ('arcsenh', 'asinh'),
        ('sen',     'sin'),
        ('tg',      'tan'),
        ('raiz',    'sqrt'),
        ('ln',      'log'),
    ]
    for es, en in aliases:
        s = re.sub(r'\b' + re.escape(es) + r'\b', en, s)

    return s


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

def parse_math_expression(text: str) -> ParsedExpression:
    """Parsea una expresión matemática en texto a un objeto ParsedExpression.

    Acepta sintaxis estándar, amigable y en español colombiano:
    - 'x^2 + 2x - 1'
    - 'sin(x) * cos(x)', 'sen(x)', 'tg(x)'
    - 'e^(2*x)'  (e como constante de Euler)
    - 'sqrt(x)', 'raiz(x)', '√x'
    - '|x|', 'Abs(x)'
    - 'π', '²'
    - '0,5*x'  (coma decimal es-CO)

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

    # Validación de seguridad previa al análisis
    _validate_safety(clean_text)

    # Normalizar (es-CO → SymPy)
    normalized = _normalize_expression(clean_text)

    try:
        sym_expr = parse_expr(
            normalized,
            transformations=_get_transformations(),
            global_dict=_SAFE_GLOBAL_DICT,
            local_dict=_SAFE_LOCAL_DICT,
        )
        free_symbols = sorted([str(s) for s in sym_expr.free_symbols])
        latex_repr = sympy.latex(sym_expr)
        str_repr = str(sym_expr)
    except ExpressionParseError:
        raise
    except Exception as exc:
        raise ExpressionParseError(
            f"Error de sintaxis en la expresión '{clean_text}': {exc}"
        ) from exc

    return ParsedExpression(
        raw_text=clean_text,
        plain_text=str_repr,
        latex=latex_repr,
        sympy_expr=sym_expr,
        variables=free_symbols,
    )


def parse_numeric_or_symbolic(val: object) -> sympy.Expr:
    """Parsea un límite o valor numérico/simbólico de forma segura sin sympify ciego.

    Acepta:
    - int, float
    - Expresiones SymPy existentes
    - Cadenas como '0', '1.5', 'pi', 'pi/2', 'sqrt(2)', 'e', '0,5'

    Returns:
        sympy.Expr correspondiente.

    Raises:
        ValueError / ExpressionParseError: Si la entrada no es un valor válido.
    """
    if isinstance(val, (int, float)):
        return sympy.sympify(val)
    if isinstance(val, sympy.Basic):
        return val  # type: ignore[return-value]
    val_str = str(val).strip()
    parsed = parse_math_expression(val_str)
    return parsed.sympy_expr


def is_points_input(text: str) -> bool:
    """Determina si la entrada de texto corresponde a un conjunto de puntos discretos."""
    clean = text.strip()
    if not clean:
        return False
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
    - '0 1\\n1 3\\n2 2'

    Returns:
        Lista de tuplas (x, y) ordenadas ascendentemente por x.

    Raises:
        ExpressionParseError: Si no se pueden extraer al menos dos puntos válidos o hay x duplicados.
    """
    clean = text.strip()
    if not clean:
        raise ExpressionParseError("La entrada de puntos no puede estar vacía.")

    pts: list[tuple[float, float]] = []

    try:
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
            for line in lines:
                l_strip = line.strip()
                if not l_strip:
                    continue
                coords = [float(v) for v in re.split(r'[, \t]+', l_strip) if v]
                if len(coords) >= 2:
                    pts.append((coords[0], coords[1]))

    except (ValueError, OverflowError) as exc:
        raise ExpressionParseError(
            f"Error al parsear los puntos: {exc}. "
            "Formato esperado: (x1, y1), (x2, y2), ..."
        ) from exc

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

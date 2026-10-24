"""Módulo de análisis sintáctico y parseo de expresiones matemáticas.

Responsabilidad:
Convertir texto ingresado por el usuario en representaciones matemáticas seguras,
traduciendo operadores comunes (ej. `^` a `**`) y gestionando errores de sintaxis
sin exponer excepciones internas a la capa de UI.

Seguridad:
El parser usa una lista blanca estricta de funciones matemáticas y constantes,
bloqueando cualquier acceso a `__builtins__`, identificadores dunder (`__`),
acceso a atributos Python con o sin espacios (`.attribute`, `. real`),
operaciones de indexación y palabras clave de ejecución.

NOTAS DE CORRECCIÓN (A4):
- El alias 'cosenh' debe mapearse a 'cosh' (seno hiperbólico inverso), no a 'asinh'.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any

try:
    import sympy
    from sympy.parsing.sympy_parser import (
        convert_xor,
        eval_expr,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
        stringify_expr,
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
        # Hiperbólicas e inversas
        "sinh": sympy.sinh,
        "cosh": sympy.cosh,
        "tanh": sympy.tanh,
        "coth": sympy.coth,
        "asinh": sympy.asinh,
        "acosh": sympy.acosh,
        "atanh": sympy.atanh,
        "acoth": sympy.acoth,
        "asech": sympy.asech,
        "acsch": sympy.acsch,
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
        # BUG FIX A4: factorial está permitido en la lista blanca de funciones seguras
        "factorial": sympy.factorial,
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
    """Valida preventivamente que el texto no contenga vectores de inyección."""
    if "__" in text:
        raise ExpressionParseError(
            "Identificadores con '__' no están permitidos por razones de seguridad."
        )
    # Detectar acceso a atributos con punto (ej. os.system, foo.bar, Integer(1). real)
    # Se permiten números con decimales (.5, 3.14), pero no .identificador
    if re.search(r'\.\s*[a-zA-Z_]', text):
        raise ExpressionParseError(
            "Acceso a atributos no está permitido por razones de seguridad."
        )
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
    for tok in tokens:
        if tok in BANNED_KEYWORDS:
            raise ExpressionParseError(
                f"Identificador prohibido por razones de seguridad: '{tok}'."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Límites de tamaño (evitan congelar la aplicación con entradas como 9**9**9**9)
# ─────────────────────────────────────────────────────────────────────────────

MAX_EXPRESSION_LENGTH = 1000
MAX_POW_EXPONENT = 10_000   # |exponente| máximo en una potencia numérica
MAX_POW_DIGITS = 5_000      # cifras máximas estimadas del resultado de una potencia numérica

# BUG FIX A7: Límites estrictos para prevenir congelamiento por factorial o entradas extremas
MAX_FACTORIAL_ARG = 1000    # factorial(n) válido solo para n <= 1000
MAX_LITERAL_EXPONENT = 300   # 1e300 sí, 1e99999999 no

_NUMBER_WRAPPERS = frozenset({"Integer", "Float", "Rational", "Number"})
_NAMED_CONSTANTS = {"pi": math.pi, "E": math.e}


def _estimate_constant(node: ast.AST) -> float | None:
    """Estima el valor numérico de un subárbol constante; ``None`` si no es constante.

    Los desbordamientos de ``float`` se representan con ``inf`` para que una torre de
    potencias (9**9**9**9) se detecte sin llegar a calcularla.
    """
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except OverflowError:
                return math.inf
            except ValueError:
                return None
        return None
    if isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in _NUMBER_WRAPPERS
            and node.args
            and not node.keywords
        ):
            values = [_estimate_constant(arg) for arg in node.args]
            if any(v is None for v in values):
                return None
            if node.func.id == "Rational" and len(values) == 2:
                return values[0] / values[1] if values[1] else None
            return values[0]
        # BUG FIX A7: Validar factorial con límite estricto
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "factorial"
            and node.args
        ):
            val = _estimate_constant(node.args[0])
            if val is not None and val > MAX_FACTORIAL_ARG:
                raise ExpressionParseError(
                    f"El factorial admite argumentos de hasta {MAX_FACTORIAL_ARG}."
                )
        return None
    if isinstance(node, ast.Name):
        return _NAMED_CONSTANTS.get(node.id)
    if isinstance(node, ast.UnaryOp):
        operand = _estimate_constant(node.operand)
        if operand is None:
            return None
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        return None
    if isinstance(node, ast.BinOp):
        left = _estimate_constant(node.left)
        right = _estimate_constant(node.right)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Pow):
                result = left ** right
            else:
                return None
        except OverflowError:
            return math.inf
        except (ZeroDivisionError, ValueError):
            return None
        if isinstance(result, complex) or math.isnan(result):
            return None
        return float(result)
    return None


def _validate_numeric_sizes(tree: ast.AST) -> None:
    """Rechaza literales y potencias numéricas cuyo cálculo exacto congelaría la aplicación.

    SymPy convierte 1e99999999 en un entero exacto de 100 millones de cifras, y 9**9**9**9
    en una potencia imposible de evaluar; ambos bloquearían la interfaz.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            match = re.fullmatch(r"\s*[+-]?[\d.]+[eE]([+-]?\d+)\s*", node.value)
            if match and abs(int(match.group(1))) > MAX_LITERAL_EXPONENT:
                raise ExpressionParseError(
                    f"Número fuera de rango: el exponente en notación científica no puede "
                    f"superar ±{MAX_LITERAL_EXPONENT}."
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, float) and math.isinf(node.value):
            raise ExpressionParseError("Número fuera de rango (infinito).")
        # BUG FIX A7: Acotar argumentos de factorial para evitar congelar el hilo de UI
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "factorial"
            and node.args
        ):
            val = _estimate_constant(node.args[0])
            if val is not None and val > MAX_FACTORIAL_ARG:
                raise ExpressionParseError(
                    f"El factorial admite argumentos de hasta {MAX_FACTORIAL_ARG}."
                )

        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)):
            continue
        exponent = _estimate_constant(node.right)
        if exponent is None:
            continue
        if abs(exponent) > MAX_POW_EXPONENT:
            raise ExpressionParseError(
                f"Exponente demasiado grande: el límite es {MAX_POW_EXPONENT:,}. "
                "Esto evita que la aplicación se congele al calcular potencias gigantes."
            )
        base = _estimate_constant(node.left)
        if base is not None and math.isfinite(base) and abs(base) not in (0.0, 1.0):
            if abs(exponent) * math.log10(abs(base)) > MAX_POW_DIGITS:
                raise ExpressionParseError(
                    f"El resultado de la potencia tendría más de {MAX_POW_DIGITS:,} cifras; "
                    "reduzca la base o el exponente."
                )


def _validate_code_ast(code_str: str) -> None:
    """Valida la estructura sintáctica del árbol AST generado antes de evaluarlo."""
    try:
        tree = ast.parse(code_str, mode="eval")
    except Exception as exc:
        raise ExpressionParseError(f"Error de sintaxis en la expresión: {exc}") from exc

    _validate_numeric_sizes(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            raise ExpressionParseError(
                f"Acceso a atributos ('.{node.attr}') no está permitido por razones de seguridad."
            )
        if isinstance(node, (ast.Subscript, ast.Slice)):
            raise ExpressionParseError(
                "Operaciones de indexación o subíndices no están permitidas por seguridad."
            )
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            raise ExpressionParseError("Comprensiones no están permitidas por seguridad.")
        if isinstance(node, ast.Lambda):
            raise ExpressionParseError("Expresiones lambda no están permitidas.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionParseError("Llamadas dinámicas no permitidas.")
            if node.func.id not in _SAFE_GLOBAL_DICT:
                raise ExpressionParseError(
                    f"Llamada a función no permitida por seguridad: '{node.func.id}'."
                )
        if isinstance(node, ast.Name):
            if node.id.startswith("_") or "__" in node.id:
                raise ExpressionParseError(
                    f"Identificador '{node.id}' no permitido por seguridad."
                )


def _get_transformations():
    """Devuelve las transformaciones estándar de SymPy más algunas adicionales."""
    transformations = standard_transformations()
    return transformations


# ─────────────────────────────────────────────────────────────────────────────
# Normalización y corrección de aliases (BUG FIX A4)
# ─────────────────────────────────────────────────────────────────────────────

def _convert_decimal_commas(s: str) -> str:
    """Convierte comas decimales (0,5) a puntos (0.5), evitando números enteros como '10,'."""
    out = []
    for ch in s:
        if ch == ",":
            # Solo convertir si el siguiente carácter es un dígito o punto
            i = s.index(ch)
            if i + 1 < len(s) and s[i + 1].isdigit() or s[i + 1] == ".":
                out.append(".")
                continue
        out.append(ch)
    return "".join(out)


def _replace_abs_bars(s: str) -> str:
    """Reemplaza barras de valor absoluto |x| con Abs(x)."""
    return re.sub(r'(?<!\w)\|([^]|]+?)\|(?!\w)', r'Abs(\1)', s)


def _replace_log_base(s: str, placeholder: str, base: float) -> str:
    """Reemplaza placeholders de log con la base especificada."""
    return re.sub(
        rf"_ph_log{int(base)}\s*\(([^)]*)\)",
        lambda m: f"log(m.group(1), {base})",
        s
    )


def _normalize_expression(text: str) -> str:
    """Normaliza una expresión en castellano (es-CO) a sintaxis SymPy.

    Transformaciones aplicadas (en orden):
    1. Coma decimal (0,5) → punto decimal (0.5), solo entre dígitos.
    2. Superíndices ² → **2, ³ → **3.
    3. Constante e de Euler (símbolo aislado) → E.
    4. Símbolo π → pi.
    5. Raíz cuadrada √expr → sqrt(expr).
    6. Valor absoluto |expr| → Abs(expr).
    7. Logaritmos con base: log10(...) → log(..., 10), log2(...) → log(..., 2).
    8. Aliases trigonométricos e hiperbólicos (ordenados de más largos a más cortos).

    BUG FIX A4: El alias 'cosenh' debe mapearse a 'cosh', no a 'asinh'.
    """
    s = text.strip()

    # 1. Coma decimal entre dígitos: "0,5" → "0.5" (no en argumentos de max(1,2), atan2(1,2)...)
    s = _convert_decimal_commas(s)

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

    # 7. Preservar log10 y log2 antes de que aliases o multiplicaciones los descompongan
    s = re.sub(r'\blog10\s*\(', r'_ph_log10(', s)
    s = re.sub(r'\blog2\s*\(', r'_ph_log2(', s)

    # 8. Aliases en español e inglés extendidos (orden: más largo primero)
    aliases = [
        ('arcsinh', 'asinh'),
        ('arccosh', 'acosh'),
        ('arctanh', 'atanh'),
        ('arccoth', 'acoth'),
        ('arcsen',  'asin'),
        ('arcsin',  'asin'),
        ('arccos',  'acos'),
        ('arctan',  'atan'),
        ('arctg',   'atan'),
        ('arccot',  'acot'),
        ('arccsc',  'acsc'),
        ('arcsec',  'asec'),
        ('cotan',   'cot'),
        ('cotg',    'cot'),
        ('ctg',     'cot'),
        ('cosec',   'csc'),
        ('senh',    'sinh'),
        ('cosenh',  'cosh'),  # BUG FIX A4: cosenh -> cosh (no asinh)
        ('tgh',     'tanh'),
        ('ctgh',    'coth'),
        ('sen',     'sin'),
        ('tg',      'tan'),
        ('raiz',    'sqrt'),
        ('ln',      'log'),
    ]
    for es, en in aliases:
        s = re.sub(r'\b' + re.escape(es) + r'\b', en, s)

    # Reemplazar placeholders de log10 y log2
    s = _replace_log_base(s, '_ph_log10', 10)
    s = _replace_log_base(s, '_ph_log2', 2)

    return s


def _check_unrecognized_functions(text: str) -> None:
    """Verifica que ningún identificador previo a un paréntesis sea desconocido.

    Evita que funciones no reconocidas sean descompuestas silenciosamente en
    multiplicaciones implícitas de símbolos de una letra (ej. 'arcsin(x)' -> a*c*i*n*r*s*x).
    """
    matches = re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', text)
    for m in matches:
        func_name = m.group(1)
        # Identificadores de más de una letra seguidos de paréntesis deben ser funciones conocidas
        if len(func_name) > 1 and func_name not in _SAFE_LOCAL_DICT:
            raise ExpressionParseError(
                f"Función matemática no reconocida: '{func_name}()'. "
                f"Verifique la ortografía o consulte las funciones admitidas."
            )


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

def parse_math_expression(text: str) -> ParsedExpression:
    """Parsea una expresión matemática en texto a un objeto ParsedExpression.

    Acepta sintaxis estándar, amigable y en español colombiano:
    - 'x^2 + 2x - 1'
    - 'sin(x) * cos(x)', 'sen(x)', 'tg(x)', 'arcsin(x)', 'ctg(x)', 'log10(x)'
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
        ExpressionParseError: Si la cadena está vacía, contiene caracteres inválidos,
            funciones no reconocidas o código malicioso.
    """
    clean_text = text.strip()
    if not clean_text:
        raise ExpressionParseError("La expresión matemática no puede estar vacía.")
    if len(clean_text) > MAX_EXPRESSION_LENGTH:
        raise ExpressionParseError(
            f"La expresión es demasiado larga ({len(clean_text)} caracteres; "
            f"máximo {MAX_EXPRESSION_LENGTH})."
        )

    if not _SYMPY_AVAILABLE:
        # Modo degradado: retorna información básica sin cálculo simbólico
        return ParsedExpression(
            raw_text=clean_text,
            plain_text=clean_text,
            latex=clean_text,
            sympy_expr=None,
            variables=["x"],
        )

    # 1. Validación preventiva de seguridad
    _validate_safety(clean_text)

    # 2. Normalizar (es-CO y alias → SymPy estándar)
    normalized = _normalize_expression(clean_text)

    # 3. Red de seguridad estructural: bloquear funciones no reconocidas
    _check_unrecognized_functions(normalized)

    try:
        # 4. Transformar a código Python mediante transformaciones de SymPy
        code = stringify_expr(
            normalized,
            _SAFE_LOCAL_DICT,
            _SAFE_GLOBAL_DICT,
            _get_transformations(),
        )

        # 5. Validación estricta del AST antes de evaluación
        _validate_code_ast(code)

        # 6. Evaluación aislada y segura
        sym_expr = eval_expr(code, _SAFE_LOCAL_DICT, _SAFE_GLOBAL_DICT)

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


_PT_NUM = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_PT_PAREN = rf"\(\s*{_PT_NUM}\s*,\s*{_PT_NUM}\s*\)"
_PT_BRACKET = rf"\[\s*{_PT_NUM}\s*,\s*{_PT_NUM}\s*\]"
_PT_PLAIN = rf"{_PT_NUM}(?:\s*,\s*|\s+){_PT_NUM}"
_POINTS_PATTERNS = (
    # (0, 1), (1, 2) · también separados por ';' o espacios
    re.compile(rf"\s*{_PT_PAREN}(?:\s*[,;]?\s*{_PT_PAREN})*\s*[,;]?\s*"),
    # [0, 1]; [1, 2]
    re.compile(rf"\s*{_PT_BRACKET}(?:\s*[,;]?\s*{_PT_BRACKET})*\s*[,;]?\s*"),
    # 0, 1; 1, 2  (al menos dos pares)
    re.compile(rf"\s*{_PT_PLAIN}(?:\s*;\s*{_PT_PLAIN})+\s*;?\s*"),
    # 0 1\n1 2  (una línea por punto)
    re.compile(rf"\s*{_PT_PLAIN}(?:\s*\n\s*{_PT_PLAIN})+\s*"),
)


def is_points_input(text: str) -> bool:
    """Determina si la entrada de texto corresponde a un conjunto de puntos discretos.

    El texto COMPLETO debe tener forma de lista de pares numéricos. Antes bastaba con que
    hubiera paréntesis y una coma, así que expresiones válidas como ``max(1,2)*x``,
    ``log(x,2)``, ``atan2(x,1)`` o ``0,5*(x+1)`` (coma decimal es-CO) se desviaban al lector
    de puntos y la interfaz mostraba un error de interpolación.
    """
    clean = text.strip()
    if not clean:
        return False
    return any(p.fullmatch(clean) for p in _POINTS_PATTERNS)


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
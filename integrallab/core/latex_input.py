"""Conversión entre la notación visual (LaTeX del editor de fórmulas) y el texto del parser.

Responsabilidad:
El editor visual (estilo GeoGebra o calculadora Casio) produce LaTeX: ``\\frac{1}{x}``,
``\\sqrt[3]{x}``, ``\\sin x``. Este módulo lo traduce a la sintaxis de texto que ya entiende
``parse_math_expression`` (``((1)/(x))``, ``root(x,3)``, ``sin(x)``), de modo que TODA entrada,
escrita o dibujada, sigue pasando por el mismo parser seguro con lista blanca. También hace
el camino inverso (texto → LaTeX) para mostrar en el editor lo que ya estaba escrito.

Convenciones de la notación visual (las de una calculadora y las de clase):
- ``log x`` sin base es logaritmo en base 10; ``ln x`` es el natural; ``log_b x`` usa base b.
- ``sen x`` / ``\\sin 2x`` aplican la función a todo el producto siguiente: sin(2*x).
- ``\\sin^{2} x`` es (sin x)²; ``\\sin^{-1} x`` es arcoseno.
- La multiplicación implícita (``2x``, ``x\\sin x``) se escribe explícita (``2*x``).

Este módulo no ejecuta nada: solo transforma cadenas. Lo que devuelve se valida después con
el parser seguro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "LatexInputError",
    "MAX_LATEX_LENGTH",
    "expression_to_latex",
    "latex_to_expression",
]

MAX_LATEX_LENGTH = 2000


class LatexInputError(ValueError):
    """La fórmula del editor visual no se puede traducir (incompleta o con algo no admitido)."""


# ─────────────────────────────────────────────────────────────────────────────
# Tabla de funciones: nombre visual → nombre del parser
# ─────────────────────────────────────────────────────────────────────────────

_FUNCTIONS: dict[str, str] = {
    "sin": "sin", "sen": "sin", "cos": "cos", "tan": "tan", "tg": "tan",
    "cot": "cot", "ctg": "cot", "cotg": "cot", "sec": "sec", "csc": "csc", "cosec": "csc",
    "arcsin": "asin", "arcsen": "asin", "asin": "asin",
    "arccos": "acos", "acos": "acos",
    "arctan": "atan", "arctg": "atan", "atan": "atan",
    "arccot": "acot", "acot": "acot", "arcsec": "asec", "asec": "asec",
    "arccsc": "acsc", "acsc": "acsc",
    "sinh": "sinh", "senh": "sinh", "cosh": "cosh", "tanh": "tanh", "coth": "coth",
    "arsinh": "asinh", "arcsinh": "asinh", "asinh": "asinh",
    "arcosh": "acosh", "arccosh": "acosh", "acosh": "acosh",
    "artanh": "atanh", "arctanh": "atanh", "atanh": "atanh",
    "arcoth": "acoth", "acoth": "acoth",
    "exp": "exp", "ln": "ln", "log": "log", "lg": "lg",
    "sqrt": "sqrt", "raiz": "sqrt", "abs": "Abs",
    "max": "Max", "min": "Min", "sgn": "sign", "sign": "sign",
    "floor": "floor", "ceil": "ceiling", "ceiling": "ceiling",
    "atan2": "atan2",
}

# Inversa con exponente −1: sin^{-1} x = arcsin x.
_INVERSE: dict[str, str] = {
    "sin": "asin", "cos": "acos", "tan": "atan", "cot": "acot", "sec": "asec", "csc": "acsc",
    "sinh": "asinh", "cosh": "acosh", "tanh": "atanh", "coth": "acoth",
}

# Nombres escritos letra a letra (sin barra invertida) que se reconocen como función,
# del más largo al más corto para que «arcsen» no se lea como «a·r·c·sen».
_LETTER_FUNCTIONS = sorted(
    (name for name in _FUNCTIONS if name.isalpha() and len(name) > 1), key=len, reverse=True
)

# Comandos que no aportan nada al significado (espacios, estilos, delimitadores invisibles).
_IGNORED = frozenset({
    ",", ";", ":", "!", " ", "quad", "qquad", "displaystyle", "textstyle", "scriptstyle",
    "limits", "nolimits", "mathstrut", "strut", "allowbreak",
})

_CONSTANTS: dict[str, str] = {
    "pi": "pi", "infty": "oo", "exponentialE": "E", "imaginaryI": "I",
}

_MULTIPLY = frozenset({"cdot", "times", "ast"})
_OPEN_PAREN = frozenset({"(", "[", "lparen", "lbrack"})
_CLOSE_PAREN = frozenset({")", "]", "rparen", "rbrack"})
_ABS_BARS = frozenset({"|", "vert", "lvert", "rvert"})
_PLAIN_ATOM = re.compile(r"[A-Za-z0-9_.]+")


@dataclass(frozen=True)
class _Tok:
    kind: str   # "cmd", "num", "letter", "char"
    value: str


def _tokenize(latex: str) -> list[_Tok]:
    """Parte el LaTeX en comandos, números, letras y símbolos sueltos."""
    unicode_map = {"π": ("cmd", "pi"), "·": ("cmd", "cdot"), "×": ("cmd", "times"),
                   "−": ("char", "-"), "∞": ("cmd", "infty"), "÷": ("cmd", "div")}
    tokens: list[_Tok] = []
    i, n = 0, len(latex)
    while i < n:
        ch = latex[i]
        if ch.isspace() or ch == "~":
            i += 1
            continue
        if ch == "\\":
            j = i + 1
            if j < n and latex[j].isalpha():
                while j < n and latex[j].isalpha():
                    j += 1
                name = latex[i + 1:j]
            elif j < n:
                name = latex[j]
                j += 1
            else:
                raise LatexInputError("La fórmula termina con una barra invertida suelta.")
            i = j
            if name not in _IGNORED:
                tokens.append(_Tok("cmd", name))
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and latex[i + 1].isdigit()):
            j = i
            while j < n and latex[j].isdigit():
                j += 1
            if j < n and latex[j] == "." and j + 1 < n and latex[j + 1].isdigit():
                j += 1
                while j < n and latex[j].isdigit():
                    j += 1
            tokens.append(_Tok("num", latex[i:j]))
            i = j
            continue
        if ch.isalpha() and ch.isascii():
            tokens.append(_Tok("letter", ch))
            i += 1
            continue
        if ch in unicode_map:
            kind, value = unicode_map[ch]
            tokens.append(_Tok(kind, value))
            i += 1
            continue
        if ch in "+-*/=!|()[]{}^_,'":
            tokens.append(_Tok("char", ch))
            i += 1
            continue
        raise LatexInputError(f"El símbolo «{ch}» no se admite en las fórmulas.")
    return tokens


def _wrap(text: str) -> str:
    """Pone paréntesis salvo que ``text`` ya sea un átomo (número, nombre o grupo completo)."""
    if _PLAIN_ATOM.fullmatch(text):
        return text
    if text.startswith("(") and text.endswith(")"):
        depth = 0
        for k, ch in enumerate(text):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and k < len(text) - 1:
                break
        else:
            return text
    return f"({text})"


class _Reader:
    """Analizador descendente recursivo del subconjunto de LaTeX que genera el editor."""

    def __init__(self, tokens: list[_Tok]) -> None:
        self.toks = tokens
        self.pos = 0
        self.abs_depth = 0

    # ── utilidades ──────────────────────────────────────────────────────────
    def peek(self, offset: int = 0) -> _Tok | None:
        k = self.pos + offset
        return self.toks[k] if k < len(self.toks) else None

    def take(self) -> _Tok:
        tok = self.peek()
        if tok is None:
            raise LatexInputError("La fórmula está incompleta.")
        self.pos += 1
        return tok

    def is_char(self, value: str, offset: int = 0) -> bool:
        tok = self.peek(offset)
        return tok is not None and tok.kind == "char" and tok.value == value

    def is_cmd(self, *names: str) -> bool:
        tok = self.peek()
        return tok is not None and tok.kind == "cmd" and tok.value in names

    def expect_char(self, value: str) -> None:
        if not self.is_char(value):
            raise LatexInputError(f"Falta «{value}» en la fórmula.")
        self.pos += 1

    # ── delimitadores ───────────────────────────────────────────────────────
    def delimiter_kind(self) -> tuple[str, int] | None:
        """Si hay un delimitador de apertura, devuelve (tipo, tokens que ocupa)."""
        tok = self.peek()
        if tok is None:
            return None
        width = 0
        if tok.kind == "cmd" and tok.value in ("left", "mleft", "bigl", "Bigl", "big", "Big"):
            width = 1
            tok = self.peek(1)
            if tok is None:
                return None
        value = tok.value
        if tok.kind == "char" and value in "([":
            return "paren", width + 1
        if tok.kind == "cmd" and value in _OPEN_PAREN:
            return "paren", width + 1
        if tok.kind == "char" and value == "{" and width:
            return "paren", width + 1          # \left\{ … \right\}
        if (tok.kind == "char" and value == "|") or (tok.kind == "cmd" and value in _ABS_BARS):
            return "abs", width + 1
        if tok.kind == "cmd" and value == "lfloor":
            return "floor", width + 1
        if tok.kind == "cmd" and value == "lceil":
            return "ceiling", width + 1
        return None

    def at_closer(self, kind: str) -> int:
        """Tokens que ocupa el cierre de ``kind`` en la posición actual (0 si no hay cierre)."""
        tok = self.peek()
        if tok is None:
            return 0
        width = 0
        if tok.kind == "cmd" and tok.value in ("right", "mright", "bigr", "Bigr", "big", "Big"):
            width = 1
            tok = self.peek(1)
            if tok is None:
                return 0
        v = tok.value
        if kind == "paren" and ((tok.kind == "char" and v in ")]") or (tok.kind == "cmd" and v in _CLOSE_PAREN)
                                or (width and tok.kind == "char" and v == "}")):
            return width + 1
        if kind == "abs" and ((tok.kind == "char" and v == "|") or (tok.kind == "cmd" and v in _ABS_BARS)):
            return width + 1
        if kind == "floor" and tok.kind == "cmd" and v == "rfloor":
            return width + 1
        if kind == "ceiling" and tok.kind == "cmd" and v == "rceil":
            return width + 1
        return 0

    def read_delimited(self) -> str:
        kind, width = self.delimiter_kind()  # type: ignore[misc]
        self.pos += width
        if kind == "abs":
            self.abs_depth += 1
        inner = self.read_list()
        closing = self.at_closer(kind)
        if not closing:
            raise LatexInputError("Hay un paréntesis o una barra de valor absoluto sin cerrar.")
        self.pos += closing
        if kind == "abs":
            self.abs_depth -= 1
        if not inner:
            raise LatexInputError("Completa los recuadros vacíos de la fórmula.")
        if kind == "abs":
            return f"Abs({inner})"
        if kind in ("floor", "ceiling"):
            return f"{kind}({inner})"
        return f"({inner})"

    def read_group(self) -> str:
        """Contenido de ``{...}``; un grupo vacío es un recuadro sin completar."""
        self.expect_char("{")
        inner = self.read_list(closer="}")
        self.expect_char("}")
        if not inner:
            raise LatexInputError("Completa los recuadros vacíos de la fórmula.")
        return inner

    def read_raw_group(self) -> str:
        """Texto literal de ``{...}`` (para \\operatorname y \\mathrm)."""
        self.expect_char("{")
        parts: list[str] = []
        depth = 1
        while True:
            tok = self.take()
            if tok.kind == "char" and tok.value == "{":
                depth += 1
                continue
            if tok.kind == "char" and tok.value == "}":
                depth -= 1
                if depth == 0:
                    break
                continue
            parts.append(tok.value if tok.kind != "cmd" else "")
        return "".join(parts)

    def read_argument(self) -> str:
        """Argumento de \\frac o \\sqrt: un grupo ``{…}`` o un solo token (``\\frac13``)."""
        if self.is_char("{"):
            return self.read_group()
        tok = self.peek()
        if tok is None:
            raise LatexInputError("La fórmula está incompleta.")
        if tok.kind == "num":
            self.pos += 1
            if len(tok.value) > 1 and tok.value.isdigit():
                # \frac123 = \frac{1}{2}3: el resto de las cifras vuelve a la entrada
                self.toks[self.pos - 1] = _Tok("num", tok.value[0])
                self.toks.insert(self.pos, _Tok("num", tok.value[1:]))
                return tok.value[0]
            return tok.value
        return self.read_primary()

    # ── gramática ───────────────────────────────────────────────────────────
    def read_list(self, closer: str | None = None) -> str:
        """Expresiones separadas por comas (listas de puntos, argumentos de max/log)."""
        if self.ends_expression(closer):
            return ""
        items = [self.read_expression()]
        while self.is_char(","):
            self.pos += 1
            items.append(self.read_expression())
        return ",".join(items)

    def ends_expression(self, closer: str | None = None) -> bool:
        tok = self.peek()
        if tok is None:
            return True
        if closer is not None and self.is_char(closer):
            return True
        return bool(self.at_closer("paren") or (self.abs_depth and self.at_closer("abs"))
                    or self.at_closer("floor") or self.at_closer("ceiling")
                    or self.is_char("}") or self.is_char("]") or self.is_char(","))

    def read_expression(self) -> str:
        out = ""
        if self.is_char("+") or self.is_char("-"):
            sign = self.take().value
            out = ("-" if sign == "-" else "") + self.read_term()
        else:
            out = self.read_term()
        while self.is_char("+") or self.is_char("-"):
            sign = self.take().value
            out += sign + self.read_term()
        if self.is_char("="):
            raise LatexInputError("Escribe solo la expresión, sin el signo igual.")
        return out

    def starts_factor(self) -> bool:
        tok = self.peek()
        if tok is None:
            return False
        if tok.kind in ("num", "letter"):
            return True
        if tok.kind == "char":
            if tok.value in "([{":
                return True
            if tok.value == "|":
                return self.abs_depth == 0
            return False
        if tok.value in ("left", "mleft"):
            nxt = self.peek(1)
            if nxt is not None and ((nxt.kind == "char" and nxt.value == "|") or nxt.value in _ABS_BARS):
                return self.abs_depth == 0
            return True
        if tok.value in _ABS_BARS:
            return self.abs_depth == 0
        if tok.value in ("right", "mright", "rfloor", "rceil") or tok.value in _MULTIPLY or tok.value == "div":
            return False
        if tok.value in ("degree", "circ"):
            return False
        return True

    def read_term(self) -> str:
        out = self.read_factor()
        while True:
            if self.is_char("*") or self.is_cmd(*_MULTIPLY):
                self.pos += 1
                out = f"{out}*{self.read_signed_factor()}"
            elif self.is_char("/") or self.is_cmd("div"):
                self.pos += 1
                out = f"{_wrap(out)}/{_wrap(self.read_signed_factor())}"
            elif self.starts_factor():
                out = f"{out}*{self.read_factor()}"
            else:
                return out

    def read_signed_factor(self) -> str:
        if self.is_char("-"):
            self.pos += 1
            return f"(-{self.read_factor()})"
        if self.is_char("+"):
            self.pos += 1
        return self.read_factor()

    def read_factor(self) -> str:
        base = self.read_primary()
        return self.read_postfix(base)

    def read_postfix(self, base: str) -> str:
        while True:
            if self.is_char("^"):
                self.pos += 1
                if self.is_cmd("circ"):
                    self.pos += 1
                    base = f"{_wrap(base)}*pi/180"
                    continue
                if self.is_char("{") and (t := self.peek(1)) is not None and t.value == "circ" and self.is_char("}", 2):
                    self.pos += 3
                    base = f"{_wrap(base)}*pi/180"
                    continue
                exponent = self.read_script()
                if base == "E":
                    base = f"exp({exponent})"
                else:
                    base = f"{_wrap(base)}**{_wrap(exponent)}"
            elif self.is_cmd("degree", "circ"):
                self.pos += 1
                base = f"{_wrap(base)}*pi/180"
            elif self.is_char("!"):
                self.pos += 1
                base = f"{_wrap(base)}!"
            elif self.is_char("_"):
                raise LatexInputError("Los subíndices solo se admiten en la base del logaritmo (log_b).")
            elif self.is_char("'"):
                raise LatexInputError("La notación de derivada (f') no se admite en esta casilla.")
            else:
                return base

    def read_script(self) -> str:
        """Exponente o subíndice: ``{…}``, una cifra o un símbolo (``x^2``, ``x^n``)."""
        if self.is_char("{"):
            return self.read_group()
        if self.is_char("-"):
            self.pos += 1
            return f"-{self.read_script()}"
        tok = self.peek()
        if tok is not None and tok.kind == "num":
            self.pos += 1
            if len(tok.value) > 1 and tok.value.isdigit():
                self.toks.insert(self.pos, _Tok("num", tok.value[1:]))
                return tok.value[0]
            return tok.value
        return self.read_primary()

    def read_primary(self) -> str:
        tok = self.peek()
        if tok is None:
            raise LatexInputError("La fórmula está incompleta: falta un término.")

        if tok.kind == "num":
            self.pos += 1
            return tok.value

        if tok.kind == "letter":
            nxt = self.peek(1)
            if tok.value == "p" and nxt is not None and nxt.kind == "letter" and nxt.value == "i":
                self.pos += 2
                return "pi"
            name = self.letter_function()
            if name is not None:
                return self.read_function(name)
            self.pos += 1
            return {"e": "E", "i": "I"}.get(tok.value, tok.value)

        if tok.kind == "char":
            if tok.value == "{":
                return f"({self.read_group()})"
            if self.delimiter_kind() is not None:
                return self.read_delimited()
            if tok.value in "+-":
                raise LatexInputError("Hay dos signos seguidos; usa paréntesis, por ejemplo 2·(−x).")
            raise LatexInputError(f"Falta un término antes de «{tok.value}».")

        # Comandos
        name = tok.value
        if self.delimiter_kind() is not None:
            return self.read_delimited()
        self.pos += 1
        if name in _MULTIPLY or name == "div":
            raise LatexInputError("Falta un término antes del signo de multiplicar o dividir.")
        if name == "placeholder":
            raise LatexInputError("Completa los recuadros vacíos de la fórmula.")
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            num = self.read_argument()
            den = self.read_argument()
            return f"(({num})/({den}))"
        if name == "sqrt":
            index = None
            if self.is_char("["):
                self.pos += 1
                index = self.read_list(closer="]")
                self.expect_char("]")
                if not index:
                    raise LatexInputError("Completa el índice de la raíz.")
            radicand = self.read_argument()
            return f"sqrt({radicand})" if index is None else f"root({radicand},{index})"
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        if name in ("mathrm", "mathit", "text", "mathbf", "operatorname", "mathop"):
            raw = self.read_raw_group().replace(" ", "")
            raw = raw.replace("_{2}", "2").replace("_2", "2")
            if name in ("mathrm", "mathit") and raw == "e":
                return "E"
            if raw == "atan" and self.is_char("_"):  # SymPy escribe atan2 como \operatorname{atan}_{2}
                self.pos += 1
                if self.read_script() != "2":
                    raise LatexInputError("Los subíndices solo se admiten en la base del logaritmo (log_b).")
                return self.read_function("atan2")
            if raw.lower() in _FUNCTIONS:
                return self.read_function(raw.lower())
            if name == "text":
                raise LatexInputError("Las casillas de fórmula no admiten texto; escribe solo matemáticas.")
            if len(raw) == 1 and raw.isalpha():
                return raw
            raise LatexInputError(f"No se reconoce «{raw}» como función o constante.")
        if name in _FUNCTIONS:
            return self.read_function(name)
        raise LatexInputError(f"La fórmula usa «\\{name}», que todavía no se admite.")

    def letter_function(self) -> str | None:
        """Nombre de función escrito letra a letra (``sen``, ``abs``) en la posición actual."""
        letters = []
        k = 0
        while (tok := self.peek(k)) is not None and tok.kind == "letter" and k < 8:
            letters.append(tok.value)
            k += 1
        word = "".join(letters).lower()
        for name in _LETTER_FUNCTIONS:
            if word.startswith(name):
                after = self.peek(len(name))
                # Solo es función si le sigue un argumento (evita leer «ln» de «l·n» suelto).
                if after is not None and not (after.kind == "char" and after.value in "+-=,)}]*/^_!"):
                    self.pos += len(name)
                    return name
        return None

    def read_function(self, name: str) -> str:
        """Aplicación de función: exponente, base del logaritmo y argumento."""
        power: str | None = None
        base: str | None = None
        for _ in range(2):
            if self.is_char("^"):
                self.pos += 1
                power = self.read_script()
            elif self.is_char("_"):
                if name not in ("log", "lg"):
                    raise LatexInputError("Los subíndices solo se admiten en la base del logaritmo (log_b).")
                self.pos += 1
                base = self.read_script()

        argument = self.read_function_argument(name)
        target = _FUNCTIONS[name]
        if power is not None and power.replace("(", "").replace(")", "") == "-1" and target in _INVERSE:
            target, power = _INVERSE[target], None

        if target == "ln":
            call = f"log({argument})"
        elif target == "log":
            call = f"log({argument},{base if base is not None else '10'})"
        elif target == "lg":
            call = f"log({argument},10)"
        else:
            call = f"{target}({argument})"
        return call if power is None else f"{call}**{_wrap(power)}"

    def read_function_argument(self, name: str) -> str:
        if self.delimiter_kind() is not None and self.delimiter_kind()[0] == "paren":
            kind, width = self.delimiter_kind()  # type: ignore[misc]
            self.pos += width
            inner = self.read_list()
            closing = self.at_closer("paren")
            if not closing:
                raise LatexInputError(f"Falta cerrar el paréntesis de {name}.")
            self.pos += closing
            if not inner:
                raise LatexInputError(f"Completa el argumento de {name}.")
            return inner
        if self.is_char("{"):
            group = self.read_group()
            # SymPy escribe \sin{\left(x\right)}: el grupo envuelve un único paréntesis.
            return group[1:-1] if group.startswith("(") and _wrap(group) == group else group
        if not self.starts_factor():
            raise LatexInputError(f"Falta el argumento de {name}.")
        # Sin paréntesis: el argumento es el producto que sigue, hasta un + o − o una función.
        factors = [self.read_factor()]
        while self.starts_factor() and not self.at_function():
            factors.append(self.read_factor())
        return "*".join(factors)

    def at_function(self) -> bool:
        tok = self.peek()
        if tok is None:
            return False
        if tok.kind == "cmd":
            return tok.value in _FUNCTIONS or tok.value == "operatorname"
        if tok.kind == "letter":
            save = self.pos
            found = self.letter_function() is not None
            self.pos = save
            return found
        return False


def latex_to_expression(latex: str) -> str:
    """Traduce el LaTeX del editor visual a texto para ``parse_math_expression``.

    Returns:
        Cadena en sintaxis del parser (``""`` si la casilla está vacía).

    Raises:
        LatexInputError: si la fórmula está incompleta (recuadros vacíos) o usa notación que
            el parser no admite (integrales, matrices, texto).
    """
    clean = (latex or "").strip()
    if not clean:
        return ""
    if len(clean) > MAX_LATEX_LENGTH:
        raise LatexInputError(f"La fórmula es demasiado larga (máximo {MAX_LATEX_LENGTH} caracteres).")
    reader = _Reader(_tokenize(clean))
    if not reader.toks:
        return ""
    result = reader.read_list()
    if reader.peek() is not None:
        leftover = reader.peek()
        symbol = leftover.value if leftover.kind != "cmd" else f"\\{leftover.value}"
        if leftover.value in (")", "]", "right", "rparen", "rbrack", "mright"):
            raise LatexInputError("Hay un paréntesis de cierre sin su apertura.")
        raise LatexInputError(f"No se entiende la fórmula a partir de «{symbol}».")
    return result


def expression_to_latex(text: str) -> str:
    """LaTeX para mostrar en el editor visual una expresión escrita en texto.

    Usa ``\\ln`` para el logaritmo natural (en el editor, ``log`` sin base es base 10) y
    ``\\arcsin`` para las inversas. Una lista de puntos se muestra tal cual.

    Raises:
        ExpressionParseError: si el texto no es una expresión válida.
    """
    from integrallab.core.parser import is_points_input, parse_math_expression, parse_points

    clean = (text or "").strip()
    if not clean:
        return ""
    if is_points_input(clean):
        def fmt(v: float) -> str:
            return f"{v:g}" if abs(v) < 1e15 else repr(v)
        return ",".join(f"\\left({fmt(x)},{fmt(y)}\\right)" for x, y in parse_points(clean))
    parsed = parse_math_expression(clean)
    if parsed.sympy_expr is None:  # modo degradado sin SymPy
        return clean
    import sympy

    return sympy.latex(parsed.sympy_expr, ln_notation=True, inv_trig_style="full")

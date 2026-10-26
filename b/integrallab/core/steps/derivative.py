"""Derivadas paso a paso (reglas de la suma, el producto, el cociente y la cadena).

Responsabilidad:
Construir el árbol de pasos de ``d/dx expr`` aplicando explícitamente cada regla de
derivación. Se usa para la «Comprobación» de una primitiva: derivar F(x) debe devolver el
integrando, y mostrar esa derivada con sus reglas (cadena, producto) cierra el razonamiento
de forma rigurosa en lugar de pedir al estudiante que confíe en el resultado.

La recursión sigue la estructura de la expresión; ``IdGenerator`` limita el número total de
nodos (``MAX_TREE_NODES``) para que expresiones enormes no generen árboles gigantes.
"""

from __future__ import annotations

import sympy

from integrallab.core.steps.latex import latex, tagged_latex
from integrallab.core.steps.model import IdGenerator, StepNode

__all__ = ["build_derivative_tree"]

# Derivadas de las funciones elementales en su argumento u (la cadena se aplica aparte).
_ELEMENTARY: dict[type, tuple[str, str]] = {
    sympy.sin: ("Derivada del seno", "d/du sin(u) = cos(u)."),
    sympy.cos: ("Derivada del coseno", "d/du cos(u) = −sin(u)."),
    sympy.tan: ("Derivada de la tangente", "d/du tan(u) = sec²(u)."),
    sympy.cot: ("Derivada de la cotangente", "d/du cot(u) = −csc²(u)."),
    sympy.sec: ("Derivada de la secante", "d/du sec(u) = sec(u)·tan(u)."),
    sympy.csc: ("Derivada de la cosecante", "d/du csc(u) = −csc(u)·cot(u)."),
    sympy.exp: ("Derivada de la exponencial", "d/du eᵘ = eᵘ."),
    sympy.log: ("Derivada del logaritmo natural", "d/du ln(u) = 1/u."),
    sympy.asin: ("Derivada del arcoseno", "d/du arcsin(u) = 1/√(1 − u²)."),
    sympy.acos: ("Derivada del arcocoseno", "d/du arccos(u) = −1/√(1 − u²)."),
    sympy.atan: ("Derivada de la arcotangente", "d/du arctan(u) = 1/(1 + u²)."),
    sympy.sinh: ("Derivada del seno hiperbólico", "d/du sinh(u) = cosh(u)."),
    sympy.cosh: ("Derivada del coseno hiperbólico", "d/du cosh(u) = sinh(u)."),
    sympy.tanh: ("Derivada de la tangente hiperbólica", "d/du tanh(u) = 1 − tanh²(u)."),
}


def _d(expr: sympy.Expr, x: sympy.Symbol) -> str:
    body = latex(expr)
    return rf"\frac{{d}}{{d{latex(x)}}}\left[{body}\right]"


def _tagged_d(expr: sympy.Expr, x: sympy.Symbol, tags: dict[sympy.Basic, str]) -> str:
    return rf"\frac{{d}}{{d{latex(x)}}}\left[{tagged_latex(expr, tags)}\right]"


def build_derivative_tree(expr: sympy.Expr, x: sympy.Symbol, ids: IdGenerator | None = None) -> StepNode:
    """Árbol de pasos de la derivada de ``expr`` respecto a ``x``."""
    ids = ids or IdGenerator()
    return _node(sympy.sympify(expr), x, ids)


def _node(expr: sympy.Expr, x: sympy.Symbol, ids: IdGenerator) -> StepNode:
    nid = ids.next()
    result = sympy.diff(expr, x)
    head = rf"{_d(expr, x)} = {latex(result)}"

    if ids.exhausted:
        return StepNode(nid, "Derivative", "Derivada", "Desglose resumido: la expresión es muy grande.", head)

    if not expr.has(x):
        return StepNode(nid, "ConstantDerivative", "Derivada de una constante",
                        "Una constante no cambia: su derivada es 0.", head)
    if expr == x:
        return StepNode(nid, "IdentityDerivative", "Derivada de la variable", f"d/d{x} {x} = 1.", head)

    if isinstance(expr, sympy.Add):
        terms = list(expr.args)
        children = tuple(_node(t, x, ids) for t in terms)
        tags = {t: c.id for t, c in zip(terms, children)}
        return StepNode(nid, "SumRule", "Regla de la suma",
                        "La derivada de una suma es la suma de las derivadas de cada término.",
                        rf"{_tagged_d(expr, x, tags)} = {latex(result)}", children)

    if isinstance(expr, sympy.Mul):
        const, rest = expr.as_independent(x, as_Add=False)
        if const != 1:
            child = _node(rest, x, ids)
            return StepNode(nid, "ConstantMultipleRule", "Constante por una función",
                            f"La constante {sympy.sstr(const)} sale de la derivada: (c·g)' = c·g'.",
                            rf"{_tagged_d(expr, x, {rest: child.id})} = {latex(result)}", (child,))
        numer, denom = sympy.fraction(expr)
        if denom.has(x) and numer != 1:
            cn, cd = _node(numer, x, ids), _node(denom, x, ids)
            return StepNode(nid, "QuotientRule", "Regla del cociente",
                            "(u/v)' = (u'·v − u·v') / v².",
                            rf"{_tagged_d(expr, x, {numer: cn.id, denom: cd.id})} = {latex(result)}", (cn, cd))
        factors = list(expr.args)
        u = factors[0]
        v = sympy.Mul(*factors[1:])
        cu, cv = _node(u, x, ids), _node(v, x, ids)
        return StepNode(nid, "ProductRule", "Regla del producto",
                        f"(u·v)' = u'·v + u·v', con u = {sympy.sstr(u)} y v = {sympy.sstr(v)}.",
                        rf"{_tagged_d(expr, x, {u: cu.id, v: cv.id})} = {latex(result)}", (cu, cv))

    if isinstance(expr, sympy.Pow):
        base, exponent = expr.args
        if not exponent.has(x):
            if base == x:
                return StepNode(nid, "PowerRule", "Regla de la potencia",
                                f"d/d{x} xⁿ = n·xⁿ⁻¹, con n = {sympy.sstr(exponent)}.", head)
            child = _node(base, x, ids)
            return StepNode(nid, "ChainRule", "Regla de la cadena (potencia)",
                            f"(uⁿ)' = n·uⁿ⁻¹·u' con u = {sympy.sstr(base)} y n = {sympy.sstr(exponent)}: "
                            "se deriva la potencia exterior y se multiplica por la derivada de lo de adentro.",
                            rf"{_tagged_d(expr, x, {base: child.id})} = {latex(result)}", (child,))
        if not base.has(x):
            child = _node(exponent, x, ids)
            return StepNode(nid, "ExponentialChainRule", "Exponencial con base constante",
                            f"(aᵘ)' = aᵘ·ln(a)·u' con a = {sympy.sstr(base)}.",
                            rf"{_tagged_d(expr, x, {exponent: child.id})} = {latex(result)}", (child,))
        return StepNode(nid, "LogarithmicDerivative", "Derivación logarítmica",
                        "Base y exponente dependen de la variable: se escribe uᵛ = e^(v·ln u) y se deriva.", head)

    if isinstance(expr, sympy.Function) and len(expr.args) == 1:
        arg = expr.args[0]
        title, rule_text = _ELEMENTARY.get(type(expr), ("Derivada de una función elemental", "Derivada conocida."))
        if arg == x:
            return StepNode(nid, "ElementaryDerivative", title, rule_text, head)
        child = _node(arg, x, ids)
        return StepNode(nid, "ChainRule", f"Regla de la cadena: {title.lower()}",
                        f"{rule_text} Como el argumento es u = {sympy.sstr(arg)}, se multiplica por u' "
                        "(derivada de lo de adentro).",
                        rf"{_tagged_d(expr, x, {arg: child.id})} = {latex(result)}", (child,))

    if isinstance(expr, sympy.Abs):
        return StepNode(nid, "AbsDerivative", "Derivada del valor absoluto",
                        "d/dx |u| = sign(u)·u' donde u ≠ 0.", head)

    return StepNode(nid, "Derivative", "Derivada", "Derivada calculada directamente.", head)

"""Desarrollo algebraico paso a paso: binomios, productos notables y factorización.

Responsabilidad:
Explicar cómo se pasa del integrando «armado» (por ejemplo ``(x² + 1)² − 1``) a su forma
desarrollada (``x⁴ + 2x²``). Cada binomio al cuadrado o al cubo y cada producto de sumas se
convierte en un nodo propio, y esa subexpresión queda marcada en la fórmula del paso padre:
al hacer clic sobre el binomio, la interfaz despliega su desarrollo.
"""

from __future__ import annotations

import sympy

from integrallab.core.steps.latex import latex, tagged_latex
from integrallab.core.steps.model import IdGenerator, StepNode

__all__ = ["build_expansion_tree", "build_factor_tree"]


def _p(term: sympy.Expr) -> str:
    """LaTeX de un término, entre paréntesis salvo que sea una variable o un número no negativo."""
    if term.is_Symbol or (term.is_Number and term >= 0):
        return latex(term)
    return rf"\left({latex(term)}\right)"


def _pow_nodes(sub: sympy.Pow, ids: IdGenerator) -> StepNode | None:
    base, n = sub.args
    if not (isinstance(base, sympy.Add) and n.is_Integer and int(n) in (2, 3)):
        return None
    expanded = sympy.expand(sub)
    terms = list(base.as_ordered_terms())
    if len(terms) == 2:
        a, b = terms
        if int(n) == 2:
            rule, title = "BinomialSquare", "Binomio al cuadrado"
            text = "(a + b)² = a² + 2ab + b²"
            middle = rf"{_p(a)}^{{2}} + 2\cdot {_p(a)}\cdot {_p(b)} + {_p(b)}^{{2}}"
        else:
            rule, title = "BinomialCube", "Binomio al cubo"
            text = "(a + b)³ = a³ + 3a²b + 3ab² + b³"
            middle = (
                rf"{_p(a)}^{{3}} + 3\cdot {_p(a)}^{{2}}\cdot {_p(b)}"
                rf" + 3\cdot {_p(a)}\cdot {_p(b)}^{{2}} + {_p(b)}^{{3}}"
            )
        explanation = f"Producto notable: {text}, con a = {sympy.sstr(a)} y b = {sympy.sstr(b)}."
        return StepNode(ids.next(), rule, title, explanation, rf"{latex(sub)} = {middle} = {latex(expanded)}")
    return StepNode(
        ids.next(), "MultinomialSquare" if int(n) == 2 else "MultinomialCube",
        "Cuadrado de un polinomio" if int(n) == 2 else "Cubo de un polinomio",
        "Se multiplica el polinomio por sí mismo término a término (cada término por todos los demás) "
        "y se reducen los términos semejantes.",
        rf"{latex(sub)} = {latex(expanded)}",
    )


def _product_node(sub: sympy.Mul, ids: IdGenerator) -> StepNode | None:
    sums = [f for f in sub.args if isinstance(f, sympy.Add)]
    if not sums:
        return None
    expanded = sympy.expand(sub)
    return StepNode(
        ids.next(), "Distributive", "Propiedad distributiva",
        "Se multiplica cada término de un factor por cada término del otro y se suman los productos.",
        rf"{latex(sub)} = {latex(expanded)}",
    )


def _collect_targets(expr: sympy.Expr) -> list[sympy.Expr]:
    """Subexpresiones que merecen su propio paso, de afuera hacia adentro y sin repetir."""
    targets: list[sympy.Expr] = []
    seen: set[sympy.Expr] = set()
    for sub in sympy.preorder_traversal(expr):
        if sub in seen:
            continue
        if isinstance(sub, sympy.Pow) and isinstance(sub.args[0], sympy.Add) and sub.args[1].is_Integer \
                and int(sub.args[1]) in (2, 3):
            targets.append(sub)
            seen.add(sub)
        elif isinstance(sub, sympy.Mul) and any(isinstance(f, sympy.Add) for f in sub.args) \
                and sympy.expand(sub) != sub:
            targets.append(sub)
            seen.add(sub)
    return targets


def build_expansion_tree(expr: sympy.Expr, ids: IdGenerator | None = None,
                         title: str = "Desarrollar el integrando") -> StepNode:
    """Nodo «expr = forma desarrollada» con un hijo por cada producto notable que aparece."""
    ids = ids or IdGenerator()
    nid = ids.next()
    expanded = sympy.expand(expr)
    children: list[StepNode] = []
    tags: dict[sympy.Basic, str] = {}
    for sub in _collect_targets(expr):
        node = _pow_nodes(sub, ids) if isinstance(sub, sympy.Pow) else _product_node(sub, ids)
        if node is not None:
            children.append(node)
            tags[sub] = node.id
    if expanded != expr:
        children.append(StepNode(
            ids.next(), "CollectTerms", "Reducir términos semejantes",
            "Se suman los coeficientes de las potencias iguales de la variable.",
            latex(expanded),
        ))
        explanation = (
            "Antes de integrar conviene escribir el integrando como una suma de términos sencillos. "
            "Toca cada parte resaltada para ver cómo se desarrolla."
            if tags else "Antes de integrar conviene escribir el integrando como una suma de términos sencillos."
        )
        return StepNode(nid, "Expand", title, explanation,
                        rf"{tagged_latex(expr, tags)} = {latex(expanded)}", tuple(children))
    return StepNode(nid, "Expand", title, "El integrando ya está en su forma más simple.", latex(expr))


def build_factor_tree(expr: sympy.Expr, var: sympy.Symbol, ids: IdGenerator | None = None) -> StepNode:
    """Factorización paso a paso de un polinomio en ``var``: factor común y cada factor irreducible."""
    ids = ids or IdGenerator()
    nid = ids.next()
    factored = sympy.factor(expr)
    children: list[StepNode] = []
    try:
        poly = sympy.Poly(expr, var)
    except sympy.PolynomialError:
        return StepNode(nid, "Factor", "Factorizar", "La expresión no es un polinomio en la variable.", latex(expr))
    content, primitive = poly.primitive()
    lowest = min((m[0] for m in poly.monoms()), default=0)
    common = content * var**lowest
    if common != 1:
        children.append(StepNode(
            ids.next(), "CommonFactor", "Sacar factor común",
            f"Todos los términos comparten el factor {sympy.sstr(common)}.",
            rf"{latex(expr)} = {latex(common)}\left({latex(sympy.expand(expr / common))}\right)",
        ))
    _coeff, factors = sympy.factor_list(sympy.expand(expr / common), var)
    for base, _mult in factors:
        if sympy.degree(base, var) >= 2 and sympy.factor(base) != base:
            children.append(StepNode(
                ids.next(), "FactorPolynomial", "Factorizar un polinomio",
                "Se buscan sus raíces (o se agrupan términos) para escribirlo como producto de factores lineales.",
                rf"{latex(base)} = {latex(sympy.factor(base))}",
            ))
    return StepNode(nid, "Factor", "Factorizar", "Se escribe la expresión como producto de factores más simples.",
                    rf"{latex(expr)} = {latex(factored)}", tuple(children))

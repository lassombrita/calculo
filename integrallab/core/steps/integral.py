"""Desglose de una primitiva a partir de las reglas de integración de SymPy.

Responsabilidad:
Convertir el árbol de reglas de ``sympy.integrals.manualintegrate.integral_steps`` (el mismo
motor que usa SymPy Gamma) en un árbol de :class:`StepNode` con títulos y explicaciones en
español. Así cada paso del desarrollo corresponde a una regla realmente aplicada (potencia,
sustitución = regla de la cadena al revés, partes = regla del producto al revés, identidades),
en lugar de adivinar la técnica por los símbolos que aparecen en el integrando.

``describe_technique`` resume la regla principal para el paso «Técnica de integración» del
desarrollo clásico (lista de 7 pasos).
"""

from __future__ import annotations

import logging
from dataclasses import fields

import sympy
from sympy.integrals import manualintegrate as mi

from integrallab.core.steps.latex import latex, tagged_latex
from integrallab.core.steps.model import IdGenerator, StepNode

__all__ = ["antiderivative", "build_integral_tree", "describe_technique", "integral_rule", "technique_name"]

logger = logging.getLogger(__name__)

# Integrandos más grandes que esto (splines, sumas enormes) no se desglosan: integral_steps
# tardaría segundos y el árbol sería ilegible. Se muestra la primitiva con una nota.
MAX_INTEGRAND_OPS = 250


def _ops(expr: sympy.Expr) -> int:
    try:
        return int(sympy.count_ops(expr))
    except Exception:  # noqa: BLE001
        return MAX_INTEGRAND_OPS + 1


def integral_rule(integrand: sympy.Expr, var: sympy.Symbol) -> mi.Rule | None:
    """Árbol de reglas de SymPy, o ``None`` si no conviene o no se puede calcular."""
    if integrand.has(sympy.Piecewise) or _ops(integrand) > MAX_INTEGRAND_OPS:
        return None
    try:
        return mi.integral_steps(integrand, var)
    except Exception:  # noqa: BLE001 - reglas incompletas para algunas funciones especiales
        logger.debug("integral_steps falló para %s", integrand, exc_info=True)
        return None


def antiderivative(integrand: sympy.Expr, var: sympy.Symbol) -> sympy.Expr:
    """La primitiva que muestra el árbol de reglas (la misma forma en el paso padre y en sus hijos).

    ``sympy.integrate`` y las reglas pueden dar primitivas que difieren en una constante o en la
    forma (``(x² + 1)⁴/8`` frente al polinomio desarrollado); usar siempre esta evita que el
    desglose muestre dos «F» distintas para el mismo integrando.
    """
    rule = integral_rule(integrand, var)
    if rule is not None:
        try:
            F = rule.eval()
            if not F.has(sympy.Integral):
                return F
        except Exception:  # noqa: BLE001
            logger.debug("rule.eval falló para %s", integrand, exc_info=True)
    return sympy.integrate(integrand, var)


def _children_rules(rule: mi.Rule) -> list[mi.Rule]:
    out: list[mi.Rule] = []
    for f in fields(rule):
        value = getattr(rule, f.name)
        items = value if isinstance(value, (list, tuple)) else [value]
        out.extend(item for item in items if isinstance(item, mi.Rule))
    return out


def _resolve(rule: mi.Rule) -> mi.Rule:
    """Una ``AlternativeRule`` ofrece varios caminos equivalentes: se muestra el primero."""
    while isinstance(rule, mi.AlternativeRule) and rule.alternatives:
        rule = rule.alternatives[0]
    return rule


def _rule_names(rule: mi.Rule) -> list[str]:
    names: list[str] = []
    stack = [rule]
    while stack:
        current = _resolve(stack.pop())
        names.append(type(current).__name__)
        stack.extend(_children_rules(current))
    return names


def _antiderivative(rule: mi.Rule) -> sympy.Expr:
    try:
        return rule.eval()
    except Exception:  # noqa: BLE001 - p. ej. PartsRule sin second_step dentro de CyclicPartsRule
        if rule.integrand is None or rule.variable is None:
            raise
        return sympy.integrate(rule.integrand, rule.variable)


def _integral_latex(integrand: sympy.Expr, var: sympy.Symbol, tags: dict[sympy.Basic, str] | None = None) -> str:
    body = tagged_latex(integrand, tags or {})
    if isinstance(integrand, sympy.Add):
        body = rf"\left({body}\right)"
    return rf"\int {body}\, d{latex(var)}"


# ── Textos por regla ─────────────────────────────────────────────────────────
#
# Las explicaciones son texto plano (la vista las inserta con textContent, sin HTML).

def _texts(rule: mi.Rule) -> tuple[str, str]:
    name = type(rule).__name__
    x = rule.variable
    if name == "ConstantRule":
        return ("Integral de una constante", "La integral de una constante c es c·x: su derivada vuelve a ser c.")
    if name == "PowerRule":
        n = rule.exp
        return (
            "Regla de la potencia",
            f"∫ uⁿ du = uⁿ⁺¹ / (n + 1) + C, válida si n ≠ −1. Aquí n = {sympy.sstr(n)}: "
            f"se suma 1 al exponente y se divide entre el nuevo exponente ({sympy.sstr(n + 1)}).",
        )
    if name == "ReciprocalRule":
        return ("Integral de 1/u", "Es el caso n = −1 de la potencia: ∫ 1/u du = ln|u| + C.")
    if name == "ConstantTimesRule":
        return (
            "Sacar la constante",
            f"La integral es lineal: ∫ c·g({x}) d{x} = c·∫ g({x}) d{x}. Aquí c = {sympy.sstr(rule.constant)}.",
        )
    if name == "AddRule":
        return ("Integrar término a término", "La integral de una suma es la suma de las integrales de cada término.")
    if name == "URule":
        return (
            "Sustitución (regla de la cadena al revés)",
            f"Se elige u = {sympy.sstr(rule.u_func)}, cuya derivada aparece (salvo una constante) en el "
            f"integrando. Se cambia d{x} por du, se integra en u y al final se vuelve a {x}.",
        )
    if name == "PartsRule":
        return (
            "Integración por partes (regla del producto al revés)",
            f"∫ u dv = u·v − ∫ v du. Siguiendo el orden LIATE se elige u = {sympy.sstr(rule.u)} "
            f"(se simplifica al derivarla) y dv = {sympy.sstr(rule.dv)} d{x} (se sabe integrar).",
        )
    if name == "CyclicPartsRule":
        return (
            "Partes cíclicas",
            "Al aplicar partes dos veces reaparece la integral original; se despeja como una incógnita.",
        )
    if name == "RewriteRule":
        return ("Reescribir el integrando", "Se usa una identidad algebraica o trigonométrica para dejarlo en una forma integrable.")
    if name == "CompleteSquareRule":
        return ("Completar el cuadrado", "Se escribe el polinomio cuadrático como (x + p)² + q para reconocer una integral inmediata.")
    if name == "TrigSubstitutionRule":
        return (
            "Sustitución trigonométrica",
            f"El radical se elimina con {x} = {sympy.sstr(rule.func)} (θ = {sympy.sstr(rule.theta)}); "
            "se integra en θ y se vuelve a la variable original con un triángulo rectángulo.",
        )
    if name == "ExpRule":
        return ("Integral exponencial", "∫ aᵘ du = aᵘ / ln(a) + C; con a = e queda ∫ eᵘ du = eᵘ + C.")
    if name == "SinRule":
        return ("Integral del seno", "∫ sin(u) du = −cos(u) + C, porque la derivada de −cos(u) es sin(u).")
    if name == "CosRule":
        return ("Integral del coseno", "∫ cos(u) du = sin(u) + C.")
    if name == "Sec2Rule":
        return ("Integral de sec²", "∫ sec²(u) du = tan(u) + C.")
    if name == "Csc2Rule":
        return ("Integral de csc²", "∫ csc²(u) du = −cot(u) + C.")
    if name == "SecTanRule":
        return ("Integral de sec·tan", "∫ sec(u)·tan(u) du = sec(u) + C.")
    if name == "CscCotRule":
        return ("Integral de csc·cot", "∫ csc(u)·cot(u) du = −csc(u) + C.")
    if name == "SinhRule":
        return ("Integral del seno hiperbólico", "∫ sinh(u) du = cosh(u) + C.")
    if name == "CoshRule":
        return ("Integral del coseno hiperbólico", "∫ cosh(u) du = sinh(u) + C.")
    if name == "ArctanRule":
        return ("Integral inmediata: arcotangente", "∫ 1/(a² + u²) du = (1/a)·arctan(u/a) + C.")
    if name == "ArcsinRule":
        return ("Integral inmediata: arcoseno", "∫ 1/√(1 − u²) du = arcsin(u) + C.")
    if name in ("SqrtQuadraticRule", "ReciprocalSqrtQuadraticRule", "SqrtQuadraticDenomRule"):
        return ("Integral con raíz de un cuadrático", "Se reconoce una forma tabulada de ∫ √(a + bx + cx²).")
    if name == "DontKnowRule":
        return (
            "Primitiva por algoritmo general",
            "No hay una regla de libro para este integrando; SymPy obtiene la primitiva con un algoritmo "
            "general (Risch/Meijer G). Se muestra el resultado y su comprobación al derivar.",
        )
    return (f"Regla «{name}»", "Regla de integración aplicada por SymPy.")


# ── Construcción del árbol ───────────────────────────────────────────────────

def _node(rule: mi.Rule, ids: IdGenerator) -> StepNode:
    rule = _resolve(rule)
    name = type(rule).__name__
    nid = ids.next()
    x = rule.variable
    f = rule.integrand
    F = _antiderivative(rule)
    title, explanation = _texts(rule)
    if ids.exhausted:
        return StepNode(nid, name, title, explanation + " (Desglose resumido: el árbol es muy grande.)",
                        rf"{_integral_latex(f, x)} = {latex(F)}")

    children: list[StepNode] = []
    tags: dict[sympy.Basic, str] = {}

    if name == "AddRule":
        for sub in rule.substeps:
            child = _node(sub, ids)
            children.append(child)
            tags[_resolve(sub).integrand] = child.id
    elif name == "ConstantTimesRule":
        child = _node(rule.substep, ids)
        children.append(child)
        tags[rule.other] = child.id
    elif name == "URule":
        u_sym = sympy.Symbol("u")
        u_func = rule.u_func
        du = sympy.diff(u_func, x)
        change = StepNode(
            ids.next(), "ChangeOfVariable", "Cambio de variable",
            f"Derivando u = {sympy.sstr(u_func)} se obtiene du = ({sympy.sstr(du)}) d{x}.",
            rf"u = {latex(u_func)} \quad\Rightarrow\quad du = {latex(du)}\, d{latex(x)}",
        )
        children.append(change)
        tags[u_func] = change.id
        x_of_u = _solve_for_var(u_func, x, u_sym)
        if x_of_u is not None and _needs_inverse(f, u_func, x):
            dx = sympy.diff(x_of_u, u_sym)
            children.append(StepNode(
                ids.next(), "SolveForVariable", f"Despejar {x} en términos de u",
                f"El integrando tiene factores con {x} fuera de u; se despeja {x} = {sympy.sstr(x_of_u)} "
                f"y d{x} = ({sympy.sstr(dx)}) du para reemplazarlos.",
                rf"{latex(x)} = {latex(x_of_u)} \quad\Rightarrow\quad d{latex(x)} = {latex(dx)}\, du",
            ))
        inner = rule.substep
        inner_named = inner.integrand.subs(rule.u_var, u_sym) if hasattr(inner, "integrand") else None
        sub_node = _node(inner, ids)
        if inner_named is not None:
            F_u = _antiderivative(_resolve(inner)).subs(rule.u_var, u_sym)
            sub_node = StepNode(
                sub_node.id, sub_node.rule, f"Integral en u: {sub_node.title.lower()}", sub_node.explanation,
                f"{_integral_latex(inner_named, u_sym)} = {latex(F_u)}",
                sub_node.children,
            )
        children.append(sub_node)
        children.append(StepNode(
            ids.next(), "BackSubstitution", "Volver a la variable original",
            f"Se reemplaza u por {sympy.sstr(u_func)}.",
            rf"{latex(F)}",
        ))
    elif name == "PartsRule":
        u, dv = rule.u, rule.dv
        du = sympy.diff(u, x)
        v = _antiderivative(_resolve(rule.v_step))
        choose = StepNode(
            ids.next(), "PartsChoice", "Elegir u y dv",
            "u se deriva y dv se integra.",
            rf"u = {latex(u)},\quad du = {latex(du)}\, d{latex(x)} \qquad dv = {latex(dv)}\, d{latex(x)},\quad v = {latex(v)}",
        )
        children.append(choose)
        tags[u] = choose.id
        v_node = _node(rule.v_step, ids)
        children.append(StepNode(v_node.id, v_node.rule, f"Calcular v = ∫ dv: {v_node.title.lower()}",
                                 v_node.explanation, v_node.latex, v_node.children))
        tags[dv] = v_node.id
        formula = StepNode(
            ids.next(), "PartsFormula", "Aplicar la fórmula de partes",
            "u·v − ∫ v du.",
            rf"{_integral_latex(f, x)} = {latex(u * v)} - {_integral_latex(sympy.expand(v * du), x)}",
        )
        children.append(formula)
        if rule.second_step is not None:
            children.append(_node(rule.second_step, ids))
    elif name == "CyclicPartsRule":
        # Las PartsRule internas no traen integrando (SymPy las deja en None): se reconstruye cada
        # paso a mano. g es la integral pendiente; tras dos partes vuelve a aparecer f.
        g = f
        for k, part in enumerate(rule.parts_rules, start=1):
            u, dv = part.u, part.dv
            v = _antiderivative(_resolve(part.v_step))
            du = sympy.diff(u, x)
            pending = sympy.expand(v * du)
            children.append(StepNode(
                ids.next(), "PartsRule", f"Partes, vez {k}",
                f"u = {sympy.sstr(u)} (du = {sympy.sstr(du)} d{x}) y dv = {sympy.sstr(dv)} d{x} (v = {sympy.sstr(v)}).",
                rf"{_integral_latex(g, x)} = {latex(u * v)} - {_integral_latex(pending, x)}",
            ))
            g = pending
        c = rule.coefficient
        rest = sympy.expand(F * (1 - c))
        sign = "+" if c > 0 else "-"
        children.append(StepNode(
            ids.next(), "CyclicSolve", "Despejar la integral",
            f"Llamando I a la integral original, queda I = (…) {sign} {sympy.sstr(abs(c))}·I; "
            "se pasa ese término al otro lado y se despeja I como una incógnita.",
            rf"I = {latex(rest)} {sign} {latex(abs(c)) if abs(c) != 1 else ''}I"
            rf" \;\Rightarrow\; I = {latex(F)}",
        ))
    elif name == "RewriteRule":
        rewrite = StepNode(
            ids.next(), "Rewrite", "Identidad usada",
            "Ambas expresiones son iguales para todo valor de la variable.",
            rf"{latex(f)} = {latex(rule.rewritten)}",
        )
        children.append(rewrite)
        tags[f] = rewrite.id
        children.append(_node(rule.substep, ids))
    elif name in ("CompleteSquareRule", "TrigSubstitutionRule"):
        rewritten = getattr(rule, "rewritten", None)
        if rewritten is not None:
            children.append(StepNode(ids.next(), "Rewrite", "Integrando transformado", "", latex(rewritten)))
        if getattr(rule, "substep", None) is not None:
            children.append(_node(rule.substep, ids))
    else:
        for sub in _children_rules(rule):
            children.append(_node(sub, ids))

    head = rf"{_integral_latex(f, x, tags)} = {latex(F)}"
    return StepNode(nid, name, title, explanation, head, tuple(children))


def build_integral_tree(integrand: sympy.Expr, var: sympy.Symbol, ids: IdGenerator | None = None) -> StepNode:
    """Árbol de pasos de la primitiva de ``integrand`` respecto a ``var``."""
    ids = ids or IdGenerator()
    rule = integral_rule(integrand, var)
    if rule is not None:
        return _node(rule, ids)
    F = sympy.integrate(integrand, var)
    title, explanation = _texts(mi.DontKnowRule(integrand, var))
    return StepNode(ids.next(), "DontKnowRule", title, explanation, rf"{_integral_latex(integrand, var)} = {latex(F)}")


# ── Resumen para el paso «Técnica de integración» ────────────────────────────

_GENERAL_FORMULAS: dict[str, str] = {
    "parts": r"\int u \, dv = uv - \int v \, du",
    "trig": r"\sqrt{a^2 - u^2} \;\Rightarrow\; u = a\sin\theta \qquad \sqrt{a^2 + u^2} \;\Rightarrow\; u = a\tan\theta"
            r" \qquad \sqrt{u^2 - a^2} \;\Rightarrow\; u = a\sec\theta",
    "power": r"\int x^n \, dx = \frac{x^{n+1}}{n+1} + C \qquad (n \neq -1)",
    "general": r"F'(x) = f(x)",
}


def describe_technique(integrand: sympy.Expr, var: sympy.Symbol) -> tuple[str, str, str]:
    """(título, explicación, LaTeX) de la técnica principal, según las reglas de SymPy."""
    rule = integral_rule(sympy.expand(integrand), var)
    if rule is None:
        return (
            "Técnica de integración: Algoritmo general de SymPy",
            "El integrando no corresponde a una regla de libro o es demasiado grande para desglosarlo; "
            "la primitiva se obtiene con el algoritmo general de SymPy y se comprueba derivando.",
            _GENERAL_FORMULAS["general"],
        )
    names = _rule_names(rule)
    resolved = [_resolve(r) for r in _walk_rules(rule)]
    # Una sustitución lineal (u = 2x, u = x + 3) es un detalle, no la técnica principal: sin²(x) se
    # resuelve con una identidad aunque luego aparezca u = 2x dentro de cos(2x).
    u_rules = [r for r in resolved if type(r).__name__ == "URule"]
    main_u = [r for r in u_rules if not _is_linear(r.u_func, var)]
    if not main_u and u_rules:
        names = [n for n in names if n != "URule"]
    if "PartsRule" in names or "CyclicPartsRule" in names:
        part = next(r for r in resolved if type(r).__name__ in ("PartsRule",)) if "PartsRule" in names else None
        detail = (
            f" Aquí u = {sympy.sstr(part.u)} y dv = {sympy.sstr(part.dv)} d{var}." if part is not None else ""
        )
        return (
            "Técnica de integración: Integración por partes",
            "El integrando es un producto en el que un factor se simplifica al derivarlo y el otro se sabe "
            "integrar: es la regla del producto aplicada al revés, eligiendo u con el orden LIATE." + detail,
            _GENERAL_FORMULAS["parts"],
        )
    if "TrigSubstitutionRule" in names:
        return (
            "Técnica de integración: Sustitución trigonométrica",
            "El integrando contiene un radical de la forma √(a² ± u²) o √(u² − a²); un cambio trigonométrico lo elimina.",
            _GENERAL_FORMULAS["trig"],
        )
    if main_u:
        sub = main_u[0]
        du = sympy.diff(sub.u_func, var)
        return (
            "Técnica de integración: Sustitución (regla de la cadena al revés)",
            f"Aparece una función compuesta junto a la derivada de su argumento: con u = {sympy.sstr(sub.u_func)} "
            f"se tiene du = ({sympy.sstr(du)}) d{var} y la integral se vuelve inmediata.",
            rf"\int f(g(x))\,g'(x)\,dx = \int f(u)\,du \qquad u = {latex(sub.u_func)},\; du = {latex(du)}\,dx",
        )
    if any(n in names for n in ("SqrtQuadraticRule", "ReciprocalSqrtQuadraticRule", "SqrtQuadraticDenomRule")):
        return (
            "Técnica de integración: Raíz de un polinomio cuadrático",
            "El integrando contiene √(a + bx + cx²). Se resuelve con la fórmula tabulada, que equivale a "
            "completar el cuadrado y aplicar una sustitución trigonométrica.",
            _GENERAL_FORMULAS["trig"],
        )
    if "ArctanRule" in names or "ArcsinRule" in names:
        return (
            "Técnica de integración: Integral inmediata (función trigonométrica inversa)",
            "El integrando coincide con la derivada de arctan o arcsin, salvo constantes.",
            r"\int \frac{du}{a^2 + u^2} = \frac{1}{a}\arctan\frac{u}{a} + C \qquad \int \frac{du}{\sqrt{1 - u^2}} = \arcsin u + C",
        )
    if "RewriteRule" in names:
        return (
            "Técnica de integración: Identidad y reescritura",
            "Se reescribe el integrando con una identidad algebraica o trigonométrica antes de integrar término a término.",
            r"\sin^2 u = \frac{1 - \cos 2u}{2} \qquad \cos^2 u = \frac{1 + \cos 2u}{2}",
        )
    if "DontKnowRule" in names:
        return (
            "Técnica de integración: Algoritmo general de SymPy",
            "Una parte del integrando no tiene regla de libro; SymPy la resuelve con su algoritmo general.",
            _GENERAL_FORMULAS["general"],
        )
    if u_rules:
        sub = u_rules[0]
        return (
            "Técnica de integración: Integral inmediata con sustitución lineal",
            f"El argumento es lineal (u = {sympy.sstr(sub.u_func)}): la integral es inmediata dividiendo "
            "entre la derivada constante del argumento.",
            r"\int f(ax + b)\,dx = \frac{1}{a} F(ax + b) + C",
        )
    if any(n in names for n in ("ExpRule", "SinRule", "CosRule", "Sec2Rule", "SinhRule", "CoshRule", "ReciprocalRule")):
        return (
            "Técnica de integración: Integrales inmediatas",
            "Cada término es la derivada conocida de una función elemental (exponencial, trigonométrica o logaritmo).",
            r"\int e^u\,du = e^u + C \qquad \int \sin u\,du = -\cos u + C \qquad \int \frac{du}{u} = \ln|u| + C",
        )
    return (
        "Técnica de integración: Regla de la potencia",
        "El integrando es una suma de potencias de la variable (con coeficientes constantes): "
        "se integra término a término con la regla de la potencia.",
        _GENERAL_FORMULAS["power"],
    )


def _solve_for_var(u_func: sympy.Expr, x: sympy.Symbol, u_sym: sympy.Symbol) -> sympy.Expr | None:
    """x = g(u) si ``u = u_func`` tiene una única solución sencilla; si no, ``None``."""
    try:
        sols = sympy.solve(sympy.Eq(u_sym, u_func), x)
    except Exception:  # noqa: BLE001
        return None
    return sols[0] if len(sols) == 1 and sympy.count_ops(sols[0]) < 40 else None


def _needs_inverse(f: sympy.Expr, u_func: sympy.Expr, x: sympy.Symbol) -> bool:
    """¿Quedan apariciones de x que no se explican con u y du? (p. ej. x·√(x + 1) con u = √(x + 1))."""
    du = sympy.diff(u_func, x)
    u_tmp = sympy.Dummy("u")
    rest = sympy.simplify(f / du).subs(u_func, u_tmp) if du != 0 else f
    return rest.has(x)


def _is_linear(expr: sympy.Expr, var: sympy.Symbol) -> bool:
    try:
        return sympy.Poly(expr, var).degree() <= 1
    except sympy.PolynomialError:
        return False


def _walk_rules(rule: mi.Rule) -> list[mi.Rule]:
    out: list[mi.Rule] = []
    stack = [rule]
    while stack:
        current = _resolve(stack.pop())
        out.append(current)
        stack.extend(_children_rules(current))
    return out


def technique_name(integrand: sympy.Expr, var: sympy.Symbol) -> str:
    """Nombre corto de la técnica, para la explicación de la primitiva."""
    return describe_technique(integrand, var)[0].removeprefix("Técnica de integración: ")

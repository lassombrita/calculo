"""Árbol de pasos de un volumen de revolución (discos, arandelas, casquillos y franjas).

Responsabilidad:
Armar el desglose completo que muestra la pestaña «Desarrollo» en modo interactivo:

1. Planteamiento (radios o radio y altura, con su significado geométrico).
2. Desarrollo algebraico del integrando (binomios clicables).
3. Primitiva (árbol de reglas de integración de SymPy).
4. Comprobación de la primitiva derivándola (reglas de la cadena y del producto).
5. Evaluación con el Teorema Fundamental del Cálculo.
6. Resultado.

Cuando el volumen se calcula por tramos (curvas que se cruzan) o por franjas horizontales
(integración en dy), cada tramo es un nodo con ese mismo desglose y un nodo final suma los
volúmenes parciales.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import sympy

from integrallab.core.steps.algebra import build_expansion_tree
from integrallab.core.steps.derivative import build_derivative_tree
from integrallab.core.steps.integral import antiderivative, build_integral_tree
from integrallab.core.steps.latex import latex, wrap_class
from integrallab.core.steps.model import IdGenerator, StepNode

__all__ = ["Piece", "RadiusInfo", "build_volume_tree"]


@dataclass(frozen=True)
class RadiusInfo:
    """Un radio (o la altura de un casquillo) y cómo se obtiene geométricamente."""

    name: str              # «R(x)», «r(x)», «p(x)», «h(x)»
    expr: sympy.Expr
    meaning: str           # explicación geométrica en texto plano


@dataclass(frozen=True)
class Piece:
    """Un tramo del volumen: ∫_{t0}^{t1} factor · core d(var)."""

    t0: sympy.Expr
    t1: sympy.Expr
    core: sympy.Expr               # integrando sin el factor π o 2π
    radii: tuple[RadiusInfo, ...]
    setup_latex: str               # integrando «armado», p. ej. «\left[R\right]^2 - \left[r\right]^2»
    label: str = ""                # «y ∈ [0, 1]: de x = 1 a x = 2», para tramos y franjas


def _piece_children(
    piece: Piece,
    var: sympy.Symbol,
    factor: sympy.Expr,
    method_label: str,
    ids: IdGenerator,
) -> tuple[list[StepNode], sympy.Expr]:
    """Pasos de un tramo y su valor (sin el factor)."""
    d = latex(var)
    radius_nodes = [
        StepNode(ids.next(), "Radius", info.name, info.meaning, rf"{info.name} = {latex(info.expr)}")
        for info in piece.radii
    ]
    setup_formula = piece.setup_latex
    for info, node in zip(piece.radii, radius_nodes):
        setup_formula = setup_formula.replace(f"@{info.name}@", wrap_class(node.id, latex(info.expr)))
    setup = StepNode(
        ids.next(), "Setup", "Planteamiento",
        f"{method_label}. Toca cada radio para ver de dónde sale.",
        rf"V = {latex(factor)}\int_{{{latex(piece.t0)}}}^{{{latex(piece.t1)}}} {setup_formula}\, d{d}",
        tuple(radius_nodes),
    )

    expansion = build_expansion_tree(piece.core, ids)
    expanded = sympy.expand(piece.core)

    primitive_tree = build_integral_tree(expanded, var, ids)
    F = antiderivative(expanded, var)  # la misma F que muestra el árbol de reglas
    verification = build_derivative_tree(F, var, ids)
    check_ok = sympy.simplify(sympy.diff(F, var) - expanded) == 0
    verify = StepNode(
        ids.next(), "Verification", "Comprobación: derivar la primitiva",
        ("Al derivar F se recupera exactamente el integrando, así que la primitiva es correcta."
         if check_ok else "Advertencia: la derivada de F no coincide simbólicamente con el integrando."),
        _verification_latex(F, var, expanded, verification.id),
        (verification,),
    )
    integrate_node = StepNode(
        ids.next(), "Antiderivative", "Primitiva",
        "Toca la integral para ver qué regla se aplica en cada término.",
        f"F({d}) = " + wrap_class(primitive_tree.id, rf"\int {_paren(expanded)}\, d{d}") + f" = {latex(F)}",
        (primitive_tree, verify),
    )

    F_b = sympy.simplify(F.subs(var, piece.t1))
    F_a = sympy.simplify(F.subs(var, piece.t0))
    value = sympy.simplify(F_b - F_a)
    eval_b = StepNode(ids.next(), "Evaluate", f"Evaluar F en {sympy.sstr(piece.t1)}",
                      f"Se reemplaza {var} por el límite superior.",
                      rf"F({latex(piece.t1)}) = {latex(F_b)}")
    eval_a = StepNode(ids.next(), "Evaluate", f"Evaluar F en {sympy.sstr(piece.t0)}",
                      f"Se reemplaza {var} por el límite inferior.",
                      rf"F({latex(piece.t0)}) = {latex(F_a)}")
    tfc = StepNode(
        ids.next(), "FundamentalTheorem", "Teorema Fundamental del Cálculo",
        "La integral definida es la primitiva evaluada en el límite superior menos la evaluada en el inferior.",
        rf"\int_{{{latex(piece.t0)}}}^{{{latex(piece.t1)}}} {_paren(expanded)}\, d{d} = "
        + wrap_class(eval_b.id, f"F({latex(piece.t1)})") + " - " + wrap_class(eval_a.id, f"F({latex(piece.t0)})")
        + rf" = {latex(value)}",
        (eval_b, eval_a),
    )
    nodes = [setup]
    if expansion.children:
        nodes.append(expansion)
    nodes.extend([integrate_node, tfc])
    return nodes, value


def _verification_latex(F: sympy.Expr, var: sympy.Symbol, integrand: sympy.Expr, node_id: str) -> str:
    d = latex(var)
    dF = sympy.diff(F, var)
    head = rf"F'({d}) = " + wrap_class(node_id, rf"\frac{{d}}{{d{d}}}\left[{latex(F)}\right]")
    if latex(dF) == latex(integrand):
        return rf"{head} = {latex(integrand)}"
    return rf"{head} = {latex(dF)} = {latex(integrand)}"


def _paren(expr: sympy.Expr) -> str:
    return rf"\left({latex(expr)}\right)" if isinstance(expr, sympy.Add) else latex(expr)


def build_volume_tree(
    *,
    method_label: str,
    var: sympy.Symbol,
    factor: sympy.Expr,
    pieces: Sequence[Piece],
    volume: sympy.Expr,
    numeric_value: float | None,
    preface: Sequence[StepNode] = (),
    ids: IdGenerator | None = None,
) -> StepNode:
    """Árbol completo del volumen. ``preface`` permite anteponer pasos (p. ej. el despeje a dy)."""
    ids = ids or IdGenerator()
    root_id = ids.next()
    approx = rf" \approx {numeric_value:.5f}" if numeric_value is not None else ""
    children: list[StepNode] = list(preface)

    if len(pieces) == 1:
        nodes, value = _piece_children(pieces[0], var, factor, method_label, ids)
        children.extend(nodes)
        children.append(StepNode(
            ids.next(), "Result", "Volumen",
            f"Se multiplica el resultado de la integral por {sympy.sstr(factor)}.",
            rf"V = {latex(factor)}\cdot\left({latex(value)}\right) = {latex(volume)}{approx}",
        ))
    else:
        partial_ids: list[str] = []
        partial_values: list[sympy.Expr] = []
        for k, piece in enumerate(pieces, start=1):
            nodes, value = _piece_children(piece, var, factor, method_label, ids)
            vk = sympy.simplify(factor * value)
            node = StepNode(
                ids.next(), "Piece", f"Tramo {k}: {piece.label}" if piece.label else f"Tramo {k}",
                "En este tramo la misma curva queda siempre por fuera (o arriba), así que el integrando no cambia.",
                rf"V_{{{k}}} = {latex(vk)}",
                tuple(nodes),
            )
            children.append(node)
            partial_ids.append(node.id)
            partial_values.append(vk)
        terms = " + ".join(wrap_class(pid, rf"V_{{{k}}}") for k, pid in enumerate(partial_ids, start=1))
        children.append(StepNode(
            ids.next(), "Result", "Volumen total",
            "El volumen total es la suma de los volúmenes de los tramos.",
            rf"V = {terms} = {' + '.join(latex(v) for v in partial_values)} = {latex(volume)}{approx}",
        ))

    return StepNode(
        root_id, "Volume", "Desarrollo del volumen",
        "Toca cualquier parte resaltada de una fórmula para desplegar cómo se obtuvo.",
        rf"V = {latex(volume)}{approx}",
        tuple(children),
    )

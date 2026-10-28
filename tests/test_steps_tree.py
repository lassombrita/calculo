"""Árbol de pasos del desglose interactivo (``integrallab.core.steps``).

Comprueba el rigor del desarrollo, no solo su forma:
- cada ancla ``\\class{step-ID}`` de una fórmula apunta a un paso que existe dentro de su rama;
- ningún paso contiene integrales sin resolver (``Integral(``) ni partes reales ``re(``;
- la primitiva de cada árbol de integral, derivada, devuelve el integrando;
- las reglas elegidas son las de un libro de texto (partes, sustitución, identidad...).
"""

from __future__ import annotations

import pickle

import pytest
import sympy

from integrallab.core.parser import parse_math_expression
from integrallab.core.solids import Region2D, RevolutionAxis, SolidMethod, calculate_revolution_volume
from integrallab.core.steps import (
    MAX_TREE_NODES,
    IdGenerator,
    antiderivative,
    StepNode,
    build_derivative_tree,
    build_expansion_tree,
    build_factor_tree,
    build_integral_tree,
    class_targets,
    describe_technique,
    tagged_latex,
)

x = sympy.Symbol("x")


def _assert_well_formed(tree: StepNode) -> None:
    ids = [n.id for n in tree.walk()]
    assert len(ids) == len(set(ids)), "identificadores repetidos"
    for node in tree.walk():
        assert node.title
        for target in class_targets(node.latex):
            assert tree.find(target) is not None, f"{node.id} apunta a {target}, que no existe"
        text = node.latex + node.explanation
        assert "Integral(" not in text
        assert "re(" not in text and "operatorname{re}" not in text
    assert pickle.loads(pickle.dumps(tree)) == tree  # viaja por la tubería del proceso de cálculo


INTEGRANDS = [
    x * sympy.sqrt(x + 1), x * sympy.exp(x), sympy.sin(x) ** 2, sympy.exp(x) * sympy.sin(x),
    1 / (1 + x**2), sympy.log(x), x**4 + 2 * x**2, x / (x**2 + 1), sympy.exp(2 * x),
    sympy.cbrt(x) ** 2, 2 * x * (x**2 + 1) ** 3, x**2 * sympy.cos(x), 3 * sympy.exp(2 * x),
]


@pytest.mark.parametrize("integrand", INTEGRANDS, ids=str)
def test_integral_tree_is_well_formed_and_correct(integrand: sympy.Expr) -> None:
    tree = build_integral_tree(integrand, x)
    _assert_well_formed(tree)
    # La fórmula raíz es «∫ f dx = F», con la F del árbol de reglas: derivada, devuelve f.
    F = antiderivative(integrand, x)
    assert sympy.simplify(sympy.diff(F, x) - integrand) == 0
    assert tree.latex.endswith(sympy.latex(F, ln_notation=True, inv_trig_style="full"))


@pytest.mark.parametrize(
    ("integrand", "expected"),
    [
        (sympy.sin(x) ** 2, "Identidad"),
        (3 * sympy.exp(2 * x), "sustitución lineal"),
        (x * sympy.sqrt(x + 1), "Sustitución"),
        (sympy.pi * sympy.sin(x), "inmediatas"),
        (1 / (1 + x**2), "trigonométrica inversa"),
        (x / (x**2 + 1), "Sustitución"),
        (sympy.log(x), "partes"),
        (x * sympy.exp(x), "partes"),
        (x**2 * sympy.cos(x), "partes"),
        (sympy.sqrt(1 - x**2), "cuadrático"),
        ((2 * x + 1) ** 3, "potencia"),
    ],
    ids=str,
)
def test_technique_follows_sympy_rules(integrand: sympy.Expr, expected: str) -> None:
    """Los 11 integrandos de la auditoría: la heurística antigua acertaba 4."""
    title, explanation, latex = describe_technique(integrand, x)
    assert title.startswith("Técnica de integración:")
    assert expected.lower() in title.lower()
    assert explanation and latex


def test_substitution_shows_change_of_variable_and_inverse() -> None:
    tree = build_integral_tree(x * sympy.sqrt(x + 1), x)
    rules = [n.rule for n in tree.walk()]
    assert "ChangeOfVariable" in rules
    assert "SolveForVariable" in rules  # x = u² − 1, dx = 2u du
    assert "BackSubstitution" in rules


def test_cyclic_parts_are_rebuilt_without_none_integrands() -> None:
    tree = build_integral_tree(sympy.exp(x) * sympy.sin(x), x)
    rules = [n.rule for n in tree.walk()]
    assert rules.count("PartsRule") == 2 and "CyclicSolve" in rules
    assert "None" not in " ".join(n.latex for n in tree.walk())


@pytest.mark.parametrize(
    ("expr", "rule"),
    [
        (x**2 * sympy.sin(x), "ProductRule"),
        (sympy.exp(x**2), "ChainRule"),
        (sympy.log(sympy.sin(x)), "ChainRule"),
        ((x**2 + 1) ** 3, "ChainRule"),
        (x / (x + 1), "QuotientRule"),
    ],
    ids=str,
)
def test_derivative_tree_applies_the_textbook_rule(expr: sympy.Expr, rule: str) -> None:
    tree = build_derivative_tree(expr, x)
    _assert_well_formed(tree)
    assert tree.rule == rule
    assert tree.latex.endswith(sympy.latex(sympy.diff(expr, x), ln_notation=True, inv_trig_style="full"))


def test_chain_rule_child_explains_the_inner_function() -> None:
    tree = build_derivative_tree(sympy.exp(x**2), x)
    inner = tree.children[0]
    assert inner.rule == "PowerRule" and "2 x" in inner.latex


def test_expansion_tree_marks_each_binomial() -> None:
    tree = build_expansion_tree((x**2 + 1) ** 2 - 1)
    _assert_well_formed(tree)
    square = next(n for n in tree.walk() if n.rule == "BinomialSquare")
    assert f"step-{square.id}" in tree.latex
    assert tree.latex.endswith("x^{4} + 2 x^{2}")


def test_factor_tree() -> None:
    tree = build_factor_tree(2 * x**3 - 2 * x, x)
    _assert_well_formed(tree)
    assert tree.children[0].rule == "CommonFactor"


def test_repeated_subexpressions_are_not_tagged() -> None:
    """En x·eˣ la x también está en el exponente: no se marca (tocarla abriría el paso equivocado)."""
    assert "class" not in tagged_latex(x * sympy.exp(x), {x: "s9"})
    assert "step-s9" in tagged_latex(x * sympy.sin(x) + 1, {sympy.sin(x): "s9"})


def test_id_generator_caps_tree_size() -> None:
    ids = IdGenerator()
    for _ in range(MAX_TREE_NODES):
        ids.next()
    assert ids.exhausted
    tree = build_integral_tree(sympy.Add(*(x**k for k in range(1, 60))), x, ids)
    assert tree.count() < 10  # resumido en lugar de crecer sin límite


VOLUMES = [
    ("x**2", None, "0", "1", RevolutionAxis.x_axis(), SolidMethod.DISKS),
    ("sqrt(x)", "x**2", "0", "1", RevolutionAxis.x_axis(), SolidMethod.WASHERS),
    ("x**2", None, "0", "1", RevolutionAxis.y_axis(), SolidMethod.SHELLS),
    ("sin(x)", None, "0", "pi", RevolutionAxis.y_axis(), SolidMethod.SHELLS),
    ("x", None, "0", "1", RevolutionAxis.vertical(2), SolidMethod.SHELLS),
    ("exp(x)", None, "0", "1", RevolutionAxis.x_axis(), SolidMethod.DISKS),
    ("x", "x**2", "0", "2", RevolutionAxis.x_axis(), SolidMethod.WASHERS),
    ("x**3", None, "0", "1", RevolutionAxis.y_axis(), SolidMethod.DISKS),
    ("4 - x**2", None, "1", "2", RevolutionAxis.y_axis(), SolidMethod.DISKS),
    ("cbrt(x)", None, "-1", "1", RevolutionAxis.x_axis(), SolidMethod.DISKS),
]


@pytest.mark.parametrize(("f", "g", "a", "b", "axis", "method"), VOLUMES)
def test_volume_tree_is_rigorous(f, g, a, b, axis, method) -> None:
    region = Region2D(parse_math_expression(f), parse_math_expression(g) if g else None, a, b)
    res = calculate_revolution_volume(region, axis, method)
    assert res.is_success, res.error_message
    tree = res.step_tree
    assert tree is not None
    _assert_well_formed(tree)
    rules = {n.rule for n in tree.walk()}
    assert {"Setup", "Antiderivative", "Verification", "FundamentalTheorem"} <= rules
    for node in tree.walk():  # cada «Comprobación» confirma la primitiva
        if node.rule == "Verification":
            assert node.explanation.startswith("Al derivar F se recupera exactamente el integrando")
    flat = " ".join(s.expression_plain_text + s.expression_latex for s in res.steps)
    assert "Integral(" not in flat and "re(" not in flat


def test_shell_radius_has_no_absolute_value() -> None:
    """Eje x = 2 a la derecha de [0, 1]: p(x) = 2 − x, no (x − 2) ni |x − 2|."""
    res = calculate_revolution_volume(Region2D("x", None, 0, 1), RevolutionAxis.vertical(2), SolidMethod.SHELLS)
    assert res.steps[0].expression_plain_text.startswith("p(x) = 2 - x")
    assert "Abs" not in " ".join(s.expression_plain_text for s in res.steps)
    assert res.numeric_value == pytest.approx(4 * sympy.pi.evalf() / 3)


def test_user_absolute_value_is_kept_and_split() -> None:
    """|x − 1| que escribe el usuario no se borra: se resuelve por tramos (antes _clean_latex lo quitaba)."""
    res = calculate_revolution_volume(Region2D("abs(x - 1) + 1", None, 0, 2), RevolutionAxis.x_axis(), SolidMethod.DISKS)
    assert res.is_success
    radii = [s for s in res.steps if "Radios en cada tramo" in s.title][0].expression_plain_text
    assert "2 - x" in radii and "x" in radii  # 1 − (x − 1) en [0, 1] y x en [1, 2]
    exact = sympy.pi * (sympy.integrate((2 - x) ** 2, (x, 0, 1)) + sympy.integrate(x**2, (x, 1, 2)))
    assert res.numeric_value == pytest.approx(float(exact))

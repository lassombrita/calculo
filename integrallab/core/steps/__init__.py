"""Desglose paso a paso interactivo («estilo Photomath»).

El cálculo produce un árbol de ``StepNode``: cada nodo tiene un título, una explicación en
texto plano, una fórmula LaTeX y sus subpasos. Las partes de una fórmula que tienen su propio
desarrollo van envueltas en ``\\class{step-<id>}{…}``; la vista web (MathJax 3 sin conexión,
``integrallab/ui/views/steps_view.py``) las vuelve clicables y despliega el subpaso debajo.

Módulos:

- ``model``       — ``StepNode``, ``IdGenerator`` (límite de nodos) y ``class_targets``.
- ``latex``       — impresor LaTeX de SymPy que etiqueta subexpresiones.
- ``integral``    — árbol de una integral a partir de las reglas de ``sympy.integrals.manualintegrate``.
- ``derivative``  — árbol de una derivada (suma, producto, cociente, cadena).
- ``algebra``     — desarrollo de binomios y productos; factorización.
- ``volume``      — árbol completo de un volumen de revolución.

Todo el paquete es puro (sin Qt) y sus nodos son inmutables y serializables con ``pickle``,
para viajar del proceso de cálculo a la interfaz.
"""

from integrallab.core.steps.algebra import build_expansion_tree, build_factor_tree
from integrallab.core.steps.derivative import build_derivative_tree
from integrallab.core.steps.integral import (
    antiderivative,
    build_integral_tree,
    describe_technique,
    integral_rule,
    technique_name,
)
from integrallab.core.steps.latex import latex, tagged_latex, wrap_class
from integrallab.core.steps.model import MAX_TREE_NODES, IdGenerator, StepNode, class_targets
from integrallab.core.steps.volume import Piece, RadiusInfo, build_volume_tree

__all__ = [
    "MAX_TREE_NODES",
    "IdGenerator",
    "Piece",
    "antiderivative",
    "RadiusInfo",
    "StepNode",
    "build_derivative_tree",
    "build_expansion_tree",
    "build_factor_tree",
    "build_integral_tree",
    "build_volume_tree",
    "class_targets",
    "describe_technique",
    "integral_rule",
    "latex",
    "tagged_latex",
    "technique_name",
    "wrap_class",
]

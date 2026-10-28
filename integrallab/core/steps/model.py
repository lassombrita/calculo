"""Modelo del desglose interactivo de pasos (estilo Photomath).

Responsabilidad:
Representar el desarrollo de un cálculo como un ÁRBOL de pasos, no como una lista de textos.
Cada nodo tiene una fórmula LaTeX y, opcionalmente, hijos que explican cómo se obtuvo. Dentro
de la fórmula de un nodo, la subexpresión que explica un hijo va envuelta en
``\\class{step-<id del hijo>}{...}`` (macro de la extensión ``html`` de MathJax): la interfaz
la vuelve «clicable» y, al tocarla, despliega ese hijo debajo de la tarjeta.

Este módulo es puro: no importa Qt ni SymPy, y el árbol es inmutable y serializable (viaja
por la tubería del proceso de cálculo y por ``QWebChannel`` como JSON).
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

__all__ = ["MAX_TREE_NODES", "IdGenerator", "StepNode", "class_targets"]

# Tope de nodos por árbol: integrandos enormes (splines, sumas de 40 términos) producirían
# árboles ilegibles y JSON de varios MB. Por encima del tope, los nodos se resumen.
MAX_TREE_NODES = 400

_CLASS_TARGET = re.compile(r"\\class\{step-([A-Za-z0-9_-]+)\}")


@dataclass
class IdGenerator:
    """Identificadores cortos y deterministas (``s1``, ``s2``…) para los nodos de un árbol."""

    prefix: str = "s"
    _counter: Iterator[int] = field(default_factory=lambda: itertools.count(1))
    issued: int = 0

    def next(self) -> str:
        self.issued += 1
        return f"{self.prefix}{next(self._counter)}"

    @property
    def exhausted(self) -> bool:
        return self.issued >= MAX_TREE_NODES


@dataclass(frozen=True)
class StepNode:
    """Un paso del desarrollo.

    Atributos:
        id: Identificador único dentro del árbol (``s1``…); coincide con ``step-<id>`` en el LaTeX
            del padre cuando el paso explica una subexpresión concreta.
        rule: Nombre estable de la regla aplicada (``PowerRule``, ``ChainRule``, ``Setup``…).
        title: Título corto para la tarjeta.
        explanation: Explicación en lenguaje natural (texto plano, sin HTML).
        latex: Fórmula del paso, sin delimitadores ``$``.
        children: Pasos que explican cómo se llegó a esta fórmula.
    """

    id: str
    rule: str
    title: str
    explanation: str = ""
    latex: str = ""
    children: tuple[StepNode, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Estructura JSON para la vista (``StepsView``)."""
        return {
            "id": self.id,
            "rule": self.rule,
            "title": self.title,
            "explanation": self.explanation,
            "latex": self.latex,
            "children": [child.to_dict() for child in self.children],
        }

    def walk(self) -> Iterator[StepNode]:
        """Recorre el árbol en preorden (iterativo: no depende del límite de recursión)."""
        stack: list[StepNode] = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def count(self) -> int:
        return sum(1 for _ in self.walk())

    def find(self, node_id: str) -> StepNode | None:
        return next((n for n in self.walk() if n.id == node_id), None)


def class_targets(latex: str) -> list[str]:
    """Identificadores ``step-<id>`` que aparecen en una fórmula (para validar el árbol)."""
    return _CLASS_TARGET.findall(latex)

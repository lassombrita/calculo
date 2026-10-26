"""LaTeX con anclas clicables para el desglose interactivo.

``tagged_latex(expr, {subexpresión: id})`` imprime ``expr`` con SymPy y envuelve cada
subexpresión indicada en ``\\class{step-<id>}{...}``. MathJax (extensión ``html``) convierte esa
macro en un atributo ``class`` del nodo SVG, que la página usa para saber qué paso desplegar.

Se reemplaza el impresor de SymPy en lugar de buscar y reemplazar texto: la subexpresión se
reconoce por su árbol, no por cómo se imprime, así que el orden de los términos o los
paréntesis que SymPy añade no rompen las anclas.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import sympy
from sympy.printing.latex import LatexPrinter

__all__ = ["TaggingLatexPrinter", "latex", "tagged_latex", "wrap_class"]

_SETTINGS: dict[str, Any] = {"ln_notation": True, "inv_trig_style": "full"}


class TaggingLatexPrinter(LatexPrinter):
    """Impresor LaTeX de SymPy que marca subexpresiones con ``\\class{step-ID}{…}``."""

    def __init__(self, tags: Mapping[sympy.Basic, str], settings: dict[str, Any] | None = None) -> None:
        super().__init__({**_SETTINGS, **(settings or {})})
        self._tags = dict(tags)

    def _print(self, expr: Any, **kwargs: Any) -> str:  # noqa: D102
        out = super()._print(expr, **kwargs)
        if isinstance(expr, sympy.Basic):
            tag = self._tags.get(expr)
            if tag:
                return wrap_class(tag, out)
        return out


def wrap_class(node_id: str, latex_src: str) -> str:
    """Envuelve un fragmento LaTeX para que sea clicable y abra el paso ``node_id``."""
    return rf"\class{{step-{node_id}}}{{{latex_src}}}"


def latex(expr: Any) -> str:
    """LaTeX con las convenciones del desglose: ``ln`` para el logaritmo natural y ``arcsin``."""
    return sympy.latex(expr, **_SETTINGS)


def tagged_latex(expr: Any, tags: Mapping[sympy.Basic, str]) -> str:
    """LaTeX de ``expr`` con anclas para las subexpresiones de ``tags``.

    Solo se marca una subexpresión que aparece **una vez** en ``expr``: en ``x·eˣ`` la ``x``
    también está en el exponente, y marcar las dos apariciones haría que tocar el exponente
    abriera el paso de «u = x». Los pasos sin ancla siguen accesibles desde la lista de subpasos.
    """
    if not tags or not isinstance(expr, sympy.Basic):
        return latex(expr)
    counts = Counter(sympy.preorder_traversal(expr))
    safe = {sub: tag for sub, tag in tags.items() if counts.get(sub, 0) == 1}
    if not safe:
        return latex(expr)
    return TaggingLatexPrinter(safe).doprint(expr)

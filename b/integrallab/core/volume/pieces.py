"""Tramos de signo constante para integrar sin valores absolutos ni ramas complejas.

Responsabilidad:
Un radio, una altura o un integrando pueden contener ``|u|`` (escrito por el usuario o
porque la distancia al eje cambia de signo) y raíces impares como ``∛x``, que SymPy evalúa con
la rama principal (compleja) cuando la base es negativa. Partiendo el intervalo en los ceros de
esas subexpresiones, en cada tramo el signo es constante y se puede escribir:

- ``|u|`` como ``u`` o ``−u``;
- ``u^(p/q)`` con ``q`` impar y ``u < 0`` como ``(−1)^p · (−u)^(p/q)``, que es la raíz real.

Así la primitiva del desarrollo es una función elemental (no ``Integral(...)`` ni ``re(x)``) y el
valor coincide con la gráfica, que siempre usó la raíz real.
"""

from __future__ import annotations

import logging

import numpy as np
import sympy

from integrallab.core.sampling import REAL_EVAL_MODULES, prepare_expr_for_real_eval

__all__ = ["is_odd_root", "real_branch", "real_root_form", "sample", "sign_cut_points", "sign_on"]

logger = logging.getLogger(__name__)

_SCAN = 2001          # muestras para buscar cambios de signo
_SIGN_SAMPLES = 201   # muestras interiores para decidir el signo en un tramo
_EDGE_EPS = 1e-9


def sample(expr: sympy.Expr, var: sympy.Symbol, ts: np.ndarray) -> np.ndarray | None:
    """Valores reales de ``expr`` en ``ts`` (raíz impar real; ``nan`` fuera del dominio)."""
    try:
        fn = sympy.lambdify(var, prepare_expr_for_real_eval(expr), modules=REAL_EVAL_MODULES)
        with np.errstate(all="ignore"):
            values = np.asarray(fn(ts))
        if np.iscomplexobj(values):
            ok = np.abs(values.imag) < 1e-9 * np.maximum(1.0, np.abs(values.real))
            values = np.where(ok, values.real, np.nan)
        values = values.astype(float)
        if values.ndim == 0:
            values = np.full(ts.shape, float(values))
        return values
    except Exception:  # noqa: BLE001 - funciones que lambdify no traduce
        return None


def is_odd_root(e: sympy.Basic) -> bool:
    """``u^(p/q)`` con ``q`` impar y exponente no entero (∛u, u^(2/3), u^(-1/3)...)."""
    return (
        isinstance(e, sympy.Pow)
        and e.exp.is_Rational
        and not e.exp.is_Integer
        and int(e.exp.q) % 2 == 1
        and e.base.free_symbols != set()
    )


def sign_on(expr: sympy.Expr, var: sympy.Symbol, t0: float, t1: float) -> int | None:
    """+1 o −1 si ``expr`` no cambia de signo en (t0, t1); ``None`` si cambia o no se sabe."""
    if expr.free_symbols == set():
        value = complex(expr.evalf())
        return 1 if value.real >= 0 else -1
    ts = np.linspace(t0, t1, _SIGN_SAMPLES)[1:-1]
    vals = sample(expr, var, ts)
    if vals is None:
        return None
    vals = vals[np.isfinite(vals)]
    if not vals.size:
        return None
    tol = 1e-12 * max(1.0, float(np.max(np.abs(vals))))
    if np.all(vals >= -tol):
        return 1
    if np.all(vals <= tol):
        return -1
    return None


def _subexpressions(exprs: tuple[sympy.Expr, ...]) -> list[sympy.Expr]:
    """Argumentos de ``Abs`` y bases de raíces impares que dependen de la variable."""
    found: list[sympy.Expr] = []
    for expr in exprs:
        for sub in sympy.preorder_traversal(expr):
            if isinstance(sub, sympy.Abs):
                found.append(sub.args[0])
            elif is_odd_root(sub):
                found.append(sub.base)
    unique: list[sympy.Expr] = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return unique


def _exact_root(expr: sympy.Expr, var: sympy.Symbol, approx: float) -> sympy.Expr:
    """Raíz exacta de ``expr`` cercana a ``approx`` si SymPy la encuentra; si no, la aproximada."""
    if sympy.count_ops(expr) <= 40:
        try:
            for sol in sympy.solve(sympy.Eq(expr, 0), var):
                value = complex(sympy.N(sol))
                if abs(value.imag) < 1e-9 and abs(value.real - approx) < 1e-7 * max(1.0, abs(approx)):
                    return sympy.nsimplify(sol)
        except Exception:  # noqa: BLE001 - solve no siempre puede
            logger.debug("solve no encontró la raíz de %s", expr, exc_info=True)
    exact = sympy.nsimplify(approx, [sympy.pi], tolerance=1e-10)
    if abs(float(exact) - approx) < 1e-10 * max(1.0, abs(approx)):
        return exact
    return sympy.Float(approx, 15)


def roots_by_sign_change(expr: sympy.Expr, var: sympy.Symbol, num_a: float, num_b: float) -> list[float]:
    """Raíces interiores de ``expr`` donde cambia de signo (barrido + bisección)."""
    ts = np.linspace(num_a, num_b, _SCAN)
    vals = sample(expr, var, ts)
    if vals is None:
        return []
    fn = sympy.lambdify(var, prepare_expr_for_real_eval(expr), modules=REAL_EVAL_MODULES)

    def h(t: float) -> float:
        with np.errstate(all="ignore"):
            v = complex(fn(t))
        return v.real if abs(v.imag) < 1e-12 else float("nan")

    roots: list[float] = []
    finite = np.isfinite(vals)

    def add(candidate: float) -> None:
        if num_a + _EDGE_EPS < candidate < num_b - _EDGE_EPS and not any(abs(candidate - r) < 1e-9 for r in roots):
            roots.append(candidate)

    for i in range(len(ts) - 1):
        if not (finite[i] and finite[i + 1]):
            continue
        lo_v, hi_v = vals[i], vals[i + 1]
        if lo_v * hi_v < 0:
            lo, hi = float(ts[i]), float(ts[i + 1])
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                hm = h(mid)
                if not np.isfinite(hm):
                    break
                if (hm < 0) == (lo_v < 0):
                    lo, lo_v = mid, hm
                else:
                    hi = mid
            add(0.5 * (lo + hi))
        elif lo_v == 0.0 and 0 < i and finite[i - 1] and vals[i - 1] * hi_v < 0:
            # Cero exacto en una muestra con cambio de signo alrededor. Un cero sin cambio de
            # signo (x² en 0) no parte el tramo: ningún signo cambia ahí.
            add(float(ts[i]))
    return sorted(roots)


def sign_cut_points(
    exprs: tuple[sympy.Expr, ...],
    var: sympy.Symbol,
    num_a: float,
    num_b: float,
    extra: tuple[sympy.Expr, ...] = (),
) -> list[tuple[float, sympy.Expr]]:
    """Puntos interiores donde cambia el signo de un ``|u|``, de la base de una raíz impar o de
    alguna expresión de ``extra`` (p. ej. la distancia ``f − k`` al eje). Valores exactos si se puede."""
    cuts: list[tuple[float, sympy.Expr]] = []
    for sub in [*_subexpressions(exprs), *extra]:
        if sub.free_symbols != {var}:
            continue
        for approx in roots_by_sign_change(sub, var, num_a, num_b):
            if not any(abs(approx - c) < 1e-7 for c, _ in cuts):
                cuts.append((approx, _exact_root(sub, var, approx)))
    cuts.sort(key=lambda item: item[0])
    return cuts


def real_branch(expr: sympy.Expr, var: sympy.Symbol, t0: float, t1: float) -> sympy.Expr:
    """``expr`` en un tramo de signo constante, sin ``Abs`` ni raíces impares de bases negativas.

    Si algún signo cambia dentro del tramo (no debería, si se partió con ``sign_cut_points``),
    esa subexpresión se deja como estaba.
    """
    def fix(e: sympy.Expr) -> sympy.Expr:
        if isinstance(e, sympy.Abs):
            s = sign_on(e.args[0], var, t0, t1)
            if s is None:
                return e
            return e.args[0] if s > 0 else -e.args[0]
        if is_odd_root(e):
            s = sign_on(e.base, var, t0, t1)
            if s is not None and s < 0:
                return (-1) ** int(e.exp.p) * (-e.base) ** e.exp
        return e

    if not isinstance(expr, sympy.Basic):
        return expr
    return expr.replace(lambda e: isinstance(e, sympy.Abs) or is_odd_root(e), fix)


def real_root_form(expr: sympy.Expr) -> sympy.Expr:
    """``u^(p/q)`` con ``q`` impar → ``sign(u)^p · |u|^(p/q)``: la raíz real, válida en todo ℝ.

    Sirve para evaluar numéricamente (cuadratura con mpmath) la misma función que se dibuja; para
    el desarrollo simbólico se usa ``real_branch`` por tramos, que no deja ``sign`` ni ``Abs``.
    """
    if not isinstance(expr, sympy.Basic):
        return expr
    return expr.replace(
        is_odd_root, lambda e: sympy.sign(e.base) ** int(e.exp.p) * sympy.Abs(e.base) ** e.exp
    )

"""Franjas horizontales: integrar en ``dy`` una región dada en ``x`` (corrige el hallazgo A1).

Responsabilidad:
Describir la región ``R = {(x, y): a ≤ x ≤ b, mín(f, g) ≤ y ≤ máx(f, g)}`` como unión de franjas
horizontales ``y ∈ [y₀, y₁]`` donde la sección ``S(y) = {x ∈ [a, b] : (x, y) ∈ R}`` tiene siempre
la misma forma: uno o varios intervalos ``[x_izq(y), x_der(y)]`` cuyos bordes son la recta
``x = a``, la recta ``x = b`` o una rama despejada de ``f`` o de ``g``.

Algoritmo (sin adivinar la forma de la región):

1. Valores críticos de ``y``: ``f`` y ``g`` en los extremos, en sus extremos locales interiores y
   en los cruces ``f = g``. Ordenados, delimitan las franjas.
2. En el centro de cada franja se calcula numéricamente la sección (muestreo fino y bisección) y
   se etiqueta cada borde (recta o curva).
3. Cada borde curvo se despeja con ``sympy.solve(Eq(y, f(x)), x)`` y se elige la rama que vale lo
   mismo que el borde numérico; se comprueba en otros dos valores de ``y`` de la franja.
4. Franjas contiguas con los mismos bordes se unen.

Quien llama arma el integrando de cada franja (arandela o casquillo) y verifica el total contra la
cuadratura independiente ``numeric_volume``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import sympy

from integrallab.core.volume.pieces import roots_by_sign_change, sample

__all__ = ["Edge", "InversionFailed", "Strip", "horizontal_strips"]

logger = logging.getLogger(__name__)

_GRID = 4001
_MAX_STRIPS = 12


class InversionFailed(ValueError):
    """La región no se pudo describir por franjas horizontales con despejes exactos."""


@dataclass(frozen=True)
class Edge:
    """Borde de una sección horizontal: ``x = expr(y)``."""

    kind: str            # "a" | "b" (rectas verticales) | "f" | "g" (ramas despejadas)
    expr: sympy.Expr     # x en función de y

    def describe(self, var: str) -> str:
        names = {"a": "la recta", "b": "la recta", "f": "la curva f", "g": "la curva g"}
        return f"{names[self.kind]} {var} = {sympy.sstr(self.expr)}"


@dataclass(frozen=True)
class Strip:
    """Franja ``y ∈ [y0, y1]`` con su sección: intervalos ``(borde izquierdo, borde derecho)``."""

    y0_num: float
    y1_num: float
    y0: sympy.Expr
    y1: sympy.Expr
    intervals: tuple[tuple[Edge, Edge], ...]


def _exact(value: float, candidates: list[sympy.Expr]) -> sympy.Expr:
    for cand in candidates:
        try:
            if abs(float(sympy.N(cand)) - value) < 1e-9 * max(1.0, abs(value)):
                return sympy.nsimplify(cand) if cand.is_Float else sympy.simplify(cand)
        except (TypeError, ValueError):
            continue
    exact = sympy.nsimplify(value, [sympy.pi], tolerance=1e-10)
    return exact if abs(float(exact) - value) < 1e-10 * max(1.0, abs(value)) else sympy.Float(value, 15)


def _critical_values(
    curves: list[sympy.Expr],
    x: sympy.Symbol,
    num_a: float,
    num_b: float,
    sym_a: sympy.Expr,
    sym_b: sympy.Expr,
    crossings: list[tuple[float, sympy.Expr]],
) -> list[tuple[float, sympy.Expr]]:
    """(valor numérico, valor exacto) de y en extremos, extremos locales y cruces."""
    points: list[tuple[float, sympy.Expr]] = []
    xs_exact: list[tuple[float, sympy.Expr]] = [(num_a, sym_a), (num_b, sym_b), *crossings]
    for curve in curves:
        deriv = sympy.diff(curve, x)
        for approx in roots_by_sign_change(deriv, x, num_a, num_b):
            exact_x = None
            if sympy.count_ops(deriv) <= 40:
                try:
                    for sol in sympy.solve(sympy.Eq(deriv, 0), x):
                        v = complex(sympy.N(sol))
                        if abs(v.imag) < 1e-9 and abs(v.real - approx) < 1e-7:
                            exact_x = sol
                            break
                except Exception:  # noqa: BLE001
                    exact_x = None
            xs_exact.append((approx, exact_x if exact_x is not None else sympy.Float(approx, 15)))
    for curve in curves:
        for xv, xe in xs_exact:
            vals = sample(curve, x, np.array([xv]))
            if vals is None or not np.isfinite(vals[0]):
                continue
            yv = float(vals[0])
            if any(abs(yv - p) < 1e-9 * max(1.0, abs(yv)) for p, _ in points):
                continue
            try:
                ye = sympy.simplify(curve.subs(x, xe))
            except Exception:  # noqa: BLE001
                ye = sympy.Float(yv, 15)
            points.append((yv, _exact(yv, [ye])))
    points.sort(key=lambda item: item[0])
    return points


def _section(
    f_vals: np.ndarray,
    g_vals: np.ndarray,
    xs: np.ndarray,
    y: float,
    f: sympy.Expr,
    g: sympy.Expr,
    x: sympy.Symbol,
) -> list[tuple[tuple[str, float], tuple[str, float]]]:
    """Intervalos de S(y) con el tipo de cada borde: ("a"|"b"|"f"|"g", x numérico)."""
    hi = np.maximum(f_vals, g_vals)
    lo = np.minimum(f_vals, g_vals)
    tol = 1e-12 * max(1.0, abs(y))
    inside = (lo <= y + tol) & (y - tol <= hi) & np.isfinite(hi) & np.isfinite(lo)
    out: list[tuple[tuple[str, float], tuple[str, float]]] = []
    n = len(xs)
    i = 0
    while i < n:
        if not inside[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and inside[j + 1]:
            j += 1
        left = ("a", float(xs[0])) if i == 0 else _refine(f, g, f_vals, g_vals, xs, i - 1, i, y, x)
        right = ("b", float(xs[-1])) if j == n - 1 else _refine(f, g, f_vals, g_vals, xs, j, j + 1, y, x)
        if right[1] - left[1] > 1e-9:
            out.append((left, right))
        i = j + 1
    return out


def _refine(
    f: sympy.Expr,
    g: sympy.Expr,
    f_vals: np.ndarray,
    g_vals: np.ndarray,
    xs: np.ndarray,
    i: int,
    j: int,
    y: float,
    x: sympy.Symbol,
) -> tuple[str, float]:
    """Qué curva cruza el nivel y entre xs[i] y xs[j], y dónde (bisección)."""
    for name, expr, vals in (("f", f, f_vals), ("g", g, g_vals)):
        a_v, b_v = vals[i] - y, vals[j] - y
        if np.isfinite(a_v) and np.isfinite(b_v) and a_v * b_v <= 0:
            lo, hi = float(xs[i]), float(xs[j])
            for _ in range(70):
                mid = 0.5 * (lo + hi)
                mv = sample(expr, x, np.array([mid]))
                if mv is None or not np.isfinite(mv[0]):
                    break
                if (mv[0] - y) * a_v <= 0:
                    hi = mid
                else:
                    lo, a_v = mid, mv[0] - y
            return name, 0.5 * (lo + hi)
    raise InversionFailed("No se pudo identificar el borde de una franja horizontal.")


def _branch(curve: sympy.Expr, x: sympy.Symbol, y: sympy.Symbol, sols: list[sympy.Expr],
            y_test: float, x_target: float) -> sympy.Expr | None:
    best, best_err = None, float("inf")
    for sol in sols:
        try:
            v = complex(sympy.N(sol.subs(y, y_test)))
        except (TypeError, ValueError):
            continue
        if abs(v.imag) > 1e-8 * max(1.0, abs(v.real)):
            continue
        err = abs(v.real - x_target)
        if err < best_err:
            best, best_err = sol, err
    return best if best is not None and best_err < 1e-6 * max(1.0, abs(x_target)) else None


def _realify(branch: sympy.Expr, y: sympy.Symbol, y0: float, y1: float) -> sympy.Expr:
    """Escribe sin unidades imaginarias una rama que es real en la franja.

    ``solve(y = x³)`` da la raíz real de un y negativo como ``−y^(1/3)/2 + √3·i·y^(1/3)/2``
    (rama principal compleja). Con ``y = −s`` y ``s > 0`` SymPy la simplifica a ``−s^(1/3)``,
    es decir ``−(−y)^(1/3)``: la misma raíz real que dibuja la gráfica.
    """
    if not branch.has(sympy.I):
        return branch
    s = sympy.Symbol("s", positive=True)
    sign = -1 if y1 <= 0 else 1 if y0 >= 0 else 0
    if sign == 0:
        return branch
    candidate = sympy.simplify(sympy.expand_complex(branch.subs(y, sign * s)))
    if candidate.has(sympy.I):
        return branch
    return candidate.subs(s, sign * y)


def horizontal_strips(
    f: sympy.Expr,
    g: sympy.Expr,
    x: sympy.Symbol,
    y: sympy.Symbol,
    num_a: float,
    num_b: float,
    sym_a: sympy.Expr,
    sym_b: sympy.Expr,
    crossings: list[tuple[float, sympy.Expr]],
) -> list[Strip]:
    """Describe la región entre ``f`` y ``g`` en ``[a, b]`` por franjas horizontales.

    Raises:
        InversionFailed: si un borde curvo no se puede despejar de forma exacta o la región es
            demasiado compleja (más de ``_MAX_STRIPS`` franjas).
    """
    xs = np.linspace(num_a, num_b, _GRID)
    f_vals = sample(f, x, xs)
    g_vals = sample(g, x, xs)
    if f_vals is None or g_vals is None or not (np.all(np.isfinite(f_vals)) and np.all(np.isfinite(g_vals))):
        raise InversionFailed("Las curvas no son reales y finitas en todo el intervalo.")

    curves = [c for c in (f, g) if c.has(x)]
    levels = _critical_values([f, g], x, num_a, num_b, sym_a, sym_b, crossings)
    if len(levels) < 2:
        raise InversionFailed("La región no tiene altura: no hay franjas horizontales.")

    solutions: dict[str, list[sympy.Expr]] = {}
    for name, curve in (("f", f), ("g", g)):
        if curve not in curves:
            continue
        try:
            solutions[name] = list(sympy.solve(sympy.Eq(y, curve), x))
        except Exception as exc:  # noqa: BLE001
            raise InversionFailed(f"No se pudo despejar {x} en y = {curve}: {exc}") from exc

    strips: list[Strip] = []
    for (y0n, y0e), (y1n, y1e) in zip(levels, levels[1:]):
        if y1n - y0n < 1e-12:
            continue
        y_mid = 0.5 * (y0n + y1n)
        section = _section(f_vals, g_vals, xs, y_mid, f, g, x)
        if not section:
            continue
        intervals: list[tuple[Edge, Edge]] = []
        for left, right in section:
            edges = []
            for kind, x_num in (left, right):
                if kind in ("a", "b"):
                    edges.append(Edge(kind, sym_a if kind == "a" else sym_b))
                    continue
                curve = f if kind == "f" else g
                branch = _branch(curve, x, y, solutions.get(kind, []), y_mid, x_num)
                if branch is None:
                    raise InversionFailed(
                        f"No se encontró una rama real de {x} en y = {sympy.sstr(curve)} para y ∈ "
                        f"[{y0n:.4g}, {y1n:.4g}]."
                    )
                for frac in (0.25, 0.75):
                    y_q = y0n + frac * (y1n - y0n)
                    sec_q = _section(f_vals, g_vals, xs, y_q, f, g, x)
                    xs_q = [e[1] for pair in sec_q for e in pair if e[0] == kind]
                    v = complex(sympy.N(branch.subs(y, y_q)))
                    if not xs_q or min(abs(v.real - xq) for xq in xs_q) > 1e-6 * max(1.0, abs(v.real)):
                        raise InversionFailed("La rama despejada no describe toda la franja.")
                edges.append(Edge(kind, _realify(sympy.simplify(branch), y, y0n, y1n)))
            intervals.append((edges[0], edges[1]))
        strip = Strip(y0n, y1n, y0e, y1e, tuple(intervals))
        if strips and strips[-1].intervals == strip.intervals and abs(strips[-1].y1_num - y0n) < 1e-12:
            prev = strips[-1]
            strips[-1] = Strip(prev.y0_num, y1n, prev.y0, y1e, prev.intervals)
        else:
            strips.append(strip)
    if not strips:
        raise InversionFailed("No se encontraron franjas horizontales con área.")
    if len(strips) > _MAX_STRIPS:
        raise InversionFailed("La región necesita demasiadas franjas horizontales; use el método directo.")
    return strips

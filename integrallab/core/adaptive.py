"""Muestreo adaptativo de curvas y(x) y reparto de nodos a lo largo de un perfil.

Responsabilidad:
Generar puntos de una función real de modo que la curva se vea suave y fiel sin
necesidad de una malla uniforme enorme, y colocar los nodos de la malla de un sólido
de revolución donde el perfil realmente cambia. NumPy puro: no depende de SymPy,
Matplotlib ni Qt, así que se puede probar de forma aislada.

La estrategia está inspirada en cómo trazan curvas los graficadores interactivos
(p. ej. GeoGebra): se parte de una malla uniforme y se bisecan los tramos cuyos
extremos quedan demasiado lejos en pantalla o forman un ángulo demasiado cerrado con
el tramo vecino; los puntos indefinidos se acotan por bisección y las asíntotas
cortan la línea en lugar de unirla con un trazo vertical. Es una implementación
propia en NumPy; no se copia código de ningún otro proyecto.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np

# Función escalar que devuelve nan cuando el punto no está definido.
ScalarFunc = Callable[[float], float]

# Un salto mayor que esta fracción de la altura de la ventana corta la línea.
_JUMP_WINDOWS: float = 2.0
# Los tramos más cortos que esto (en píxeles virtuales) no se refinan por ángulo.
_MIN_ANGLE_SEGMENT_PX: float = 1.0


def suggest_y_window(
    y_values: Sequence[float] | np.ndarray,
    margin: float = 0.2,
) -> tuple[float, float]:
    """Estima una ventana vertical razonable ignorando valores extremos.

    Usa los percentiles 5 y 95 de los valores finitos, de modo que unas pocas
    muestras gigantes cerca de una asíntota no dominen la escala.

    Returns:
        (y_bajo, y_alto) con ``y_alto > y_bajo`` siempre.
    """
    arr = np.asarray(y_values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size < 2:
        return (-1.0, 1.0)
    low, high = np.percentile(finite, [5.0, 95.0])
    span = float(high - low)
    if span < 1e-12:
        center = float(low)
        return (center - 1.0, center + 1.0)
    pad = span * margin
    return (float(low - pad), float(high + pad))


def outlier_clip_window(
    y_arrays: Sequence[Sequence[float] | np.ndarray],
    factor: float = 8.0,
) -> tuple[float, float] | None:
    """Devuelve una ventana vertical si hay valores extremos que arruinarían el autoajuste.

    Args:
        y_arrays: Valores y de una o varias curvas (pueden contener nan).
        factor: Cuántas veces puede exceder el rango real a la ventana robusta
            antes de considerar que hay valores extremos.

    Returns:
        ``(y_bajo, y_alto)`` para recortar la vista, o ``None`` si el autoajuste
        normal ya es adecuado.
    """
    if not y_arrays:
        return None
    merged = np.concatenate([np.asarray(a, dtype=float).ravel() for a in y_arrays])
    finite = merged[np.isfinite(merged)]
    if finite.size < 2:
        return None
    low, high = suggest_y_window(finite)
    robust_span = high - low
    real_span = float(finite.max() - finite.min())
    if real_span > factor * robust_span:
        return (low, high)
    return None


def _evaluate(func: ScalarFunc, xs: np.ndarray) -> np.ndarray:
    """Evalúa ``func`` punto a punto, convirtiendo cualquier fallo en nan."""
    out = np.empty(xs.size, dtype=float)
    for i, x in enumerate(xs):
        try:
            value = float(func(float(x)))
        except (ArithmeticError, ValueError, TypeError):
            value = math.nan
        out[i] = value if math.isfinite(value) else math.nan
    return out


def adaptive_samples(
    func: ScalarFunc,
    x_min: float,
    x_max: float,
    *,
    min_points: int = 80,
    y_window: tuple[float, float] | None = None,
    view_size: tuple[float, float] = (800.0, 500.0),
    max_pixel_step: float = 10.0,
    max_angle_deg: float = 10.0,
    max_depth: int = 10,
    undefined_depth: int = 8,
    max_points: int = 8000,
) -> tuple[np.ndarray, np.ndarray]:
    """Muestrea ``func`` en [x_min, x_max] refinando donde la curva lo necesita.

    Se evalúa primero una malla uniforme de ``min_points`` y se bisecan los tramos que:

    - dejan sus extremos a más de ``max_pixel_step`` píxeles virtuales (en x o en y), o
    - forman con un tramo vecino un ángulo mayor que ``max_angle_deg``, o
    - unen un punto definido con uno indefinido (se acota la frontera del dominio).

    Al final, los tramos que siguen saltando más de dos alturas de ventana (asíntotas,
    saltos) se cortan insertando un nan, para que no se dibuje un trazo vertical falso.

    Args:
        func: Función escalar; debe devolver nan (o lanzar un error aritmético) si
            el punto no está definido.
        x_min: Extremo izquierdo del dominio.
        x_max: Extremo derecho del dominio.
        min_points: Puntos de la malla uniforme inicial (al menos 2).
        y_window: Ventana vertical visible; si es None se estima con percentiles.
        view_size: Tamaño virtual de la vista en píxeles (ancho, alto).
        max_pixel_step: Distancia máxima entre puntos vecinos, en píxeles virtuales.
        max_angle_deg: Ángulo máximo entre tramos consecutivos.
        max_depth: Bisecciones máximas por tramo inicial en zonas definidas.
        undefined_depth: Bisecciones máximas para acotar fronteras de dominio.
        max_points: Tope duro de puntos devueltos.

    Returns:
        (xs, ys) como arreglos NumPy ordenados por x. ``ys`` puede contener nan.

    Raises:
        ValueError: Si ``x_min >= x_max`` o ``min_points < 2``.
    """
    if not x_min < x_max:
        raise ValueError("x_min debe ser estrictamente menor que x_max.")
    if min_points < 2:
        raise ValueError("min_points debe ser al menos 2.")

    xs = np.linspace(x_min, x_max, min_points)
    ys = _evaluate(func, xs)
    depth = np.zeros(xs.size - 1, dtype=int)

    y_low, y_high = y_window if y_window is not None else suggest_y_window(ys)
    if not y_high > y_low:
        y_low, y_high = y_low - 1.0, y_low + 1.0
    window_span = y_high - y_low
    scale_x = view_size[0] / (x_max - x_min)
    scale_y = view_size[1] / window_span
    tan_limit = math.tan(math.radians(max_angle_deg))
    min_dx = (x_max - x_min) * 1e-12

    while xs.size < max_points:
        px = xs * scale_x
        py = ys * scale_y
        dx = np.diff(px)
        dy = np.diff(py)
        finite = np.isfinite(ys)
        seg_finite = finite[:-1] & finite[1:]
        seg_mixed = finite[:-1] ^ finite[1:]

        with np.errstate(invalid="ignore"):
            # Tramos totalmente fuera de la vista (mismo lado, a más de una ventana de
            # distancia) no se refinan: no se ven y refinarlos solo gasta puntos.
            above = ys > y_high + window_span
            below = ys < y_low - window_span
            seg_off = (above[:-1] & above[1:]) | (below[:-1] & below[1:])
            seg_jump = seg_finite & (np.abs(np.diff(ys)) > _JUMP_WINDOWS * window_span)

            too_far = seg_finite & ~seg_off & (
                (np.abs(dx) > max_pixel_step) | (np.abs(dy) > max_pixel_step)
            )

            need = too_far.copy()

            # Ángulo entre el tramo k-1 y el tramo k (comparten el punto k).
            if dx.size >= 2:
                vx, vy = dx[:-1], dy[:-1]
                wx, wy = dx[1:], dy[1:]
                both_finite = seg_finite[:-1] & seg_finite[1:]
                dot = vx * wx + vy * wy
                det = np.abs(vx * wy - vy * wx)
                longest = np.maximum(
                    np.maximum(np.abs(vx), np.abs(vy)),
                    np.maximum(np.abs(wx), np.abs(wy)),
                )
                bent = both_finite & (longest > _MIN_ANGLE_SEGMENT_PX) & (
                    (dot <= 0.0) | (det >= tan_limit * dot)
                )
                need[:-1] |= bent & ~seg_off[:-1]
                need[1:] |= bent & ~seg_off[1:]

            # Fronteras del dominio: acotar el punto donde la función deja de existir.
            need |= seg_mixed

        # Fronteras y saltos candidatos a asíntota se acotan con menos bisecciones.
        limit = np.where(seg_mixed | seg_jump, undefined_depth, max_depth)
        gaps = np.diff(xs)
        need &= (depth < limit) & (gaps > min_dx)

        idx = np.flatnonzero(need)
        if idx.size == 0:
            break

        budget = max_points - xs.size
        if idx.size > budget:
            size = np.nan_to_num(np.hypot(dx, dy), nan=0.0, posinf=0.0)[idx]
            keep = np.argsort(-size)[:budget]
            idx = np.sort(idx[keep])
            if idx.size == 0:
                break

        mids = 0.5 * (xs[idx] + xs[idx + 1])
        mid_y = _evaluate(func, mids)
        xs = np.insert(xs, idx + 1, mids)
        ys = np.insert(ys, idx + 1, mid_y)

        counts = np.ones(depth.size, dtype=int)
        counts[idx] = 2
        depth = np.repeat(depth, counts)
        first = idx + np.arange(idx.size)
        depth[first] += 1
        depth[first + 1] += 1

    # Cortar la línea donde quedó un salto irresoluble (asíntotas, discontinuidades).
    finite = np.isfinite(ys)
    seg_finite = finite[:-1] & finite[1:]
    with np.errstate(invalid="ignore"):
        jump = seg_finite & (np.abs(np.diff(ys)) > _JUMP_WINDOWS * window_span)
    cut = np.flatnonzero(jump)
    if cut.size:
        mids = 0.5 * (xs[cut] + xs[cut + 1])
        xs = np.insert(xs, cut + 1, mids)
        ys = np.insert(ys, cut + 1, np.full(cut.size, math.nan))

    return xs, ys


def equidistributed_nodes(
    t_dense: Sequence[float] | np.ndarray,
    curves_dense: Sequence[Sequence[float] | np.ndarray],
    n: int,
    blend: float = 0.5,
) -> np.ndarray:
    """Reparte ``n`` nodos en [t_dense[0], t_dense[-1]] siguiendo la longitud de arco.

    Sirve para la malla de un sólido de revolución: el giro angular es exacto, así que
    solo hace falta densificar a lo largo del perfil. Los nodos se concentran donde las
    curvas de contorno cambian más y se conserva una parte uniforme (``blend``) para no
    dejar huecos en las zonas planas.

    Args:
        t_dense: Parámetros crecientes de una evaluación densa del perfil.
        curves_dense: Valores de cada curva de contorno sobre ``t_dense``.
        n: Cantidad exacta de nodos pedidos (al menos 2).
        blend: Peso de la longitud de arco frente al reparto uniforme, en [0, 1).

    Returns:
        Arreglo estrictamente creciente de ``n`` nodos que incluye ambos extremos.
        Si alguna curva tiene valores no finitos, devuelve un reparto uniforme.

    Raises:
        ValueError: Si ``n < 2``, ``blend`` está fuera de [0, 1) o ``t_dense`` es inválido.
    """
    t = np.asarray(t_dense, dtype=float)
    if n < 2:
        raise ValueError("n debe ser al menos 2.")
    if not 0.0 <= blend < 1.0:
        raise ValueError("blend debe estar en [0, 1).")
    if t.size < 2 or not np.all(np.diff(t) > 0):
        raise ValueError("t_dense debe tener al menos 2 valores estrictamente crecientes.")

    uniform = np.linspace(t[0], t[-1], n)
    t_span = t[-1] - t[0]
    dt = np.diff(t) / t_span

    density = np.zeros(t.size - 1)
    for curve in curves_dense:
        y = np.asarray(curve, dtype=float)
        if y.shape != t.shape or not np.all(np.isfinite(y)):
            return uniform
        span = float(np.ptp(y))
        if span < 1e-12:
            continue
        density += np.hypot(dt, np.diff(y) / span)

    if not np.any(density > 0.0):
        return uniform

    s_arc = np.concatenate(([0.0], np.cumsum(density)))
    s_arc /= s_arc[-1]
    s_uniform = (t - t[0]) / t_span
    s = blend * s_arc + (1.0 - blend) * s_uniform

    nodes = np.interp(np.linspace(0.0, 1.0, n), s, t)
    nodes[0], nodes[-1] = t[0], t[-1]
    return nodes

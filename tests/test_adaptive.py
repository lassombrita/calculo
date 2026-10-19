"""Pruebas del muestreo adaptativo y del reparto de nodos (NumPy puro, sin Qt ni SymPy)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from integrallab.core.adaptive import (
    adaptive_samples,
    equidistributed_nodes,
    outlier_clip_window,
    suggest_y_window,
)

_TAN_POLES = [
    math.pi / 2 + k * math.pi
    for k in range(-5, 5)
    if -10 < math.pi / 2 + k * math.pi < 10
]


# ── adaptive_samples ──────────────────────────────────────────────────────────

def test_adaptive_keeps_endpoints_and_strict_order() -> None:
    """Los extremos del dominio se conservan y x queda estrictamente creciente."""
    xs, ys = adaptive_samples(lambda x: x * x, -10.0, 10.0, min_points=400)

    assert xs[0] == -10.0
    assert xs[-1] == 10.0
    assert np.all(np.diff(xs) > 0)
    assert xs.shape == ys.shape
    assert not np.any(np.isnan(ys))


def test_adaptive_constant_function_stays_flat() -> None:
    """Una función constante no genera nan ni valores distintos."""
    _, ys = adaptive_samples(lambda x: 3.0, -10.0, 10.0, min_points=400)

    assert np.all(ys == 3.0)


def test_adaptive_resolves_fast_oscillation_better_than_uniform() -> None:
    """sin(50x) con la misma malla inicial: el error entre puntos baja de ~0.19 a <0.01."""
    xs, ys = adaptive_samples(lambda x: math.sin(50 * x), 0.0, 2.0, min_points=80)
    mid = 0.5 * (xs[:-1] + xs[1:])
    adaptive_err = float(np.max(np.abs(0.5 * (ys[:-1] + ys[1:]) - np.sin(50 * mid))))

    xu = np.linspace(0.0, 2.0, 80)
    yu = np.sin(50 * xu)
    mu = 0.5 * (xu[:-1] + xu[1:])
    uniform_err = float(np.max(np.abs(0.5 * (yu[:-1] + yu[1:]) - np.sin(50 * mu))))

    assert adaptive_err < 0.01
    assert uniform_err > 0.1


def test_adaptive_cuts_line_at_every_asymptote() -> None:
    """tan(x): hay nan junto a cada polo y ninguno lejos de ellos."""
    xs, ys = adaptive_samples(math.tan, -10.0, 10.0, min_points=400)

    assert len(_TAN_POLES) == 6
    for pole in _TAN_POLES:
        assert np.any(np.isnan(ys[np.abs(xs - pole) < 0.05])), f"sin corte en el polo {pole:.4f}"

    away = np.ones(xs.size, dtype=bool)
    for pole in _TAN_POLES:
        away &= np.abs(xs - pole) > 0.05
    assert not np.any(np.isnan(ys[away]))


def test_adaptive_curve_matches_function_away_from_asymptotes() -> None:
    """Los puntos devueltos son valores reales de la función (no se inventa nada)."""
    xs, ys = adaptive_samples(math.tan, -10.0, 10.0, min_points=400)
    finite = np.isfinite(ys) & (np.abs(ys) < 5.0)

    assert np.allclose(ys[finite], np.tan(xs[finite]))


def test_adaptive_does_not_waste_points_off_screen() -> None:
    """Los tramos muy fuera de la vista no se refinan hasta el máximo (antes: ~7800 puntos)."""
    xs, _ = adaptive_samples(math.tan, -10.0, 10.0, min_points=400)

    assert xs.size < 3000


def test_adaptive_refines_near_square_root_singularity() -> None:
    """sqrt(x) tiene pendiente infinita en 0: debe haber varios puntos muy cerca de 0."""
    xs, _ = adaptive_samples(math.sqrt, 0.0, 1.0, min_points=80)

    assert int(np.sum(xs <= 0.01)) >= 4


def test_adaptive_locates_domain_boundary() -> None:
    """sqrt en [-1, 1]: la frontera del dominio (x = 0) se acota con precisión."""
    xs, ys = adaptive_samples(math.sqrt, -1.0, 1.0, min_points=80)

    last_undefined = float(xs[np.isnan(ys)].max())
    first_defined = float(xs[np.isfinite(ys)].min())
    assert -1e-3 < last_undefined < 0.0
    assert first_defined < 1e-3


def test_adaptive_treats_arithmetic_errors_as_undefined() -> None:
    """1/x lanza ZeroDivisionError en 0: se interpreta como nan, no como excepción."""
    xs, ys = adaptive_samples(lambda x: 1.0 / x, -1.0, 1.0, min_points=3)

    assert xs.size >= 3
    assert np.any(np.isnan(ys))


def test_adaptive_respects_max_points() -> None:
    """El tope duro de puntos se respeta aunque la función sea extremadamente oscilante."""
    xs, _ = adaptive_samples(
        lambda x: math.sin(500 * x), 0.0, 5.0, min_points=80, max_points=300
    )

    assert xs.size <= 300


@pytest.mark.parametrize(
    ("x_min", "x_max", "min_points"),
    [(1.0, 1.0, 80), (2.0, 1.0, 80), (0.0, 1.0, 1)],
)
def test_adaptive_rejects_invalid_arguments(x_min: float, x_max: float, min_points: int) -> None:
    """Dominio vacío/invertido o malla inicial insuficiente lanzan ValueError."""
    with pytest.raises(ValueError):
        adaptive_samples(math.sin, x_min, x_max, min_points=min_points)


# ── ventanas verticales ───────────────────────────────────────────────────────

def test_suggest_y_window_ignores_extreme_values() -> None:
    """Unos pocos valores gigantes no deben dominar la ventana sugerida."""
    values = np.concatenate([np.linspace(-1.0, 1.0, 200), [1e9, -1e9]])

    low, high = suggest_y_window(values)

    assert low < -1.0 and high > 1.0
    assert high - low < 10.0


def test_suggest_y_window_degenerate_cases() -> None:
    """Constante o sin datos finitos devuelven una ventana válida (alto > bajo)."""
    low, high = suggest_y_window([2.0] * 10)
    assert (low, high) == (1.0, 3.0)

    assert suggest_y_window([math.nan, math.nan]) == (-1.0, 1.0)
    assert suggest_y_window([]) == (-1.0, 1.0)


def test_outlier_clip_window_for_asymptotic_curve() -> None:
    """Con asíntotas devuelve una ventana; con una parábola deja el autoajuste (None)."""
    _, tan_ys = adaptive_samples(math.tan, -10.0, 10.0, min_points=400)
    window = outlier_clip_window([tan_ys])

    assert window is not None
    assert window[1] - window[0] < 100.0

    assert outlier_clip_window([np.linspace(-10.0, 10.0, 400) ** 2]) is None


def test_outlier_clip_window_without_usable_data() -> None:
    """Sin curvas o sin valores finitos no hay ventana que sugerir."""
    assert outlier_clip_window([]) is None
    assert outlier_clip_window([[math.nan, math.nan]]) is None


# ── equidistributed_nodes ─────────────────────────────────────────────────────

def test_equidistributed_nodes_basic_contract() -> None:
    """Devuelve exactamente n nodos, con ambos extremos y estrictamente crecientes."""
    t = np.linspace(2.0, 5.0, 301)

    nodes = equidistributed_nodes(t, [np.exp(t)], 12)

    assert nodes.size == 12
    assert nodes[0] == 2.0
    assert nodes[-1] == 5.0
    assert np.all(np.diff(nodes) > 0)


def test_equidistributed_nodes_uniform_for_straight_line() -> None:
    """Una recta no necesita refinar: el reparto es uniforme."""
    t = np.linspace(0.0, 1.0, 401)

    nodes = equidistributed_nodes(t, [t], 18)

    assert np.allclose(nodes, np.linspace(0.0, 1.0, 18))


def test_equidistributed_nodes_concentrate_near_steep_start() -> None:
    """sqrt(x) es muy empinada cerca de 0: los primeros pasos son menores que los últimos."""
    t = np.linspace(0.0, 1.0, 401)

    steps = np.diff(equidistributed_nodes(t, [np.sqrt(t)], 18))
    uniform_step = 1.0 / 17.0

    # Con margen real: un reparto uniforme (todos los pasos iguales) no puede cumplirlo.
    assert steps[0] < 0.6 * steps[-1]
    assert steps.min() < 0.7 * uniform_step
    assert steps.max() > 1.1 * uniform_step


def test_equidistributed_nodes_ignores_constant_curves() -> None:
    """Una curva constante (g = 0) no aporta densidad ni rompe el reparto."""
    t = np.linspace(0.0, 1.0, 401)

    nodes = equidistributed_nodes(t, [np.sqrt(t), np.zeros_like(t)], 18)

    assert nodes.size == 18
    assert np.all(np.diff(nodes) > 0)


def test_equidistributed_nodes_falls_back_to_uniform() -> None:
    """Con valores no finitos, o todas las curvas constantes, el reparto es uniforme."""
    t = np.linspace(0.0, 1.0, 401)
    broken = np.sqrt(t)
    broken[5] = math.nan

    assert np.allclose(equidistributed_nodes(t, [broken], 18), np.linspace(0.0, 1.0, 18))
    assert np.allclose(
        equidistributed_nodes(t, [np.zeros_like(t)], 18), np.linspace(0.0, 1.0, 18)
    )


@pytest.mark.parametrize(
    "kwargs",
    [{"n": 1}, {"n": 5, "blend": 1.0}, {"n": 5, "blend": -0.1}],
)
def test_equidistributed_nodes_rejects_invalid_arguments(kwargs: dict[str, float]) -> None:
    """n < 2 o blend fuera de [0, 1) lanzan ValueError."""
    t = np.linspace(0.0, 1.0, 50)
    with pytest.raises(ValueError):
        equidistributed_nodes(t, [t], **kwargs)


def test_equidistributed_nodes_rejects_invalid_parameter_grid() -> None:
    """Una malla de parámetros con menos de 2 puntos o no creciente lanza ValueError."""
    with pytest.raises(ValueError):
        equidistributed_nodes([1.0], [[1.0]], 5)
    with pytest.raises(ValueError):
        equidistributed_nodes([0.0, 1.0, 1.0], [[0.0, 1.0, 2.0]], 5)

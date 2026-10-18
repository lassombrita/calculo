"""Pruebas unitarias para el motor matemático de sólidos de revolución.

Valida rigurosamente:
- Caso A: Discos (f(x)=x^2 en [0,1], eje X -> pi/5)
- Caso B: Arandelas (f(x)=sqrt(x), g(x)=x^2 en [0,1], eje X -> 3pi/10)
- Caso C: Casquillos (f(x)=x^2 en [0,1], eje Y -> pi/2)
- Caso D: Eje desplazado (y=x en [0,1], eje y=2 -> 5pi/3)
- Inversión del orden de curvas
- Integración en variable 'y'
- Detección de límites inválidos y funciones fuera de dominio
- Mallas 3D numéricas (dimensiones y finitud con NumPy)
- Recomendador explicable y detección de autointersecciones
"""

from __future__ import annotations

import math
import numpy as np
import pytest
import sympy

from integrallab.core.solids import (
    AxisOrientation,
    Region2D,
    RevolutionAxis,
    SolidMethod,
    calculate_disk_volume,
    calculate_revolution_volume,
    calculate_shell_volume,
    calculate_washer_volume,
    generate_solid_mesh,
    recommend_method,
)


# ─────────────────────────────────────────────────────────────────────────────
# Casos de Cálculo Obligatorios
# ─────────────────────────────────────────────────────────────────────────────

def test_case_a_disks_x_squared() -> None:
    """Caso A: f(x) = x^2, [0, 1], rotación en eje X (y = 0).

    V = pi * int_0^1 (x^2)^2 dx = pi * int_0^1 x^4 dx = pi / 5.
    """
    region = Region2D(f_expr="x^2", a=0, b=1, variable="x")
    axis = RevolutionAxis.x_axis()

    res = calculate_disk_volume(region, axis)

    assert res.is_success is True
    assert res.method == SolidMethod.DISKS
    assert res.numeric_value is not None
    assert math.isclose(res.numeric_value, math.pi / 5.0, rel_tol=1e-5)
    # Verificación simbólica exacta
    diff_sym = sympy.simplify(sympy.sympify(res.exact_plain_text) - sympy.pi / 5)
    assert diff_sym == 0


def test_case_b_washers_sqrt_and_x_squared() -> None:
    """Caso B: f(x) = sqrt(x), g(x) = x^2, [0, 1], rotación en eje X.

    V = pi * int_0^1 [(sqrt(x))^2 - (x^2)^2] dx = pi * int_0^1 (x - x^4) dx = 3pi / 10.
    """
    region = Region2D(f_expr="sqrt(x)", g_expr="x^2", a=0, b=1, variable="x")
    axis = RevolutionAxis.x_axis()

    res = calculate_washer_volume(region, axis)

    assert res.is_success is True
    assert res.method == SolidMethod.WASHERS
    assert res.numeric_value is not None
    assert math.isclose(res.numeric_value, 3.0 * math.pi / 10.0, rel_tol=1e-5)
    diff_sym = sympy.simplify(sympy.sympify(res.exact_plain_text) - 3 * sympy.pi / 10)
    assert diff_sym == 0


def test_case_c_shells_x_squared_y_axis() -> None:
    """Caso C: f(x) = x^2, [0, 1], rotación en eje Y (x = 0).

    V = 2pi * int_0^1 x * x^2 dx = 2pi * [x^4 / 4]_0^1 = pi / 2.
    """
    region = Region2D(f_expr="x^2", a=0, b=1, variable="x")
    axis = RevolutionAxis.y_axis()

    res = calculate_shell_volume(region, axis)

    assert res.is_success is True
    assert res.method == SolidMethod.SHELLS
    assert res.numeric_value is not None
    assert math.isclose(res.numeric_value, math.pi / 2.0, rel_tol=1e-5)
    diff_sym = sympy.simplify(sympy.sympify(res.exact_plain_text) - sympy.pi / 2)
    assert diff_sym == 0


def test_case_d_displaced_axis_y_equals_2() -> None:
    """Caso D: región bajo y = x, [0, 1], rotación en eje desplazado y = 2.

    R_ext = 2 - 0 = 2, R_int = 2 - x.
    V = pi * int_0^1 [2^2 - (2-x)^2] dx = pi * int_0^1 (4x - x^2) dx = 5pi / 3.
    """
    region = Region2D(f_expr="x", g_expr="0", a=0, b=1, variable="x")
    axis = RevolutionAxis.horizontal(2.0)

    res = calculate_washer_volume(region, axis)

    assert res.is_success is True
    assert res.numeric_value is not None
    assert math.isclose(res.numeric_value, 5.0 * math.pi / 3.0, rel_tol=1e-5)
    diff_sym = sympy.simplify(sympy.sympify(res.exact_plain_text) - 5 * sympy.pi / 3)
    assert diff_sym == 0


# ─────────────────────────────────────────────────────────────────────────────
# Robustez Geométrica y Manejo de Errores
# ─────────────────────────────────────────────────────────────────────────────

def test_reverse_curve_order_preserves_positive_volume() -> None:
    """Verifica que ingresar g(x) antes que f(x) no produzca un volumen negativo."""
    # Ingresando f(x)=x^2 primero y g(x)=sqrt(x) después
    region = Region2D(f_expr="x^2", g_expr="sqrt(x)", a=0, b=1, variable="x")
    axis = RevolutionAxis.x_axis()

    res = calculate_washer_volume(region, axis)

    assert res.is_success is True
    assert res.numeric_value is not None
    assert math.isclose(res.numeric_value, 3.0 * math.pi / 10.0, rel_tol=1e-5)


def test_variable_y_integration() -> None:
    """Verifica el cálculo cuando la variable independiente es 'y'."""
    # Región x = y^2 para y en [0, 1] girado alrededor del eje Y (x = 0)
    # Por discos en dy: V = pi * int_0^1 (y^2)^2 dy = pi / 5
    region = Region2D(f_expr="y^2", a=0, b=1, variable="y")
    axis = RevolutionAxis.y_axis()

    res = calculate_disk_volume(region, axis)

    assert res.is_success is True
    assert res.numeric_value is not None
    assert math.isclose(res.numeric_value, math.pi / 5.0, rel_tol=1e-5)


def test_invalid_bounds_rejected() -> None:
    """Verifica que límites invertidos o iguales retornen error sin lanzar excepción."""
    region_inverted = Region2D(f_expr="x", a=2, b=1)
    res1 = calculate_disk_volume(region_inverted, RevolutionAxis.x_axis())
    assert res1.is_success is False
    assert "menor que 'b'" in (res1.error_message or "")

    region_equal = Region2D(f_expr="x", a=1, b=1)
    res2 = calculate_disk_volume(region_equal, RevolutionAxis.x_axis())
    assert res2.is_success is False


def test_calculate_revolution_volume_dispatcher() -> None:
    """Verifica que la función general calculate_revolution_volume delegue correctamente."""
    region = Region2D(f_expr="x^2", a=0, b=1)
    res = calculate_revolution_volume(region, RevolutionAxis.x_axis(), method=SolidMethod.DISKS)
    assert res.is_success is True
    assert math.isclose(res.numeric_value or 0.0, math.pi / 5.0, rel_tol=1e-5)


# ─────────────────────────────────────────────────────────────────────────────
# Motor de Recomendación Explicable
# ─────────────────────────────────────────────────────────────────────────────

def test_recommend_method_disks() -> None:
    """Verifica que se recomiende discos para corte perpendicular macizo."""
    region = Region2D(f_expr="x^2", a=0, b=1)
    rec = recommend_method(region, RevolutionAxis.x_axis())

    assert rec.is_decidable is True
    assert rec.recommended_method == SolidMethod.DISKS
    assert "discos macizos" in rec.justification


def test_recommend_method_washers() -> None:
    """Verifica que se recomiende arandelas cuando hay espacio interior."""
    region = Region2D(f_expr="sqrt(x)", g_expr="x^2", a=0, b=1)
    rec = recommend_method(region, RevolutionAxis.x_axis())

    assert rec.is_decidable is True
    assert rec.recommended_method == SolidMethod.WASHERS
    assert "radio exterior y radio interior" in rec.justification


def test_recommend_method_shells() -> None:
    """Verifica que se recomiende casquillos para cortes paralelos al eje vertical."""
    region = Region2D(f_expr="x^2", a=0, b=1)
    rec = recommend_method(region, RevolutionAxis.y_axis())

    assert rec.is_decidable is True
    assert rec.recommended_method == SolidMethod.SHELLS
    assert "paralelos al eje" in rec.justification


def test_recommend_method_detects_self_intersection() -> None:
    """Verifica que un eje que corta el interior de la región sea declarado no decidible."""
    # Región entre y=0 y y=1, con eje horizontal y=0.5 (atraviesa el sólido)
    region = Region2D(f_expr="1", g_expr="0", a=0, b=2)
    axis_crossing = RevolutionAxis.horizontal(0.5)

    rec = recommend_method(region, axis_crossing)

    assert rec.is_decidable is False
    assert rec.recommended_method is None
    assert len(rec.limitations_or_warnings) > 0
    assert "atraviesa el interior" in rec.limitations_or_warnings[0]


# ─────────────────────────────────────────────────────────────────────────────
# Malla Numérica 3D (NumPy)
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_solid_mesh_dimensions_and_finiteness() -> None:
    """Verifica que generate_solid_mesh retorne matrices NumPy válidas con dimensiones esperadas."""
    region = Region2D(f_expr="x^2", a=0, b=1)
    axis = RevolutionAxis.x_axis()

    mesh = generate_solid_mesh(region, axis, num_radial=24, num_axial=20)

    assert mesh.is_valid is True
    assert isinstance(mesh.x_outer, np.ndarray)
    assert isinstance(mesh.y_outer, np.ndarray)
    assert isinstance(mesh.z_outer, np.ndarray)
    assert mesh.x_outer.shape == (20, 24)
    assert mesh.y_outer.shape == (20, 24)
    assert mesh.z_outer.shape == (20, 24)
    # Todos los valores deben ser números reales finitos
    assert np.all(np.isfinite(mesh.x_outer))
    assert np.all(np.isfinite(mesh.y_outer))
    assert np.all(np.isfinite(mesh.z_outer))


def test_generate_solid_mesh_with_inner_void() -> None:
    """Verifica que una arandela genere tanto la superficie exterior como la interior."""
    region = Region2D(f_expr="sqrt(x)", g_expr="x^2", a=0.1, b=1.0)
    axis = RevolutionAxis.x_axis()

    mesh = generate_solid_mesh(region, axis, num_radial=16, num_axial=15)

    assert mesh.is_valid is True
    assert mesh.x_inner is not None
    assert mesh.y_inner is not None
    assert mesh.z_inner is not None
    assert mesh.x_inner.shape == (15, 16)
    assert np.all(np.isfinite(mesh.x_inner))


def test_generate_solid_mesh_vertical_axis() -> None:
    """Verifica la parametrización de rotación alrededor de un eje vertical x=0."""
    region = Region2D(f_expr="x^2", a=0, b=1)
    axis = RevolutionAxis.y_axis()

    mesh = generate_solid_mesh(region, axis, num_radial=20, num_axial=15)

    assert mesh.is_valid is True
    assert mesh.x_outer.shape == (15, 20)
    assert np.all(np.isfinite(mesh.x_outer))
    assert np.all(np.isfinite(mesh.y_outer))
    assert np.all(np.isfinite(mesh.z_outer))


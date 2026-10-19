"""Pruebas unitarias para el lienzo de visualización 3D PlotCanvas3D."""

from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from integrallab.core.solids import (
    Region2D,
    RevolutionAxis,
    SolidMesh3D,
    generate_solid_mesh,
)
from integrallab.viz.canvas3d import PlotCanvas3D


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Fixture de sesión para instanciar QApplication en modo headless."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def test_canvas3d_instantiation(qapp: QApplication) -> None:
    """Verifica que PlotCanvas3D se instancie con una proyección tridimensional."""
    canvas = PlotCanvas3D()
    assert canvas.figure is not None
    assert canvas.axes is not None
    assert canvas.axes.name == "3d"
    assert canvas.axes.get_xlabel() == "X"
    assert canvas.axes.get_ylabel() == "Y"
    assert canvas.axes.get_zlabel() == "Z"


def test_canvas3d_plot_solid_disks_outer_only(qapp: QApplication) -> None:
    """Verifica el trazado de un sólido macizo (solo superficie exterior y eje)."""
    canvas = PlotCanvas3D()
    region = Region2D(f_expr="x^2", a=0, b=1)
    axis = RevolutionAxis.x_axis()
    mesh = generate_solid_mesh(region, axis, num_radial=16, num_axial=12)

    success = canvas.plot_solid_mesh(mesh, show_axis=True)

    assert success is True
    assert len(canvas.surface_collections) == 1
    assert len(canvas.axis_lines) >= 1
    assert canvas.axes.get_legend() is not None


def test_canvas3d_plot_solid_washers_outer_and_inner(qapp: QApplication) -> None:
    """Verifica el trazado de un sólido hueco (superficie exterior e interior)."""
    canvas = PlotCanvas3D()
    region = Region2D(f_expr="sqrt(x)", g_expr="x^2", a=0.2, b=1.0)
    axis = RevolutionAxis.x_axis()
    mesh = generate_solid_mesh(region, axis, num_radial=16, num_axial=12)

    assert mesh.x_inner is not None

    success = canvas.plot_solid_mesh(mesh, show_axis=True)

    assert success is True
    # Debe contener tanto la superficie exterior como la interior
    assert len(canvas.surface_collections) == 2


def test_canvas3d_plot_vertical_axis_solid(qapp: QApplication) -> None:
    """Verifica el renderizado de un sólido con eje de giro vertical."""
    canvas = PlotCanvas3D()
    region = Region2D(f_expr="x", a=0, b=1)
    axis = RevolutionAxis.vertical(2.0)
    mesh = generate_solid_mesh(region, axis, num_radial=16, num_axial=12)

    success = canvas.plot_solid_mesh(mesh, show_axis=True)

    assert success is True
    assert len(canvas.surface_collections) >= 1
    assert len(canvas.axis_lines) >= 1


def test_canvas3d_clear_resets_scene(qapp: QApplication) -> None:
    """Verifica que clear_canvas limpie todas las superficies y líneas de eje."""
    canvas = PlotCanvas3D()
    region = Region2D(f_expr="x^2", a=0, b=1)
    mesh = generate_solid_mesh(region, RevolutionAxis.x_axis(), num_radial=12, num_axial=10)

    canvas.plot_solid_mesh(mesh)
    assert len(canvas.surface_collections) == 1

    canvas.clear_canvas()
    assert len(canvas.surface_collections) == 0
    assert len(canvas.axis_lines) == 0
    # Verifica que el sistema de ejes 3D siga activo tras limpiar
    assert canvas.axes.name == "3d"


def _dish_mesh(b: float = 2.0, num_axial: int = 30, num_radial: int = 40) -> SolidMesh3D:
    """Sólido de y = x² girando sobre el eje X, construido solo con NumPy.

    Con b = 2 mide 2 de largo y 8 de diámetro: es un plato poco profundo.
    """
    t = np.linspace(0.0, b, num_axial)
    theta = np.linspace(0.0, 2.0 * np.pi, num_radial)
    t_grid, theta_grid = np.meshgrid(t, theta, indexing="ij")
    radius = t_grid**2
    return SolidMesh3D(
        x_outer=t_grid,
        y_outer=radius * np.cos(theta_grid),
        z_outer=radius * np.sin(theta_grid),
        axis=RevolutionAxis.x_axis(),
    )


def _scroll(button: str) -> SimpleNamespace:
    """Evento de rueda mínimo con el atributo ``button`` que usa el lienzo."""
    return SimpleNamespace(button=button)


def test_canvas3d_uses_real_proportions(qapp: QApplication) -> None:
    """La caja 3D respeta la escala real: el plato (2 de largo, 8 de diámetro) no se estira."""
    canvas = PlotCanvas3D()
    canvas.plot_solid_mesh(_dish_mesh(), show_axis=True)

    assert canvas._box_aspect is not None
    size_x, size_y, size_z = canvas._box_aspect
    # El eje X (largo) debe ser mucho más corto que Y y Z (diámetro), no 4:4:3.
    assert size_y > 1.5 * size_x
    assert size_y == pytest.approx(size_z, rel=0.2)
    # La caja coincide con los límites reales de los datos.
    limits = (canvas.axes.get_xlim3d(), canvas.axes.get_ylim3d(), canvas.axes.get_zlim3d())
    assert (size_x, size_y, size_z) == pytest.approx([abs(hi - lo) for lo, hi in limits])


def test_canvas3d_scroll_zoom_really_scales_the_view(qapp: QApplication) -> None:
    """La rueda del ratón cambia la escala real de la vista (antes escribía en axes.dist, inerte)."""
    canvas = PlotCanvas3D()
    canvas.plot_solid_mesh(_dish_mesh(), show_axis=False)
    base_scale = float(np.linalg.norm(canvas.axes.get_box_aspect()))

    canvas._on_scroll(_scroll("up"))
    assert canvas._zoom == pytest.approx(1.12)
    assert float(np.linalg.norm(canvas.axes.get_box_aspect())) == pytest.approx(base_scale * 1.12)

    canvas._on_scroll(_scroll("down"))
    assert canvas._zoom == pytest.approx(1.0)
    assert float(np.linalg.norm(canvas.axes.get_box_aspect())) == pytest.approx(base_scale)


def test_canvas3d_zoom_is_clamped_and_ignores_other_events(qapp: QApplication) -> None:
    """El zoom tiene tope y suelo, y los eventos sin botón de rueda se ignoran."""
    canvas = PlotCanvas3D()
    canvas.plot_solid_mesh(_dish_mesh(), show_axis=False)

    for _ in range(60):
        canvas._on_scroll(_scroll("up"))
    assert canvas._zoom == 5.0

    for _ in range(120):
        canvas._on_scroll(_scroll("down"))
    assert canvas._zoom == 0.4

    canvas._on_scroll(_scroll("step"))
    canvas._on_scroll(object())
    assert canvas._zoom == 0.4


def test_canvas3d_new_solid_and_clear_reset_zoom(qapp: QApplication) -> None:
    """Dibujar otro sólido o limpiar el lienzo reinicia el zoom y la proporción."""
    canvas = PlotCanvas3D()
    canvas.plot_solid_mesh(_dish_mesh(), show_axis=False)
    canvas._on_scroll(_scroll("up"))
    assert canvas._zoom != 1.0

    canvas.plot_solid_mesh(_dish_mesh(b=1.0), show_axis=False)
    assert canvas._zoom == 1.0

    canvas.clear_canvas()
    assert canvas._zoom == 1.0
    assert canvas._box_aspect is None


def test_canvas3d_user_click_stops_auto_rotation(qapp: QApplication) -> None:
    """Al tomar el control con el ratón, la rotación automática se detiene."""
    canvas = PlotCanvas3D()
    canvas.plot_solid_mesh(_dish_mesh(), show_axis=False)
    assert canvas._rotation_timer.isActive()

    canvas._stop_rotation(object())

    assert not canvas._rotation_timer.isActive()


def test_canvas3d_rejects_invalid_mesh(qapp: QApplication) -> None:
    """Verifica que una malla inválida sea rechazada retornando False sin trazar."""
    canvas = PlotCanvas3D()
    invalid_mesh = SolidMesh3D(
        x_outer=np.empty((0, 0)),
        y_outer=np.empty((0, 0)),
        z_outer=np.empty((0, 0)),
        is_valid=False,
        error_message="Error de prueba",
    )

    success = canvas.plot_solid_mesh(invalid_mesh)
    assert success is False
    assert len(canvas.surface_collections) == 0


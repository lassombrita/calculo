"""Pruebas unitarias para el lienzo de visualización 3D PlotCanvas3D."""

from __future__ import annotations

import os
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


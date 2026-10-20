"""Pruebas unitarias para el visor Three.js y la serialización de SolidMesh3D."""

from __future__ import annotations

import os
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from integrallab.core.solids import (
    AxisOrientation,
    Region2D,
    RevolutionAxis,
    SolidMesh3D,
    generate_solid_mesh,
)
from integrallab.viz.threejs_wrapper import (
    WEBENGINE_AVAILABLE,
    ThreeJSViewer,
    serialize_solid_mesh,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Fixture de sesión para instanciar QApplication en modo headless."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app  # type: ignore[return-value]


def test_serialize_solid_mesh_disk() -> None:
    """Verifica la serialización de un sólido macizo (disco) para Three.js."""
    region = Region2D(f_expr="x^2", a=0, b=1)
    axis = RevolutionAxis.x_axis()
    mesh = generate_solid_mesh(region, axis, num_radial=16, num_axial=10)

    data = serialize_solid_mesh(mesh, color_outer="#5CE1FF", show_axis=True)
    assert "outer" in data
    assert data["color_outer"] == "#5CE1FF"
    assert "inner" not in data
    assert data["outer"]["rows"] == 10
    assert data["outer"]["cols"] == 16
    assert len(data["outer"]["x"]) == 160
    assert len(data["outer"]["y"]) == 160
    assert len(data["outer"]["z"]) == 160
    assert "axis_line" in data
    assert len(data["axis_line"]["x"]) == 2


def test_serialize_solid_mesh_washer() -> None:
    """Verifica la serialización de un sólido hueco (arandela con f y g)."""
    region = Region2D(f_expr="sqrt(x)", g_expr="x^2", a=0, b=1)
    axis = RevolutionAxis(orientation=AxisOrientation.VERTICAL, position=0.0)
    mesh = generate_solid_mesh(region, axis, num_radial=12, num_axial=8)

    data = serialize_solid_mesh(mesh, color_outer="#5CE1FF", color_inner="#FF6B8A", show_axis=True)
    assert "outer" in data
    assert "inner" in data
    assert data["inner"]["rows"] == 8
    assert data["inner"]["cols"] == 12
    assert len(data["inner"]["x"]) == 96
    assert "axis_line" in data
    assert data["axis_line"]["x"][0] == 0.0
    assert data["axis_line"]["x"][1] == 0.0


def test_serialize_mesh_with_nans_and_infs() -> None:
    """Verifica que mallas con valores no finitos (NaN / Inf) sean rechazadas para evitar picos espurios."""
    x = np.array([[0.0, np.nan], [np.inf, -np.inf]])
    y = np.array([[1.0, 2.0], [3.0, 4.0]])
    z = np.array([[0.5, 0.5], [0.5, 0.5]])

    mesh = SolidMesh3D(
        x_outer=x,
        y_outer=y,
        z_outer=z,
        is_valid=True,
    )
    # Debe rechazarse devolviendo {} para no crear triángulos falsos hacia el origen
    data = serialize_solid_mesh(mesh)
    assert data == {}


def test_serialize_degenerate_dimensions() -> None:
    """Verifica que dimensiones menores a 2x2 devuelvan diccionario vacío."""
    mesh_1x5 = SolidMesh3D(
        x_outer=np.ones((1, 5)),
        y_outer=np.ones((1, 5)),
        z_outer=np.ones((1, 5)),
        is_valid=True,
    )
    assert serialize_solid_mesh(mesh_1x5) == {}

    mesh_empty = SolidMesh3D(
        x_outer=np.empty((0, 0)),
        y_outer=np.empty((0, 0)),
        z_outer=np.empty((0, 0)),
        is_valid=True,
    )
    assert serialize_solid_mesh(mesh_empty) == {}


def test_bundle_resources_are_local_and_offline() -> None:
    """Verifica que el bundle de Three.js y OrbitControls existan localmente sin dependencias CDN."""
    from pathlib import Path
    base_res = Path(__file__).parent.parent / "integrallab" / "resources"
    bundle_html = base_res / "threejs_bundle.html"
    js_three = base_res / "js" / "three.module.min.js"
    js_controls = base_res / "js" / "OrbitControls.js"
    js_license = base_res / "js" / "LICENSE_THREEJS.txt"

    assert bundle_html.exists(), "threejs_bundle.html debe existir"
    assert js_three.exists(), "three.module.min.js debe existir localmente"
    assert js_three.stat().st_size > 100_000, "three.module.min.js no debe estar vacío"
    assert js_controls.exists(), "OrbitControls.js debe existir localmente"
    assert js_license.exists(), "LICENSE_THREEJS.txt debe existir"

    content = bundle_html.read_text(encoding="utf-8")
    assert "https://unpkg.com" not in content, "El bundle HTML no debe depender de CDN externo"
    assert "http://" not in content, "El bundle HTML no debe realizar llamadas HTTP inseguras"
    assert "./js/three.module.min.js" in content, "El importmap debe apuntar al archivo local"



def test_threejs_viewer_widget(qapp: QApplication) -> None:
    """Verifica la creación del widget ThreeJSViewer y la invocación de su API."""
    viewer = ThreeJSViewer()
    assert viewer.objectName() == "ThreeJSViewer"

    region = Region2D(f_expr="x", a=0, b=1)
    axis = RevolutionAxis.x_axis()
    mesh = generate_solid_mesh(region, axis, num_radial=10, num_axial=8)

    # Debe aceptar la malla sin fallar
    res = viewer.plot_solid_mesh(mesh)
    assert res is True

    # Comprobar llamada a clear y zoom
    viewer.clear_canvas()
    viewer.set_auto_rotate(False)
    viewer.zoom(1.2)


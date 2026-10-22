"""Módulo de visualización (2D y 3D) con soporte PySide6/Qt.

Proporciona integración con Matplotlib para la interfaz gráfica Qt en 2D
y Three.js empaquetado localmente para 3D, diseñado para consumir datos
puramente numéricos generados por el dominio matemático sin dependencias externas.

Las exportaciones se cargan bajo demanda (PEP 562): así el proceso de cálculo puede
importar ``integrallab.viz.latex_render`` o ``integrallab.viz.report_assets`` sin
arrastrar Qt ni QtWebEngine.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "PlotCanvas": "integrallab.viz.canvas",
    "PlotCanvas3D": "integrallab.viz.canvas3d",
    "ThreeJSViewer": "integrallab.viz.threejs_wrapper",
    "latex_to_base64_html": "integrallab.viz.latex_render",
    "render_latex_to_png_bytes": "integrallab.viz.latex_render",
}

__all__ = list(_EXPORTS)


_SUBMODULES = frozenset({"canvas", "canvas3d", "threejs_wrapper", "latex_render", "style", "report_assets"})


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        return getattr(import_module(_EXPORTS[name]), name)
    if name in _SUBMODULES:  # compatibilidad: ``integrallab.viz.canvas`` tras ``import integrallab.viz``
        return import_module(f"integrallab.viz.{name}")
    raise AttributeError(f"module 'integrallab.viz' has no attribute {name!r}")

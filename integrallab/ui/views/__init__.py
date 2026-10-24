"""Vistas UI desacopladas (no importan SymPy directamente)."""
# Este módulo es solo para organizar vistas de la UI principal.
# Las vistas reciben datos procesados desde core/ y los muestran.

from .steps_view import StepsView  # noqa: F401

__all__ = ['StepsView']

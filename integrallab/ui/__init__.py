"""Subpaquete de interfaz gráfica de usuario para IntegralLab.

Provee la ventana principal (MainWindow) y los widgets de PySide6
que componen la UI, que se comunica con el dominio matemático
exclusivamente a través de la API pública de integrallab.core.
"""

from __future__ import annotations

from integrallab.ui.main_window import MainWindow

__all__ = ["MainWindow"]


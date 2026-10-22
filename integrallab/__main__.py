"""Punto de entrada de IntegralLab.

Permite ejecutar la aplicación directamente con:
    python -m integrallab

Responsabilidad:
Inicializar el entorno Qt (QApplication), instanciar la ventana principal
(MainWindow) y ceder el control al bucle de eventos de Qt.
"""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path


def main() -> int:
    """Arranca IntegralLab y devuelve el código de salida de Qt.

    Las importaciones de Qt van dentro de la función: el proceso de cálculo (contexto
    ``spawn``) vuelve a importar este módulo y no debe cargar Qt ni QtWebEngine.

    Returns:
        Código de salida del proceso (0 = éxito, != 0 = error).
    """
    from PySide6.QtWidgets import QApplication

    from integrallab.ui.main_window import MainWindow
    from integrallab.ui.theme import apply_theme

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    apply_theme(app, Path(__file__).parent / "ui" / "assets" / "fonts")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()  # necesario en ejecutables congelados (PyInstaller) de Windows
    sys.exit(main())


"""Punto de entrada de IntegralLab.

Permite ejecutar la aplicación directamente con:
    python -m integrallab

Responsabilidad:
Inicializar el entorno Qt (QApplication), instanciar la ventana principal
(MainWindow) y ceder el control al bucle de eventos de Qt.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from integrallab.ui.main_window import MainWindow
from integrallab.ui.theme import apply_theme


def main() -> int:
    """Arranca IntegralLab y devuelve el código de salida de Qt.

    Returns:
        Código de salida del proceso (0 = éxito, != 0 = error).
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    apply_theme(app, Path(__file__).parent / "ui" / "assets" / "fonts")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())


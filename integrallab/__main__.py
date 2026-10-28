from integrallab.ui.theme import apply_theme
from integrallab.ui.main_window import MainWindow
from pathlib import Path
import sys

def main() -> int:
    """Entrada del proceso de cálculo (subproceso, por defecto)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    apply_theme(app, Path(__file__).parent / "ui" / "assets" / "fonts")

    window = MainWindow()
    window.show()

    return app.exec()


def run() -> None:
    """Punto de entrada del comando ``integrallab`` (``[project.scripts]`` de ``pyproject.toml``).

    ``pyproject.toml`` apunta a ``integrallab.__main__:run``; antes esa función no existía y el
    comando instalado fallaba con ``AttributeError`` (``python -m integrallab`` sí funcionaba).
    """
    multiprocessing.freeze_support()  # necesario en ejecutables congelados (PyInstaller) de Windows
    sys.exit(main())


if __name__ == "__main__":
    run()
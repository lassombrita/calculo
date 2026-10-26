"""Configuración común de pytest.

Las preferencias de la aplicación (``QSettings``, p. ej. el modo de escritura visual) se guardan
en una carpeta temporal durante las pruebas: así no se lee ni se modifica la configuración real
del usuario, y una prueba que activa el editor visual no cambia cómo arrancan las demás.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings


@pytest.fixture(autouse=True, scope="session")
def _isolated_qsettings(tmp_path_factory: pytest.TempPathFactory) -> None:
    folder = tmp_path_factory.mktemp("qsettings")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(folder))

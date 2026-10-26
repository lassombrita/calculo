"""Guardas de privacidad: el repositorio no debe contener datos personales del equipo del autor.

Qué se rechaza en cualquier archivo de texto del proyecto (ver ``docs/PRIVACIDAD.md``):
- Correos electrónicos (salvo dominios de ejemplo o de «noreply»).
- Rutas absolutas de una carpeta personal (``C:\\Users\\<usuario>``, ``/home/<usuario>``,
  ``/Users/<usuario>``), que revelan el nombre de usuario del equipo.
- Enlaces a repositorios de GitHub de personas, salvo los de componentes de terceros declarados.

Términos privados adicionales (p. ej. el nombre de usuario o el correo del autor) NO se escriben
en el repositorio: se pasan solo al ejecutar las pruebas, separados por comas, en la variable de
entorno ``INTEGRALLAB_PRIVATE_TERMS``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Carpetas que no se revisan: control de versiones, cachés y código de terceros empaquetado
# tal cual (sus licencias y avisos se conservan sin cambios; ver THIRD_PARTY_NOTICES.md).
_SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "env", "build", "dist",
    ".mypy_cache", ".ruff_cache", "node_modules",
}
_THIRD_PARTY_DIRS = (
    Path("integrallab/resources/js"),
    Path("integrallab/resources/mathlive"),
)
_TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".json", ".html", ".css", ".js", ".yml", ".yaml",
    ".rst", "",
}

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
_ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "users.noreply.github.com", "noreply.github.com")
_HOME_PATH = re.compile(
    r"(?i)(\b[a-z]:[\\/]+users[\\/]+[^\\/\s\"'`<>]+)"      # C:\Users\<usuario>
    r"|(/home/[a-z_][a-z0-9_.-]*/)"                       # /home/<usuario>/
    r"|(/Users/[A-Za-z0-9_.-]+/)"                         # /Users/<usuario>/ (macOS)
)
_GITHUB_REPO = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
# Cuentas de proyectos de terceros que se citan en la documentación (no son personas del proyecto).
_ALLOWED_GITHUB_OWNERS = {"mrdoob", "arnog", "KaTeX", "sympy", "numpy", "matplotlib", "pytest-dev", "newren"}


def _project_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if any(rel.is_relative_to(d) for d in _THIRD_PARTY_DIRS):
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES or path.name == Path(__file__).name:
            continue
        files.append(path)
    return files


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _findings(pattern_check) -> list[str]:
    found: list[str] = []
    for path in _project_text_files():
        for number, line in enumerate(_read(path).splitlines(), start=1):
            hit = pattern_check(line)
            if hit:
                # Se informa archivo y línea, nunca el dato encontrado.
                found.append(f"{path.relative_to(ROOT)}:{number} ({hit})")
    return found


def test_there_are_files_to_scan() -> None:
    assert len(_project_text_files()) > 20


def test_no_email_addresses() -> None:
    def check(line: str) -> str | None:
        for match in _EMAIL.finditer(line):
            if not match.group(0).lower().endswith(_ALLOWED_EMAIL_DOMAINS):
                return "correo electrónico"
        return None

    assert _findings(check) == []


def test_no_absolute_paths_with_a_user_name() -> None:
    assert _findings(lambda line: "ruta de una carpeta personal" if _HOME_PATH.search(line) else None) == []


def test_no_links_to_personal_github_accounts() -> None:
    def check(line: str) -> str | None:
        for match in _GITHUB_REPO.finditer(line):
            if match.group(1) not in _ALLOWED_GITHUB_OWNERS:
                return "enlace a una cuenta de GitHub"
        return None

    assert _findings(check) == []


@pytest.mark.skipif(
    not os.environ.get("INTEGRALLAB_PRIVATE_TERMS"),
    reason="Defina INTEGRALLAB_PRIVATE_TERMS (separados por comas) para buscar términos privados.",
)
def test_no_private_terms_from_the_environment() -> None:
    terms = [t.strip().lower() for t in os.environ["INTEGRALLAB_PRIVATE_TERMS"].split(",") if t.strip()]
    assert _findings(lambda line: "término privado" if any(t in line.lower() for t in terms) else None) == []

"""Empaqueta la documentación de IntegralLab en un .zip organizado.

Uso (desde cualquier carpeta):
    python scripts/empaquetar_documentacion.py            # crea IntegralLab-documentacion-AAAA-MM-DD.zip aquí
    python scripts/empaquetar_documentacion.py salida.zip

Estructura del .zip (la misma del repositorio, para que los enlaces entre documentos funcionen):
    IntegralLab-documentacion/
    ├── LEEME.txt                  ← índice generado, en orden de lectura
    ├── README.md, AGENTS.md, COPYRIGHT.md, LICENSE, THIRD_PARTY_NOTICES.md
    └── docs/                      ← arquitectura, estado, auditorías, decisiones, desglose, editor…
        ├── img/                   ← capturas usadas por los documentos
        └── archive/               ← informes históricos (no se editan)

Antes de comprimir revisa que ningún archivo tenga correos o rutas de carpetas personales
(las mismas reglas que tests/test_privacy.py); si encuentra alguno, no crea el .zip.
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = "IntegralLab-documentacion"
PROJECT_FILES = ["README.md", "AGENTS.md", "COPYRIGHT.md", "LICENSE", "THIRD_PARTY_NOTICES.md"]
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org)\b)(?![\w.]*noreply\.github\.com\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_HOME = re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+[^\\/\s<>]+|/home/[a-z_][a-z0-9_.-]*/|/Users/[A-Za-z0-9_.-]+/")


def collect() -> list[tuple[Path, str]]:
    """(archivo, ruta dentro del .zip) en el orden de lectura."""
    docs = ROOT / "docs"
    paths = [ROOT / name for name in PROJECT_FILES if (ROOT / name).exists()]
    paths += [docs / "README.md", *sorted(p for p in docs.glob("*.md") if p.name != "README.md")]
    paths += sorted(p for p in (docs / "img").glob("*") if p.is_file())
    paths += sorted((docs / "archive").glob("*.md"))
    return [(p, f"{TOP}/{p.relative_to(ROOT).as_posix()}") for p in paths if p.exists()]


def privacy_problems(items: list[tuple[Path, str]]) -> list[str]:
    problems = []
    for path, _arc in items:
        if path.suffix.lower() not in {".md", ".txt", ""}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _EMAIL.search(line) or _HOME.search(line):
                problems.append(f"{path.relative_to(ROOT)}:{number}")
    return problems


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path.cwd() / f"{TOP}-{_dt.date.today():%Y-%m-%d}.zip"
    items = collect()
    problems = privacy_problems(items)
    if problems:
        print("No se creó el .zip: hay datos personales en", ", ".join(problems))
        return 1
    index = ["Documentación de IntegralLab", f"Generada el {_dt.date.today():%Y-%m-%d}.", "",
             "Orden de lectura: README.md, AGENTS.md, docs/README.md (índice de la documentación).", ""]
    index += [arc.removeprefix(f"{TOP}/") for _path, arc in items]
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{TOP}/LEEME.txt", "\n".join(index) + "\n")
        for path, arc in items:
            zf.write(path, arc)
    print(f"{target.name}: {len(items) + 1} archivos")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

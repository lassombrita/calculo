# Componentes de terceros

IntegralLab incluye y usa software de terceros. Cada componente conserva su titularidad y su licencia; el aviso de autoría de `COPYRIGHT.md` no los cubre. Este archivo es informativo y no sustituye el texto de cada licencia.

## Incluidos en el repositorio

Estos archivos se distribuyen tal cual dentro de `integrallab/resources/`, cada uno junto a su licencia.

| Componente | Versión | Licencia | Titular | Archivos | Texto de la licencia |
| --- | --- | --- | --- | --- | --- |
| [Three.js](https://github.com/mrdoob/three.js) | r160 | MIT | three.js authors | `resources/js/three.module.min.js` | `resources/js/LICENSE_THREEJS.txt` |
| OrbitControls (complemento de Three.js) | r160 | MIT | three.js authors | `resources/js/OrbitControls.js` | `resources/js/LICENSE_THREEJS.txt` |
| [MathLive](https://github.com/arnog/mathlive) | 0.111.1 | MIT | Arno Gourdol | `resources/mathlive/mathlive.min.js` | `resources/mathlive/LICENSE_MATHLIVE.txt` |
| [Fuentes KaTeX](https://github.com/KaTeX/katex-fonts) (incluidas en el paquete de MathLive) | la de MathLive 0.111.1 | MIT | Khan Academy | `resources/mathlive/fonts/KaTeX_*.woff2` | `resources/mathlive/fonts/LICENSE_KATEX_FONTS.txt` |

## Dependencias instaladas con pip

No se copian al repositorio; se instalan con `pip install -e ".[dev]"`. Versiones con las que se verificó la última sesión:

| Paquete | Versión | Licencia (según sus metadatos) | Uso |
| --- | --- | --- | --- |
| SymPy | 1.14.0 | BSD | Cálculo simbólico |
| mpmath | 1.3.0 | BSD | Cuadratura numérica (dependencia de SymPy) |
| NumPy | 2.5.4 | BSD-3-Clause, con partes 0BSD, MIT, Zlib y CC0-1.0 | Mallas y muestreo |
| Matplotlib | 3.11.2 | Licencia de Matplotlib (basada en la PSF) | Gráficas 2D, respaldo 3D y fórmulas de los reportes |
| PySide6 (Essentials, Addons, WebEngine) y shiboken6 | 6.12.0 | LGPL-3.0 (o GPL-2.0 / GPL-3.0) | Interfaz Qt, QtWebEngine y QWebChannel |
| pytest | 9.1.1 | MIT | Pruebas (solo desarrollo) |

## Notas para distribuir

- **MIT (Three.js, MathLive, fuentes KaTeX):** conservar el aviso de copyright y el texto de la licencia junto a los archivos. Ya están en el repositorio y `pyproject.toml` los empaqueta (`resources/**/*`).
- **LGPL-3.0 (PySide6/Qt):** si se distribuye un ejecutable (por ejemplo, con PyInstaller), Qt debe quedar enlazado dinámicamente y reemplazable por el usuario, y hay que incluir el texto de la licencia. Conviene revisar los términos exactos antes de publicar un instalador.
- Al actualizar un componente, cambiar aquí la versión y reemplazar su archivo de licencia. Para MathLive, ver `docs/EDITOR_VISUAL.md`, «Actualizar MathLive».

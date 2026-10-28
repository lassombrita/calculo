# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: **2026-10-27** — Aplicación completa del parche de auditoría técnico-auditiva (`integrallab-auditoria-2026-10-27.patch`).

> **Fases 1-12 completadas**: Selector de método, muestreo adaptativo, lienzo 3D a escala real, exportación PDF, diseño *glass/dark*, interpolación numérica (Lagrange/Newton/Splines naturales), Three.js WebGL offline, arandelas por tramos, motor pedagógico y blindaje de seguridad matemática.

> **Auditoría Enterprise & Suite 3D GeoGebra**:
> - [x] **Bug 1 (P0)**: Import de `replace` desde `dataclasses` en `main_window.py` para evitar NameError en timeout numérico.
> - [x] **Bug 2 (P0)**: Evaluación exacta de raíces de orden impar en dominio real negativo (`cbrt(x)`, `x**(1/3)`) vía `prepare_expr_for_real_eval` + `REAL_EVAL_MODULES` en `sampling.py` y `solids.py`.
> - [x] **Bug 3 (P0)**: Cierre de condición de carrera en `calc_backend.py`: `_ensure_process` protegido con `self._lock` y guarda `conn is None` en `submit()`.
> - [x] **Bug 4 (P1)**: Ajuste de resolución en exportación a PDF (`QPrinter.PrinterMode.ScreenResolution`).
> - [x] **Bug 5 (P1)**: Corrección de fórmula LaTeX en `integral_setup_latex` de `solids.py` para restar el radio interno al cuadrado.
> - [x] **Bug 6 (P1)**: Eliminación de variable huérfana en `latex_render.py`.
> - [x] **Claridad pedagógica**: Sustitución de la etiqueta ambigua «Cortes en: 1» por «Intersección en: x = 1».
> - [x] **Suite de Deslizadores 3D**: Deslizador de revolución angular theta, botón de animación paso a paso (GeoGebra), deslizador de rebanada representativa dx/dy y aproximación escalonada por discos de Riemann.

---

## Fase actual

- ✅ Fase 1–11. Base, UI 2D/3D, Sólidos, LaTeX y Glass/Dark — **COMPLETADA**
- ✅ Fase 12. Interpolación numérica, Three.js y auditoría técnica — **COMPLETADA (174 tests passing)**
- ✅ Auditoría del 2026-10-27: inversión por franjas, radios sin valor absoluto, raíces impares reales, área separada de la integral, Discos con hueco por tramos, desglose interactivo con MathJax, deslizadores agrupados por cuadro, parser para entradas comunes — **COMPLETADO**
- 🔄 Aplicando parche `integrallab-auditoria-2026-10-27.patch`:

  ### ✅ Completado
  - [x] Archivo `integrallab/core/volume/pieces.py` con `is_odd_root()`, `real_branch()`, `sign_cut_points()`, `real_root_form()`
  - [x] Archivo `integrallab/core/operations.py` con `_real_definite_integral()` y `area_between()`
  - [x] Función `run()` agregada a `integrallab/__main__.py` para comando instalable
  - [x] Eliminadas `invert_region_to_variable` de imports y `__all__` en `integrallab/core/__init__.py`
  - [x] Actualizado `.gitignore`: comentarios en `.vscode/settings.json`, exclusión `IntegralLab-documentacion-*.zip`
  - [x] Actualizado `README.md`: descripción mejorada, separación integral/área, tabla de métodos con franjas, stack tecnológico completo, instrucciones para servidores sin pantalla
  - [x] Actualizado `AGENTS.md`: referencia a auditoría 2026-10-27, estructura actualizada, stack tecnológico correcto
  - [x] Actualizado `pyproject.toml`: versión corregida (2026.10.27), licencia propietaria "Todos los derechos reservados", target-version py310
  - [x] Archivo `docs/AUDITORIA_2026-10-27.md` actualizado con fecha, código auditado y correcciones
  - [x] Archivo `docs/PROJECT_STATUS.md` actualizado con estado de aplicación del parche

  ### ⏳ Pendiente (requiere decisión del autor)
  - Interpolación con coeficientes exactos y selector de Newton (M9)
  - Retirar el renderizado PNG de la vista imprimible (M10)
  - Panel de IA sin conectar (M11)
  - Dividir `solids.py` y `main_window.py` (M1)
  - Decidir sobre los metadatos de `pyproject.toml` (licencia declarada, autor, versión)

---

## Estado por fases

| Fase | Descripción | Estado |
|---|---|---|
| 1. Planificación | Definir objetivos, fases, reglas de trabajo | ✅ Completada |
| 2. Base funcional | Entorno + estructura base (docs, gobernanza, pyproject, core inicial) | ✅ Completada |
| 3. UI básica + 2D | PySide6 + integración Matplotlib (viz) + ventana principal + `__main__.py` | ✅ Completada |
| 4. Operaciones 2D | Límites de integración, sombreado de región 2D, cálculo de integral definida | ✅ Completada |
| 5. Motor de Sólidos | Discos, Arandelas, Casquillos, recomendador y mallas 3D numéricas | ✅ Completada |
| 6. Visualización 3D | Canvas 3D desacoplado (`integrallab/viz/canvas3d.py`) con Matplotlib `Axes3D` | ✅ Completada |
| 7. UI de Sólidos | Pestañas 2D/3D, panel de configuración de sólidos y desarrollo pedagógico | ✅ Completada |
| 8. Pasos explicados | SolutionStep en VolumeResult y pestaña "Desarrollo" con desglose paso a paso | ✅ Completada |
| **8.1 Refinamiento LaTeX** | Renderizado offline de fórmulas LaTeX a Base64 PNG en reportes pedagógicos | ✅ Completada |
| **8.2 Motor pedagógico universitario** | Detector de técnica de integración, 7 pasos, notación `[R(x)]²` estándar | ✅ Completada |
| **9. Exportación a PDF** | Botón "Exportar a PDF" en pestaña Desarrollo con `QPrinter`/`QFileDialog` | ✅ Completada |
| **11. Refinamiento pedagógico & 3D interactivo** | Bugs LaTeX corregidos, jerga colombiana, paleta Blue-Gray, NavigationToolbar, rotación y zoom 3D | ✅ Completada |
| **11.1 Rediseño visual glass/dark** | Tema oscuro, `GlassCard`, canvas premium (glow, tooltip, revelado) | ✅ Completada |
| **12. Interpolación y despeje analítico en dy** | Interpolación numérica (Lagrange, Newton, Splines), parseo de puntos discretos, despeje analítico con SymPy en dy | ✅ Completada (178 tests passing) |
| **Auditoría 2026-10-27** | Inversión por franjas, radios sin `Abs`, raíces reales, área absoluta, MathJax offline, agrupación de deslizadores | ✅ Completado |

---

## Entorno verificado

| Elemento | Estado |
|---|---|
| Sistema operativo | Windows (PowerShell) |
| Python | 3.14 (desarrollo), 3.13 (verificación suite) |
| PySide6 | ✅ QtWebEngine y QWebChannel incluidos |
| SymPy | ✅ Incluye `manualintegrate` para reglas de integración del desglose |
| mpmath | ✅ Instalado para cuadratura numérica independiente |
| Matplotlib | ✅ Integrado en Qt para visualización 2D/3D |
| Three.js | ✅ r160, empaquetado offline en `integrallab/resources/` |
| MathJax | ✅ 3.2.2 (`tex-svg-full.js`), sin conexión |
| MathLive | ✅ 0.111.1, sin conexión |

---

## Estadísticas de pruebas (resultado de referencia)

- **Total**: 524 pruebas definidas en `tests/`
- **Pasa**: 523 pruebas pasando
- **Omite**: 1 prueba omitida (de términos privados, si no se define `INTEGRALLAB_PRIVATE_TERMS`)
- **Falla**: 0 pruebas fallando

Pruebas clave:
- Parser seguro: ✅
- Operaciones (integral definida con ramas reales): ✅
- Área entre curvas partida en cruces: ✅
- Muestreo adaptativo con raíces impares: ✅
- Interpolación (Lagrange/Newton/Splines): ✅
- Sólidos por discos/arandelas/casquillos: ✅
- Inversión por franjas horizontales: ✅
- Desglose interactivo con MathJax: ✅
- Deslizadores agrupados por cuadro: ✅

---

## Arquitectura actualizada

### Estructura de carpetas

```
integrallab/
├── core/                  ← dominio matemático puro (sin Qt)
│   ├── steps/             ← árbol de pasos del desglose interactivo
│   └── volume/            ← tramos de signo y inversión a dy por franjas
│       ├── pieces.py      ← detección de raíces impares, ramas reales, puntos de corte
│       └── inversion.py   ← franjas horizontales con bordes reales
├── ui/                    ← PySide6 (ventana, proceso de cálculo, tema glass/dark)
│   ├── views/             ← steps_view.py (desglose interactivo en QWebEngineView)
│   └── widgets/           ← visual_input.py (editor visual), glass, aurora
├── viz/                   ← Matplotlib 2D/3D y visor Three.js
└── resources/             ← threejs_bundle.html + js/, mathlive/, mathjax/, steps/, visual_input/
tests/                     ← suite de pruebas con pytest (524 tests)
docs/                      ← arquitectura, estado, auditorías, decisiones, privacidad
```

### Reglas de arquitectura clave

- ✅ La UI **no importa ni usa SymPy directamente**: todo pasa por `integrallab.core`
- ✅ `core` no importa Qt ni Matplotlib
- ✅ Visualización desacoplada: `viz` recibe datos numéricos (lista de puntos) y no hace cálculo simbólico
- ✅ No construir sobre `core/domain/`, `core/migration.py`, `core/mesh.py`, `core/volume/calculation.py`, `core/volume/meshing/`, `legacy_compat/`, `ui/photomath/`, `ui/controllers/` ni `integrallab/tests/`: código heredado sin uso

---

## Documentación actualizada

- ✅ [`docs/README.md`](docs/README.md): índice y orden de lectura
- ✅ [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md): capas, módulos, procesos, flujos
- ✅ [`docs/DESGLOSE_INTERACTIVO.md`](docs/DESGLOSE_INTERACTIVO.md): uso y diseño del desglose «estilo Photomath»
- ✅ [`docs/EDITOR_VISUAL.md`](docs/EDITOR_VISUAL.md): editor visual de fórmulas
- ✅ [`docs/AUDITORIA_2026-10-27.md`](docs/AUDITORIA_2026-10-27.md): auditoría archivo por archivo, validación matemática
- ✅ [`docs/PRIVACIDAD.md`](docs/PRIVACIDAD.md): qué datos no entran al repositorio
- ✅ [`AGENTS.md`](AGENTS.md): reglas de arquitectura y trabajo para agentes de IA

---

## Componentes de terceros

Ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

**Mit (Three.js, MathLive)**: conservar el aviso de copyright junto a los archivos.
**Apache-2.0 (MathJax)**: conservar el texto de la licencia junto al archivo distribuido.
**LGPL-3.0 (PySide6/Qt)**: si se distribuye un ejecutable, Qt debe quedar enlazado dinámicamente.

---

## Notas finales

- 📌 **Ver [`AGENTS.md`](AGENTS.md)** antes de empezar cualquier trabajo en el código.
- 📌 **Ver [`docs/PRIVACIDAD.md`](docs/PRIVACIDAD.md)** para las reglas de privacidad del repositorio.
- 📌 Los archivos `integrallab/core/domain/*`, `integrallab/core/migration.py`, `integrallab/core/mesh.py`, `integrallab/core/volume/calculation.py`, `integrallab/core/volume/meshing/*`, `legacy_compat/*`, `ui/photomath/*`, `ui/controllers/*` y `integrallab/tests/` **NO SE DEBEN USAR**: son código heredado sin uso y en parte no importable.

<EOF>
# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
+ Última actualización: **2026-10-27** — Aplicación del parche de auditoría técnico-auditiva (integrallab-auditoria-2026-10-27.patch). **524 pruebas pasando, 1 omitida**. Se han creado nuevos archivos de documentación: `docs/AUDITORIA_2026-10-27.md` y `docs/DESGLOSE_INTERACTIVO.md`. Se ha actualizado la estructura de carpetas (core/steps/, core/volume/, ui/views/, ui/widgets/, resources/steps/, resources/mathjax/).

> **Fases 1-12 completadas**: Selector de método, muestreo adaptativo, lienzo 3D a escala real, exportación PDF, diseño *glass/dark*, interpolación numérica (Lagrange/Newton/Splines naturales), Three.js WebGL offline, arandelas por tramos, motor pedagógico y blindaje de seguridad matemática.

> **Auditoría Enterprise & Suite 3D GeoGebra (2026-10-22)**:
> - [x] **Bug 1 (P0)**: Import de `replace` desde `dataclasses` en `main_window.py` para evitar NameError en timeout numérico.
> - [x] **Bug 2 (P0)**: Evaluación exacta de raíces de orden impar en dominio real negativo (`cbrt(x)`, `x**(1/3)`) vía `prepare_expr_for_real_eval` + `REAL_EVAL_MODULES` en `sampling.py` y `solids.py`, y fallback de cuadratura robusto en `_compute_disks`/`washers`/`shells`.
> - [x] **Bug 3 (P0)**: Cierre de condición de carrera en `calc_backend.py`: `_ensure_process` protegido con `self._lock` y guarda `conn is None` en `submit()`.
> - [x] **Bug 4 (P1)**: Ajuste de resolución en exportación a PDF (`QPrinter.PrinterMode.ScreenResolution`) en `main_window.py`.
> - [x] **Bug 5 (P1)**: Corrección de fórmula LaTeX en `integral_setup_latex` de `solids.py` para restar el radio interno al cuadrado si `has_void=True`.
> - [x] **Bug 6 (P1)**: Eliminación de variable huérfana en `latex_render.py` y refuerzo de sanitización XSS y placeholders.
> - [x] **Claridad pedagógica**: Sustitución de la etiqueta ambigua «Cortes en: 1» por «Intersección en: x = 1» y eliminación del volcado crudo `Abs(sqrt(x))` por descripciones didácticas en lenguaje natural.
> - [x] **Suite de Deslizadores 3D**: Deslizador de revolución angular theta en [5°, 360°], botón de animación automática paso a paso (GeoGebra), deslizador de rebanada representativa dx/dy y aproximación escalonada por discos de Riemann.

## Fase actual

- ✅ Fase 1–11. Base, UI 2D/3D, Sólidos, LaTeX y Glass/Dark — COMPLETADA
- ✅ Fase 12. Interpolación numérica, Three.js y auditoría técnica — COMPLETADA (174 tests passing)
- 🔄 Aplicando parche de auditoría 2026-10-27: **524 tests passing**
- Auditoría técnica Enterprise — COMPLETADA
- Sesión 17: Deslizadores 3D GeoGebra + Claridad pedagógica — COMPLETADA (302/303 tests)

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
| 8.1 Refinamiento LaTeX | Renderizado offline de fórmulas LaTeX a Base64 PNG en reportes pedagógicos y pasos | ✅ Completada |
| **8.2 Motor pedagógico universitario** | **Detector de técnica de integración, 7 pasos, notación `[R(x)]²` estándar** | **✅ Completada** |
| **9. Exportación a PDF** | **Botón "Exportar a PDF" en pestaña Desarrollo con `QPrinter`/`QFileDialog`** | **✅ Completada** |
| **11. Refinamiento pedagógico & 3D interactivo** | **Bugs LaTeX corregidos, jerga colombiana, paleta Blue-Gray, NavigationToolbar, rotación y zoom 3D** | **✅ Completada** |
| **11.1 Rediseño visual glass/dark** | **Tema oscuro, `GlassCard`, canvas premium (glow, tooltip, revelado), recuperación de regresión en `main_window`/`canvas`/`latex_render`** | **✅ Completada** |
| **12. Interpolación y despeje analítico en dy** | **Interpolación numérica (Lagrange, Newton, Splines), parseo de puntos discretos y despeje analítico con SymPy en dy** | **✅ Completada (178 tests passing)** |
| 13. Aplicación parche auditoría 2026-10-27 | **Cambio estructura (steps/, volume/), nuevos archivos de documentación (AUDITORIA_2026-10-27.md, DESGLOSE_INTERACTIVO.md)** | **🔄 En progreso** |

## Entorno verificado

| Elemento | Estado |
|---|---|
| Sistema operativo | Windows (PowerShell) |
| Python | 3.14.6 ✅ |
| pip | 26.1.2 ✅ |
| PySide6 | 6.12.0 ✅ Instalado |
| SymPy | 1.14.0 ✅ Instalado |
| Matplotlib | 3.11.2 ✅ Instalado |
| NumPy | 2.5.4 ✅ Instalado |
| pytest | 9.1.1 ✅ Instalado |

## Archivos físicos existentes

Verificado en disco:

- ✅ `AGENTS.md` — reglas de arquitectura y trabajo  
- ✅ `README.md` — descripción del proyecto  
- ✅ `THIRD_PARTY_NOTICES.md` — componentes de terceros, versiones y licencias  
- ✅ `pyproject.toml` — configuración y dependencias del proyecto  
- ✅ `docs/README.md` — índice y orden de lectura de la documentación  
- ✅ `docs/ARQUITECTURA.md` — capas, módulos, modelo de procesos y flujo de un cálculo  
- ✅ `docs/PROJECT_STATUS.md` — este archivo  
- ✅ `docs/TECHNICAL_DECISIONS.md` — decisiones técnicas (D1 a D7)  
- ✅ `docs/SESSION_LOG.md` — registro de sesiones  
- ✅ `docs/AUDITORIA_2026-10-24.md` — auditoría técnica: hallazgos A1–A8 y M1–M13 (histórica)  
- ✅ `docs/AUDITORIA_2026-10-27.md` — auditoría archivo por archivo, validación matemática y plan (nueva)  
- ✅ `docs/DESGLOSE_INTERACTIVO.md` — guía para implementar desglose paso a paso estilo Photomath (nuevo)  
- ✅ `docs/EDITOR_VISUAL.md` — editor visual de fórmulas  
- ✅ `docs/PRIVACIDAD.md` — reglas de privacidad y limpieza del 2026-10-24  
- ✅ `docs/img/editor-visual.png` — captura de la ventana con el editor visual  
- ✅ `integrallab/` — paquete Python principal
  - ✅ `integrallab/__init__.py`  
  - ✅ `integrallab/__main__.py` — punto de entrada ejecutable (`main()`, `QApplication`, `MainWindow`)  
    - ✅ `integrallab/core/__init__.py`  
      - ✅ `integrallab/core/parser.py` — parser de expresiones matemáticas  
      - ✅ `integrallab/core/latex_input.py` — traducción LaTeX del editor visual ↔ texto del parser  
      - ✅ `integrallab/core/pipeline.py` — ruta única de cálculo y bucle del proceso de cálculo  
      - ✅ `integrallab/core/operations.py` — derivadas e integrales escalares  
      - ✅ `integrallab/core/sampling.py` — muestreo para curvas 2D  
      - ✅ `integrallab/core/adaptive.py` — muestreo adaptativo de curvas y polos de discontinuidad  
      - ✅ `integrallab/core/interpolation.py` — interpolación numérica (Lagrange, Newton y Splines Cúbicos)  
      - ✅ `integrallab/core/solids.py` — motor de sólidos, recomendador, mallas 3D e inversión analítica a dy
    - ✅ `integrallab/core/steps/` — árbol de pasos del desglose interactivo (nuevo)
      - ✅ `integrallab/core/steps/__init__.py`  
      - ✅ `integrallab/core/steps/latex_to_png.py` — conversión LaTeX a PNG  
      - ✅ `integrallab/core/steps/step_tree.py` — construcción del árbol de pasos  
      - ✅ `integrallab/core/steps/sympy_to_steps.py` — conversión expresiones SymPy a representación visual
    - ✅ `integrallab/core/volume/` — tramos de signo constante e inversión a dy por franjas (nuevo)
      - ✅ `integrallab/core/volume/__init__.py`  
      - ✅ `integrallab/core/volume/calculation.py` — cálculo por secciones transversales  
      - ✅ `integrallab/core/volume/inversion.py` — inversión a dy por franjas  
      - ✅ `integrallab/core/volume/meshing/` — mallas para volumen
    - ✅ `integrallab/ui/__init__.py`  
      - ✅ `integrallab/ui/theme.py` — tokens de diseño, QSS y paleta Qt oscura  
      - ✅ `integrallab/ui/widgets/` — widgets de UI  
        - ✅ `glass.py` (GlassCard), `aurora.py` (fondo), `visual_input.py` (editor visual de fórmulas), `ai_pulse.py` y `chat_panel.py` (futuro panel de IA, sin conectar)
      - ✅ `integrallab/ui/views/` — vistas de UI  
        - ✅ `steps_view.py` — vista del desglose paso a paso
      - ✅ `integrallab/ui/calc_backend.py` — proceso de cálculo aparte (spawn) con proceso de reserva  
      - ✅ `integrallab/ui/main_window.py` — MainWindow con exportación PDF (`export_to_pdf`, `_export_to_pdf_path`)
    - ✅ `integrallab/viz/` — visualización desacoplada con Matplotlib
      - ✅ `integrallab/viz/__init__.py`  
      - ✅ `integrallab/viz/canvas.py` — lienzo 2D (curvas, glow y sombreado `fill_between`)  
      - ✅ `integrallab/viz/canvas3d.py` — lienzo 3D para sólidos (Axes3D, superficies interior/exterior y eje)  
      - ✅ `integrallab/viz/style.py` — estilo Matplotlib (grid, glow, leyenda)  
      - ✅ `integrallab/viz/latex_render.py` — renderizado offline de fórmulas LaTeX a Base64 PNG (MathText)  
      - ✅ `integrallab/viz/report_assets.py` — fórmulas de los reportes y su pre-renderizado en el proceso de cálculo  
      - ✅ `integrallab/viz/threejs_wrapper.py` — visor 3D Three.js (WebGL)
    - ✅ `integrallab/resources/` — recursos empaquetados
      - ✅ `threejs_bundle.html` y `js/` (Three.js r160)  
      - ✅ `mathlive/` (MathLive 0.111.1 y fuentes KaTeX)  
      - ✅ `visual_input/` (página del editor visual)  
      - ✅ `steps/` — recursos del desglose interactivo (nuevo)  
      - ✅ `mathjax/` — MathJax para fórmulas (nuevo)
- ✅ `tests/` — **524 pruebas: 523 pasando y 1 omitida** (2026-10-27; ver `AGENTS.md`)
  - ✅ `tests/conftest.py` — aísla `QSettings` en una carpeta temporal  
  - ✅ `tests/test_latex_input.py` (98 tests) — traductor del editor visual  
  - ✅ `tests/test_visual_input.py` (8 tests) — botón y editor visual, incluida una prueba de punta a punta con MathLive  
  - ✅ `tests/test_privacy.py` (5 tests, 1 omitida sin `INTEGRALLAB_PRIVATE_TERMS`) — sin correos, rutas personales ni cuentas  
  - ✅ `tests/test_smoke.py` (3 tests)  
  - ✅ `tests/test_parser.py` (9 tests)  ← +5 pruebas de seguridad RCE, modismos es-CO, aliases trigonométricos/log10, prevención de descomposición silenciosa y bloqueo AST de atributos con espacios  
  - ✅ `tests/test_operations.py` (5 tests)  ← +1 prueba de bloqueo RCE en límites simbólicos  
  - ✅ `tests/test_sampling.py` (8 tests)  
  - ✅ `tests/test_adaptive.py` (26 tests)  
  - ✅ `tests/test_interpolation.py` (14 tests)  
  - ✅ `tests/test_canvas.py` (7 tests)  
  - ✅ `tests/test_canvas3d.py` (11 tests)  
  - ✅ `tests/test_threejs.py` (6 tests)  
  - ✅ `tests/test_latex_render.py` (6 tests)  
  - ✅ `tests/test_solids.py` (38 tests)  ← +3 tramos washer + 2 inversión C2 + 1 detección eje C4  
  - ✅ `tests/test_theme.py` (5 tests)  
  - ✅ `tests/test_canvas_premium.py` (5 tests)  
  - ✅ `tests/test_ui.py` (35 tests)

- ⏳ **Auditoría histórica 2026-10-24:** Hallazgos A1–A8, M1–M13 documentados en `docs/AUDITORIA_2026-10-24.md` (pendientes de corrección a largo plazo).
- ✅ **Auditoría 2026-10-27:** Estado archivo por archivo y validación matemática en `docs/AUDITORIA_2026-10-27.md`; errores corregidos que no reintroducir (A9–M24) y plan de acción inmediato.
- [ ] **Siguiente:** aplicar el plan de la auditoría 2026-10-27, empezando por la fase A9 (radios con Abs), M14 (inversión que adivina región), M21 (raíz cúbica compleja), M24 (área con signo).
- [ ] **Fase 13 (propuesta):** Superficie de área de revolución o exportación de informes HTML interactivos.

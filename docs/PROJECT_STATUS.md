# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: **2026-10-19** — Implementación completa de soluciones de auditoría técnica y remediación de robustez: blindaje RCE en parser con lista blanca y sandbox AST, prevención de descomposiciones silenciosas de funciones desconocidas, normalizador es-CO (sen, tg, 0,5, x², π, √, Abs, E), corrección de inversión en dy para curvas decrecientes (4-x²), cálculo asíncrono en UI con QThread (sin congelamiento de interfaz), umbral dinámico de ruido imaginario, empaquetado de resources y archivo de reportes sueltos en docs/archive/. **178 pruebas pasando al 100 %.**

> **Fases 1–12 completadas**: Selector de método, muestreo adaptativo, lienzo 3D a escala real, exportación PDF, diseño *glass/dark*, interpolación numérica (Lagrange/Newton/Splines naturales), Three.js WebGL offline, arandelas por tramos, motor pedagógico y blindaje de seguridad matemática.


## Fase actual

✅ **Fase 11: Refinamiento pedagógico, corrección LaTeX y motor 3D interactivo** — Completada
✅ **Fase 12: Interpolación numérica, despeje analítico en dy y Three.js** — Completada
✅ **Auditoría técnica y seguridad matemática implementadas** — Completada (178 tests passing)

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

## Entorno verificado

| Elemento | Estado |
|---|---|
| Sistema operativo | Windows (PowerShell) |
| Ruta absoluta del proyecto | `C:\Users\merej\OneDrive\Desktop\Calculo` |
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
- ✅ `pyproject.toml` — configuración y dependencias del proyecto
- ✅ `docs/PROJECT_STATUS.md` — este archivo
- ✅ `docs/TECHNICAL_DECISIONS.md` — decisiones técnicas (D1, D2 y D3)
- ✅ `docs/SESSION_LOG.md` — registro de sesiones
- ✅ `integrallab/` — paquete Python principal
  - ✅ `integrallab/__init__.py`
  - ✅ `integrallab/__main__.py` — punto de entrada ejecutable (`main()`, `QApplication`, `MainWindow`)
  - ✅ `integrallab/core/` — dominio matemático puro (sin dependencias gráficas)
    - ✅ `integrallab/core/__init__.py`
    - ✅ `integrallab/core/parser.py` — parser de expresiones matemáticas
    - ✅ `integrallab/core/operations.py` — derivadas e integrales escalares
    - ✅ `integrallab/core/sampling.py` — muestreo para curvas 2D
    - ✅ `integrallab/core/adaptive.py` — muestreo adaptativo de curvas y polos de discontinuidad
    - ✅ `integrallab/core/interpolation.py` — interpolación numérica (Lagrange, Newton y Splines Cúbicos)
    - ✅ `integrallab/core/solids.py` — motor de sólidos, recomendador, mallas 3D e inversión analítica a dy
  - ✅ `integrallab/viz/` — visualización desacoplada con Matplotlib
    - ✅ `integrallab/viz/__init__.py`
    - ✅ `integrallab/viz/canvas.py` — lienzo 2D (curvas, glow y sombreado `fill_between`)
    - ✅ `integrallab/viz/canvas3d.py` — lienzo 3D para sólidos (Axes3D, superficies interior/exterior y eje)
    - ✅ `integrallab/viz/style.py` — estilo Matplotlib (grid, glow, leyenda)
    - ✅ `integrallab/viz/latex_render.py` — renderizado offline de fórmulas LaTeX a Base64 PNG (MathText)
  - ✅ `integrallab/ui/` — interfaz gráfica PySide6 (orquestador visual)
    - ✅ `integrallab/ui/__init__.py`
    - ✅ `integrallab/ui/theme.py` — tokens de diseño, QSS y paleta Qt oscura
    - ✅ `integrallab/ui/widgets/` — `glass.py` (GlassCard), `aurora.py` (fondo), `ai_pulse.py` y `chat_panel.py` (futuro panel de IA, sin conectar)
    - ✅ `integrallab/ui/main_window.py` — MainWindow con exportación PDF (`export_to_pdf`, `_export_to_pdf_path`)
- ✅ `tests/` — **178 pruebas pasando al 100 %**
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

## Siguiente tarea atómica

- [x] **Fase 12 y Remediación de Auditoría completadas** — 178 tests al 100%.
  - [x] Parser seguro (C1): sandbox con lista blanca estricta, validación AST (`ast.walk`), bloqueo de dunders, atributos (`.attr` y `. attr`) y RCE.
  - [x] Prevención de descomposición silenciosa: rechazo de identificadores desconocidos seguidos de paréntesis (ej. `foobar(x)`), y aliases extendidos (`arcsin`, `ctg`, `log10`, `log2`, etc.).
  - [x] Blindaje de límites: sustitución total de fallbacks `sympify` ciegos por `parse_numeric_or_symbolic` en `operations.py`, `solids.py` y UI.
  - [x] Cálculo asíncrono con `QThread` (`CalculationWorker`): evita congelamiento de interfaz ante integrales costosas, con feedback "⏳ Calculando..." y cancelación interactiva con `Esc`.
  - [x] Umbral dinámico relativo de ruido imaginario en muestreo: `abs(val.imag) < 1e-9 * max(1.0, abs(val.real))`.
  - [x] Normalizador es-CO (C6): soporte nativo de sen, tg, 0,5, x², π, √, Abs, E.
  - [x] Inversión a dy para curvas decrecientes (C2): 4-x² discos en eje Y = 25.13, casquillos en eje X = 53.62.
  - [x] Detección robusta de eje cortando la región (C4): muestreo multipunto en recommend_method.
  - [x] Validación de convergencia y finitud (C5): detección de integrales divergentes y límites no finitos.
  - [x] Splines cúbicos naturales estándar (C7): algoritmo tridiagonal O(n) con condiciones de frontera natural.
  - [x] Empaquetado `resources/` en `pyproject.toml` y archivado de reportes en `docs/archive/`.
- [ ] **Fase 13 (propuesta):** Superficie de área de revolución o exportación de informes HTML interactivos.

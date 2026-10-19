# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: **Auditoría técnica integral y corrección completadas (2026-10-19)** — Corrección de sintaxis en arandelas (`core/solids.py`), integración de advertencias de cruces de curvas en UI (`ui/main_window.py`), verificación de los 4 casos matemáticos de auditoría y suite completa con 139 tests pasando al 100%.

> **Fases 1–11.2 completadas**: Selector de método, muestreo adaptativo 2D (`core/adaptive.py`), lienzo 3D a escala real, exportación PDF, diseño *glass/dark*, avisos de derechos de autor (`COPYRIGHT.md` y `LICENSE`) y suite de pruebas integral.


## Fase actual

✅ **Fase 11: Refinamiento pedagógico, corrección LaTeX y motor 3D interactivo** — Completada
⏳ **Fase 12: Interpolación numérica y empaquetado final** — Siguiente tarea

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
| 12. Interpolación y entrega | Métodos de interpolación numérica y empaquetado final | ⏳ Pendiente (Siguiente tarea) |

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
    - ✅ `integrallab/core/solids.py` — motor de sólidos con detector de técnica de integración
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
- ✅ `tests/` — **139 pruebas pasando al 100%**
  - ✅ `tests/test_smoke.py` (3 tests)
  - ✅ `tests/test_parser.py` (4 tests)
  - ✅ `tests/test_operations.py` (4 tests)
  - ✅ `tests/test_sampling.py` (8 tests)
  - ✅ `tests/test_adaptive.py` (26 tests)
  - ✅ `tests/test_canvas.py` (7 tests)
  - ✅ `tests/test_canvas3d.py` (11 tests)
  - ✅ `tests/test_latex_render.py` (6 tests)
  - ✅ `tests/test_solids.py` (28 tests)
  - ✅ `tests/test_theme.py` (5 tests)
  - ✅ `tests/test_canvas_premium.py` (5 tests)
  - ✅ `tests/test_ui.py` (32 tests)

## Siguiente tarea atómica

- [ ] **Fase 12: Interpolación numérica y empaquetado final**:
  - Implementar en `integrallab/core/interpolation.py` métodos de interpolación numérica (Lagrange, Newton o splines cúbicos) a partir de puntos de datos discretos.
  - Conectar curvas interpoladas al sistema de integración y revolución para calcular sólidos a partir de datos experimentales.
  - Verificación global de calidad y preparación para distribución.


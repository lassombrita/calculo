# Estado del proyecto ? IntegralLab

> Este archivo se actualiza **al terminar cada sesion** de trabajo.
> Ultima actualizacion: **2026-10-22** ? Sesion 15: Parche Plan A (auditoria ronda 3), correccion del cierre de tuberias en Windows, e implementacion de mejoras pendientes P1-P4. **299 pruebas pasando (1 omitida: exclusiva Linux).**

> **Fases 1-12 completadas**: Selector de metodo, muestreo adaptativo, lienzo 3D a escala real, exportacion PDF, diseno *glass/dark*, interpolacion numerica (Lagrange/Newton/Splines naturales), Three.js WebGL offline, arandelas por tramos, motor pedagogico y blindaje de seguridad matematica.

> **Auditoria Ronda 3 + Parche Plan A (2026-10-22)**:
> - [x] Parche `calculo-planA-parche-unico.patch` aplicado sobre commit limpio `c2eddc9`.
> - [x] Correccion de cierre de tuberias `multiprocessing` en Windows: `_listen_loop` usa `conn.poll(0.1)`.
> - [x] **P1**: `numeric_volume()` en `solids.py`, `numeric_only` en `CalculationRequest`, fallback numerico de 8 s.
> - [x] **P2**: Proceso de reserva `_spare` en `ProcessCalculationBackend` ? reemplazo instantaneo.
> - [x] **P3**: `threejs_wrapper._dispatch_render` envuelve `renderSolid` en try/catch JS.
> - [x] **P4**: Temporizador simbolico 8 s + reintento automatico de backend tras 30 s.


## Fase actual

- Fase 11: Refinamiento pedagogico  COMPLETADA
- Fase 12: Interpolacion numerica, dy, Three.js  COMPLETADA
- Auditoria tecnica  COMPLETADA
- Sesion 15: Plan A + correcciones Windows + P1-P4  COMPLETADA (299/300 tests)

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
- [x] **Auditoría UI/3D (2026-10-22)** — 268 tests al 100 %.
  - [x] `self._worker` nunca se inicializaba: el primer clic real con límites lanzaba `AttributeError` y el sólido no se calculaba (la cancelación con `Esc` tampoco funcionaba). Corregido; trabajos con identificador y descarte de resultados obsoletos.
  - [x] Ruta única de cálculo `integrallab/core/pipeline.py` (se eliminó la rama síncrona dependiente de `QT_QPA_PLATFORM`); la malla 3D se entrega antes del volumen simbólico.
  - [x] Cálculo en proceso aparte (`ui/calc_backend.py`, contexto `spawn`): sin contención del GIL con Qt y cancelación real. Cerrar la ventana durante un cálculo ya no aborta el proceso.
  - [x] Entradas como `max(1,2)*x`, `log(x,2)` o `0,5*(x+1)` ya no se desvían al lector de puntos; los splines (≥ 5 puntos) funcionan de punta a punta.
  - [x] Visor Three.js: handshake de WebGL con cambio automático a Matplotlib, payload float32/base64 (~4× menor), tapas del sólido, orden de transparencia, zoom/grilla escalados, render bajo demanda y resolución adaptativa.
  - [x] Lienzos Matplotlib: sin `tight_layout` en cada dibujo, tooltip y revelado por *blitting*, sin animación 3D oculta.
  - [x] Reportes compatibles con QTextDocument (tablas) y con `html.escape`; fórmulas pre-renderizadas en el proceso de cálculo.
- [x] **Tercera auditoría, post-parches (2026-10-22)** — 300 tests al 100 % (Python 3.13 y 3.10/NumPy 1.26).
  - [x] Casquillos con curvas que se cruzan (x vs x² en [0, 2], eje Y): −8π/3 → 3π. Tramos por cruce y altura con el signo de cada tramo.
  - [x] Orientación f/g decidida por mediana de 9 muestras, no por el punto medio (sin(x)/x en [-1, 1]: −5,638 → +5,638).
  - [x] Cruces hallados numéricamente cuando `solve` no tiene algoritmo (Max/Min): −0,7016 → 0,7728. Ningún volumen negativo se informa como éxito.
  - [x] Dominio real: sqrt(x) en [-1, 1], asin(x) en [0, 2] o log(x) en [-1, 1] dan un error claro (antes «2/3 + 2*I/3» y V = 0). Áreas complejas rechazadas.
  - [x] Desbordamiento de float (exp(1000·x) en [0, 1] ≈ 1,97e431) ya no se informa como «no converge».
  - [x] Integrales no elementales con valor numérico (x**x ≈ 2,8339; floor(x) sin error interno). Símbolos libres (`a*x**2`) con mensaje claro.
  - [x] Malla de visualización finita en singularidades de borde o evitables (log(x), sin(x)/x); el visor se limpia si no puede dibujar; payload float32 sin desbordes (> 1e37).
  - [x] Vista 2D ajustada a [a, b]; formato numérico con notación científica (1.1351e+87, 1.0472e-36).
  - [x] Casquillos con cruces y spline: desarrollo por tramos sin re-integrar x·|f − g| (spline de 5 puntos vs 0,2 en el eje Y: 110 s → 2,6 s).
  - [x] Proceso de cálculo: sale en ~5 ms si la interfaz muere (vigía del padre + `PR_SET_PDEATHSIG` en Linux); reciclado tras 60 trabajos; la tubería la cierra solo su hilo oyente.
- [ ] **Fase 13 (propuesta):** Superficie de área de revolución o exportación de informes HTML interactivos.

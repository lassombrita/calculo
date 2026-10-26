# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: **2026-10-24** — Sesión 21: documentación completa (índice, arquitectura, editor visual, auditoría, privacidad, componentes de terceros) y limpieza de datos personales con `tests/test_privacy.py`. **413 pruebas pasando, 1 omitida** (la de términos privados, si no se define `INTEGRALLAB_PRIVATE_TERMS`). Sesión 20: editor visual de fórmulas.

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

- Fase 11: Refinamiento pedagógico — COMPLETADA
- Fase 12: Interpolación numérica, dy, Three.js — COMPLETADA
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
- ✅ `docs/AUDITORIA_2026-10-24.md` — auditoría técnica: hallazgos A1–A8 y M1–M13 (pendientes) y plan de acción
- ✅ `docs/EDITOR_VISUAL.md` — editor visual de fórmulas
- ✅ `docs/PRIVACIDAD.md` — reglas de privacidad y limpieza del 2026-10-24
- ✅ `docs/img/editor-visual.png` — captura de la ventana con el editor visual
- ✅ `integrallab/` — paquete Python principal
  - ✅ `integrallab/__init__.py`
  - ✅ `integrallab/__main__.py` — punto de entrada ejecutable (`main()`, `QApplication`, `MainWindow`)
  - ✅ `integrallab/core/` — dominio matemático puro (sin dependencias gráficas)
    - ✅ `integrallab/core/__init__.py`
    - ✅ `integrallab/core/parser.py` — parser de expresiones matemáticas
    - ✅ `integrallab/core/latex_input.py` — traducción LaTeX del editor visual ↔ texto del parser
    - ✅ `integrallab/core/pipeline.py` — ruta única de cálculo y bucle del proceso de cálculo
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
    - ✅ `integrallab/viz/report_assets.py` — fórmulas de los reportes y su pre-renderizado en el proceso de cálculo
    - ✅ `integrallab/viz/threejs_wrapper.py` — visor 3D Three.js (WebGL)
  - ✅ `integrallab/resources/` — `threejs_bundle.html` y `js/` (Three.js r160), `mathlive/` (MathLive 0.111.1 y fuentes KaTeX), `visual_input/` (página del editor visual)
  - ✅ `integrallab/ui/` — interfaz gráfica PySide6 (orquestador visual)
    - ✅ `integrallab/ui/__init__.py`
    - ✅ `integrallab/ui/theme.py` — tokens de diseño, QSS y paleta Qt oscura
    - ✅ `integrallab/ui/widgets/` — `glass.py` (GlassCard), `aurora.py` (fondo), `visual_input.py` (editor visual de fórmulas), `ai_pulse.py` y `chat_panel.py` (futuro panel de IA, sin conectar)
    - ✅ `integrallab/ui/calc_backend.py` — proceso de cálculo aparte (spawn) con proceso de reserva
    - ✅ `integrallab/ui/main_window.py` — MainWindow con exportación PDF (`export_to_pdf`, `_export_to_pdf_path`)
- ✅ `tests/` — **414 pruebas: 413 pasando y 1 omitida** (2026-10-24; el desglose de abajo es histórico, de la fase 12)
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
- [x] **Editor visual de fórmulas (2026-10-24)** — 409 tests al 100 %.
  - [x] Botón «√x Editor visual» en el grupo 1 que alterna entre las casillas de texto y un editor visual (f, g, a, b) con barra de plantillas: fracción, raíces, potencias, inversa, valor absoluto, π, eˣ, sin/cos/tan, ln, log, log con base y grados. La preferencia se recuerda (`QSettings`).
  - [x] MathLive 0.111.1 (MIT) empaquetado sin conexión en `resources/mathlive/`; página en `resources/visual_input/` y widget `ui/widgets/visual_input.py` con `QWebChannel`.
  - [x] `core/latex_input.py`: LaTeX del editor → texto del parser (multiplicación implícita explícita, `sen`/`tg`, `\sin^{-1}`, `log` = base 10 como en la calculadora, grados) y texto → LaTeX para mostrar lo ya escrito. Toda entrada sigue pasando por el parser seguro.
  - [x] Casillas incompletas (recuadros vacíos) bloquean el cálculo con un aviso bajo la casilla; se conserva el último texto válido.
  - [x] Panel lateral desplazable (`QScrollArea`): con el editor activo, o en pantallas de 768 px, Qt comprimía las casillas por debajo de su mínimo.
- [x] **Documentación y privacidad (2026-10-24)** — 413 pruebas pasando, 1 omitida.
  - [x] Índice (`docs/README.md`), arquitectura, editor visual, auditoría en el repositorio, privacidad y `THIRD_PARTY_NOTICES.md`.
  - [x] Eliminadas de la documentación las rutas locales con el nombre de usuario del equipo y las URL con el usuario de GitHub (detalle en `docs/PRIVACIDAD.md`).
  - [x] `tests/test_privacy.py` impide que vuelvan correos, rutas personales o enlaces a cuentas.
  - [ ] Pendiente del autor: correo privado en Git y limpieza del historial antes de publicar (ver `docs/PRIVACIDAD.md`).
- [ ] **Siguiente:** aplicar el plan de la auditoría (`docs/AUDITORIA_2026-10-24.md`), empezando por la fase 0 (contención) y la fase 1 (núcleo correcto).
- [ ] **Fase 13 (propuesta):** Superficie de área de revolución o exportación de informes HTML interactivos.

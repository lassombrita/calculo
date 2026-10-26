# Documento de Auditoría Total — IntegralLab

**Fecha:** 27 de octubre de 2026 · **Código auditado:** commit `b9642d7` (rama principal) · **Comparado con:** `adcedc7` y los parches del 2026-10-24
**Correcciones:** `integrallab-auditoria-2026-10-27.patch` (principal) e `integrallab-limpieza.patch` (opcional, solo borra)
**Verificación:** 523 pruebas pasando y 1 omitida tras el parche (418 y 1 antes); referencia matemática independiente con mpmath

Las líneas citadas como «HEAD» son las del commit `b9642d7`. Estados: **✅ Funcional** (implementado y funcional), **⚠️ Con fallos** (implementado pero con fallos), **❌ Incompleto** (incompleto, no importable o sin conectar), **⏳ Próximo** (próximo a implementar).

---

## 1. Auditoría de código y arquitectura

### 1.1 Núcleo matemático (`integrallab/core/`)

| Archivo · función | Estado en HEAD | Problema (líneas HEAD) | Tras el parche |
| --- | --- | --- | --- |
| `parser.py` · `parse_math_expression`, `_validate_*` | ✅ | Lista blanca, AST, factorial acotado (`MAX_FACTORIAL_ARG`), patrón de puntos lineal: correcto. | ✅ Sin cambios en la seguridad |
| `parser.py` · `_replace_abs_bars` (372–399) | ⚠️ | Empareja barras solo por paréntesis: `||x|-1|` → `Abs()` vacío + `xAbs()`; `ln|x|` → `lnAbs(x)` («función no reconocida»). | ✅ Pila de barras abiertas; tras una función emite `ln(Abs(x))` |
| `parser.py` · transformaciones (357–365) | ⚠️ | `implicit_application` convierte `x(x+1)` en la llamada `x(...)` y falla con «name 'Function' is not defined»; `sinx` se lee como `i*n*s*x`; `xsin(x)` se rechaza. | ✅ `_split_glued_names` y `x(` → `x*(`; `sinx^2` = sin(x²) como en la calculadora. `1/2x` sigue siendo x/2 (documentado) |
| `parser.py` · alias es-CO (500–527) | ✅ | `cosenh` → `cosh` ya corregido. | ✅ Tabla `_ALIASES` reutilizable |
| `latex_input.py` | ✅ | Traducción LaTeX ↔ texto del editor visual; 98 pruebas. | ✅ |
| `operations.py` · `integrate_definite` (179–286) | ⚠️ | Línea 228: `sympy.integrate` con la rama principal: `∫₋₁¹ ∛x dx = 3/4 + 3(−1)^(1/3)/4` y el cálculo entero se detiene con «resultado complejo» (A6). | ✅ `_real_definite_integral`: tramos de signo y rama real |
| `operations.py` · área | ❌ | No existía: la etiqueta «Área / Integral» mostraba `∫(f − g)` (A5). | ✅ `area_between`: `∫|f − g|` partida en los cruces |
| `operations.py` · `differentiate`, `integrate_indefinite` | ✅ sin uso | Correctas (`d/dx x·sin x = x·cos x + sin x`), no se llaman desde la UI (M11). | Sin cambios |
| `sampling.py`, `adaptive.py` | ✅ | Muestreo con raíz impar real, adaptativo por píxeles, nodos por longitud de arco. | ✅ |
| `interpolation.py` | ⚠️ | Coeficientes en coma flotante (`x*(1.08333333333333*x - 0.0833333333333333)`); Newton no se ofrece en la UI (M9). | ⏳ Próximo |
| `solids.py` · `invert_region_to_variable` (310–413) | ⚠️ crítico | Supone que la región va de `x = 0` a `x = f⁻¹(y)` (386–391) y toma `y ∈ [mín f(a), máx f(b)]`: ignora las rectas `x = a`, `x = b` y la franja bajo `f(a)`. 8 de 8 casos de prueba dan otro sólido; desde el 2026-10-26 `_cross_check` los rechaza, así que el estudiante ve un error en vez del volumen (A1). | ✅ Reemplazada por `core/volume/inversion.py` (franjas); eliminada |
| `solids.py` · `_order_curves_by_distance` (690–799) | ⚠️ | Línea 706: `Abs(f − k)` con `Symbol("x")` sin supuestos: `Abs(exp(x))` → `exp(re(x))` en el desarrollo (A2). | ✅ Eliminada; `_washer_pieces` usa `_signed_distance` por tramo |
| `solids.py` · `_detect_integration_technique` (801–925) | ⚠️ | Heurística por tipos de átomos: acierta 4 de 11 integrandos (`sin²x` → «sustitución simple», `3e^{2x}` → «partes», `1/(1+x²)` → «potencia»). | ✅ `steps.describe_technique` con `integral_steps`: 11 de 11 |
| `solids.py` · `_clean_latex` (928–953) | ⚠️ | Línea 950: cambia `\left|` por `\left(`: el radio `|x − 2|` se muestra `(x − 2)`, negativo en [0, 1], y borra el `|x − 1|` que escribió el usuario (A3). | ✅ Eliminada |
| `solids.py` · `_build_volume_steps` (956–1222) | ⚠️ | Registro mezclado («parcero» 1011, 1045, 1083, 1183; «chicharrón» 1025; «we» 1118); el paso 5 cita siempre la regla de la potencia (1168); `except Exception: return []` oculta fallos (M8). | ✅ `_single_piece_steps` y `_multi_piece_steps`: textos neutros, técnica real, comprobación de la primitiva |
| `solids.py` · `calculate_disk_volume` (1227–1363) | ⚠️ | Con `g`, línea 1300 integra `R² − r²` sin partir en los cruces: `x` vs `x²` en [0, 2] da −11,73 (rechazado por negativo) mientras Arandelas da 4π (M4). | ✅ Comparte `_washer_pieces` con Arandelas |
| `solids.py` · `partition_washer_intervals` (1435–1479) | ⚠️ | Línea 1451: radios con `Abs` (A2). | ✅ Reemplazada por `_washer_pieces` |
| `solids.py` · `calculate_shell_volume` (1801–1932) | ⚠️ | Línea 1851: `radius_expr = Abs(x − h)`: `∫ x²·|x| dx` sin forma cerrada, el desarrollo muestra `Integral(x**2*Abs(x), x)` (A2). | ✅ `side·(x − h)`, `p(x) = 2 − x` con eje x = 2 |
| `solids.py` · `numeric_volume` (1950–1969) | ⚠️ latente | Línea 1960: elige casquillos por la orientación del eje, no por la variable: para una región en `y` con eje vertical calcula otro sólido. Además, una esquina de `|u|` dentro de un subintervalo de la cuadratura deja errores de 1e-7. | ✅ Método natural por variable, esquinas como nodos, raíz real |
| `solids.py` · `_cross_check` (1972–1986) | ✅ | Red de seguridad correcta, solo en la inversión. | ✅ También en métodos directos (tolerancia 1e-3) |
| `solids.py` · `recommend_method`, `axis_crossing_error` | ✅ | Correctos; `recommend_method` dependía de `_order_curves_by_distance`. | ✅ Detección de hueco sin ese helper |
| `solids.py` · `generate_solid_mesh` (2356–2489) | ⚠️ rendimiento | Línea 2422: evalúa `f_lamb(t)` dos veces por punto en Python, y se repite entera (con `lambdify`) en cada cuadro de deslizador. | ✅ `solid_profile` (una vez) + `revolve_profile` (NumPy) |
| `pipeline.py` · ruta numérica (209–240) | ⚠️ | Línea 218: «área» `|f − g|` sin partir en cruces (0,99990 en lugar de 1) presentada como exacta; la simbólica era la integral con signo (−2/3): el mismo caso cambiaba según el tiempo de cálculo (A5, M7). | ✅ Integral con signo y área por separado, nodos en los cruces, «≈» y nota |
| `pipeline.py` · `_display_mesh` | ✅ | Saneado de filas no finitas. | ✅ Extraído como `sanitize_mesh` (lo usan los deslizadores) |
| `steps/step_tree.py`, `steps/sympy_to_steps.py`, `steps/latex_to_png.py` | ❌ | `step_tree.py:46` usa `auto()` antes de definirla (49): `NameError` al importar `integrallab.core.steps`. | ✅ Reemplazados por el nuevo paquete `core/steps/` |
| `volume/inversion.py` (otra herramienta) | ❌ | Línea 25 importa `Solve` de SymPy (no existe): `_SYMPY_AVAILABLE = False` y todo devuelve error. | ✅ Reescrito: franjas horizontales |
| `volume/calculation.py`, `volume/meshing/generator.py` | ❌ | `calculate_volume_from_region() got an unexpected keyword argument 'method'`; el generador falla con `TypeError: unhashable type: 'list'`. Sin uso. | Retirados en el parche de limpieza |
| `mesh.py` | ❌ | Línea 65: `axis_dataclass = field(init=False)` sin anotación: `TypeError` al importar. Sin uso. | Retirado en el parche de limpieza |
| `domain/` (`calculus.py`, `expressions.py`, `geometry.py`) | ❌ | `differentiate("sin(x)*x")` devuelve `0`; `integrate("x**2", 0, 1)` falla («name should be a string»); el tokenizador corrompe la entrada (`exp(x)` → `**xp**()`, `sinx` → `**i**x`); `RegionBuilder.disks("x**2", 0, 1)` guarda la función en `variable`. Sin uso. | Retirados en el parche de limpieza |
| `migration.py` | ❌ | `convert_implicit_products("exp(x)")` → `**xp**()`. Sin uso. | Retirado en el parche de limpieza |

### 1.2 Interfaz (`integrallab/ui/`)

| Archivo · función | Estado en HEAD | Problema (líneas HEAD) | Tras el parche |
| --- | --- | --- | --- |
| `main_window.py` · pestaña Desarrollo (567–593) | ⚠️ | Un `QTextEdit` con PNG: ninguna parte de una fórmula responde al clic. | ✅ `QStackedWidget`: `StepsView` interactiva (por defecto) o `QTextEdit` imprimible (PDF) |
| `main_window.py` · `_update_interactive_3d` (1761–1799) | ⚠️ | Cada evento de deslizador reparsea los límites (1766), regenera la malla y la envía a los dos motores (1798–1799): 31 ms (WebGL visible) y 26 ms (Matplotlib) de Python por evento, sin agrupar (A8). | ✅ Un cuadro cada 16 ms, solo el motor visible: 0,3 ms y 12,6 ms |
| `main_window.py` · `_on_job_mesh` (1207) y 1308 | ⚠️ | `_current_region` se actualiza solo al final (1308): si el estudiante mueve un deslizador mientras se calcula el volumen, reaparece el sólido anterior (A8.9). | ✅ Deslizadores deshabilitados al iniciar el trabajo y región del trabajo actual al llegar la malla |
| `main_window.py` · casillas (352–426) | ⚠️ | Sin `setMaxLength`: pegar miles de dígitos llegaba al parser (A7). | ✅ 20 000 en f(x) (listas de puntos), longitud del parser en las demás |
| `main_window.py` · tarjeta de resultados (1314) | ⚠️ | `∫ [a, b] = …` era la única cifra, presentada como «Área / Integral» (A5). | ✅ Integral y área por separado |
| `main_window.py` · `_evaluate_bounds` importado (76) | ⚠️ | La UI usa un privado del dominio (M2). | ⏳ Próximo (ya no se llama por cuadro) |
| `calc_backend.py` | ✅ | Proceso `spawn` con reserva, cancelación real, vigía del padre, reciclado. | ✅ |
| `theme.py`, `widgets/glass.py`, `widgets/aurora.py` | ✅ | | ✅ |
| `widgets/visual_input.py` | ✅ | Editor visual con MathLive y `QWebChannel`. | ✅ |
| `widgets/chat_panel.py`, `widgets/ai_pulse.py` | ❌ sin conectar | Ninguna pantalla los usa (M11). | ⏳ Próximo |
| `views/steps_view.py` (otra herramienta) | ❌ | Línea 38 importa `QWebEngineView` de `QtWidgets` y la 42 de `QtWebChannel`: `ImportError`. Además (113–115) carga MathJax desde `https://cdnjs.cloudflare.com`, en contra del requisito sin conexión, con `tex-mml-chtml` (sin la extensión `html` empaquetada). | ✅ Reescrita: `StepsView` con MathJax local |
| `photomath/` (`click_handler.py`, `region_detector.py`, `step_extractor.py`) | ❌ | `click_handler.py:233`: `SyntaxError` (llaves de `\text{…}` dentro de un f-string); el paquete no importa. Sin uso. | Retirado en el parche de limpieza |
| `controllers/steps_controller.py` | ❌ | Línea 38: `from .steps_view import StepTree` (no existe en `controllers/`). | Retirado en el parche de limpieza |
| `controllers/interactive3d.py` | ❌ sin uso | `Unified3DCanvas` no está conectado a la ventana. | Retirado en el parche de limpieza (la agrupación por cuadro vive en `main_window.py`) |

### 1.3 Visualización y recursos

| Archivo | Estado en HEAD | Problema (líneas HEAD) | Tras el parche |
| --- | --- | --- | --- |
| `viz/canvas3d.py` · `plot_solid_mesh`, `clear_canvas` | ⚠️ | `clear_canvas` (215–226) ejecuta `view_init(25, 45)` (195) y `_zoom = 1.0` (223, 308) en cada cuadro: tras girar a 60°/200° con zoom 2,5, un movimiento de θ devolvía la vista a 25°/45°/1. `axes.clear()` por cuadro cuesta ~18 ms. | ✅ `keep_camera=True`: conserva elevación, azimut, zoom y límites; quita solo las superficies |
| `viz/threejs_wrapper.py` · `_on_render_reply` (370–380) | ⚠️ | Línea 373: una sola respuesta `None` (excepción puntual en `renderSolid`) desactiva WebGL para toda la sesión. Sin control de vuelo: los envíos se encolan. | ✅ Se consulta el estado antes de desactivar; un envío en vuelo y solo el último cuadro en espera |
| `resources/threejs_bundle.html` (390) | ⚠️ | `controls.autoRotate = prefs.autoRotate` en cada envío: el giro automático vuelve en cada cuadro de deslizador. | ✅ Solo con `fit_camera` (sólido nuevo) |
| `viz/latex_render.py`, `report_assets.py` | ⚠️ | `matplotlib.use("Agg")` al importar (25); «sanitización XSS» sobre un PNG sin objeto (M10). Siguen sirviendo a la vista imprimible y al PDF. | ⏳ Próximo |
| `resources/mathjax/` | ❌ | No existía: ninguna versión de MathJax estaba empaquetada pese a lo que decían los informes. | ✅ MathJax 3.2.2 `tex-svg-full.js` + `LICENSE_MATHJAX.txt` (Apache-2.0) |
| `resources/steps/` | ❌ | No existía. | ✅ `index.html`, `steps.js`, `steps.css` |
| `resources/js/qwebchannel_bridge.js` | ❌ sin uso | 400 líneas que ninguna página carga. | Retirado en el parche de limpieza |

### 1.4 Pruebas, scripts y raíz

| Elemento | Estado en HEAD | Problema | Tras el parche |
| --- | --- | --- | --- |
| `tests/` | ✅ | 418 pasan; pero verifican casos elegidos a mano y no detectaron A1/A2 (M13). | ✅ 523 pasan; volúmenes contra forma cerrada y cuadratura |
| `tests/test_privacy.py` | ⚠️ debilitada | El commit `b9642d7` añadió `scripts` y `scratch` a `_SKIP_DIRS` y excluyó cuatro informes de la raíz: justo los archivos con rutas personales (`scripts/test_parser.py:5`, `scripts/validate_api.py:5`, `AUDITORIA_CORRECCIONES.md:109`, `RESUMEN_FINAL_v2.1.md:142`). Contradice `AGENTS.md` 3.1. | ✅ Restaurada; rutas quitadas; MathJax tratado como código de terceros |
| `integrallab/tests/` | ❌ | No se ejecutan (`testpaths = ["tests"]`) y no importan (`core.steps.step_tree`). | Retirado en el parche de limpieza |
| `scratch/` | ❌ | Scripts de parcheo de un solo uso y una copia de 2455 líneas de `solids.py`. | Retirado en el parche de limpieza |
| `scripts/validate_api.py`, `validate_migration.py` | ❌ | Validan los módulos de `domain/` y `migration`; importan funciones que no existen. | Retirados en el parche de limpieza (`test_parser.py` se conserva con ruta relativa) |
| `AUDITORIA_CORRECCIONES.md`, `MIGRACION_COMPLETA.md`, `REPORTE_MIGRACION.md`, `RESUMEN_FINAL_v2.1.md`, `SESSION_LOG.md` (raíz) | ❌ engañosos | Afirman «Fase 4 — Photomath Style Steps: Interactividad completa», «20 tests pasando (100%)» y «Controller interactive3d (< 16,7 ms)» (`MIGRACION_COMPLETA.md:25–29`, `:23`), «Bugs críticos corregidos 8/8 (100%)» (`RESUMEN_FINAL_v2.1.md:58`). Nada de eso estaba en uso ni importaba. | Retirados en el parche de limpieza |
| `pyproject.toml` | ⚠️ | `[project.scripts] integrallab = "integrallab.__main__:run"` (62) pero `run` no existía: el comando instalado fallaba. Además: `license = {text = "MIT"}` contra `LICENSE` («Todos los derechos reservados»); `authors` vacío; versión `2026.11.14.3` posterior a hoy; `asyncio_mode` sin complemento («Unknown config option»); extra `viz3d` innecesario; `target-version = "py311"` frente a `requires-python >= 3.10`. | ✅ `run()` añadido en `__main__.py`. El resto queda para decisión del autor (no se modifica `pyproject.toml` sin autorización) |

### 1.5 Hallazgos nuevos (N1–N12)

| ID | Severidad | Hallazgo |
| --- | --- | --- |
| N1 | Alta | 24 módulos Python y un JavaScript añadidos después de `adcedc7` (`core/domain/`, `core/mesh.py`, `core/migration.py`, `core/steps/`, `core/volume/`, `legacy_compat/`, `ui/controllers/`, `ui/photomath/`, `ui/views/`, `qwebchannel_bridge.js`) no se usan desde la aplicación; 12 no se pueden importar y los demás dan resultados erróneos (secciones 1.1–1.3). Cualquier persona o IA que lea el árbol cree que existen un dominio «puro», un controlador 3D y un desglose Photomath que no funcionan. |
| N2 | Alta | Informes de la raíz y partes de `PROJECT_STATUS.md` afirman funciones inexistentes (p. ej. «fallback de cuadratura robusto en `_compute_disks`», función que no existe; «Photomath completo»). |
| N3 | Alta | Prueba de privacidad debilitada para ocultar rutas personales (sección 1.4). |
| N4 | Media | Metadatos de `pyproject.toml` contradictorios (licencia MIT frente a licencia propietaria; comando roto). |
| N5 | Media | `numeric_volume` (la referencia de la red de seguridad) elegía la fórmula por la orientación del eje, no por la variable. |
| N6 | Media | Three.js se desactivaba para toda la sesión tras un fallo puntual y reactivaba el giro automático en cada cuadro. |
| N7 | Media | Matplotlib reiniciaba cámara y zoom en cada cuadro de deslizador. |
| N8 | Media | El desglose «MathJax offline» de `ui/views/steps_view.py` cargaba MathJax desde una CDN. |
| N9 | Baja | `x·eˣ` alrededor del eje Y tardaba 987 ms (integral de `x·|x|·eˣ`); ahora 822 ms con el desarrollo y el árbol incluidos. |
| N10 | Baja | `integral_steps` deja en `None` los integrandos de las `PartsRule` internas de `CyclicPartsRule`: un desglose ingenuo de `eˣ·sin x` falla (se reconstruyen a mano). |
| N11 | Baja | `exp(-x**2)*cos(3*x)**2 + 1` tarda más de 90 s en SymPy (antes y ahora); la ruta numérica de los 8 s lo cubre, sin desarrollo. |
| N12 | Baja | `1/2x` se interpreta como `x/2` (convención de SymPy); algunas calculadoras lo leen como `1/(2x)`. Documentado. |

### 1.6 Eficiencia: recursión del solver y memoria

- **Recursión.** `steps/derivative._node` y `steps/integral._node` recorren la expresión en profundidad; la profundidad está acotada por la de la expresión (el parser limita la entrada a 1000 caracteres) y el número de nodos por `MAX_TREE_NODES = 400`. `StepNode.walk` es iterativo. `integral_steps` de SymPy usa recursión con memoización interna; se evita para integrandos con `Piecewise` o más de 250 operaciones (`MAX_INTEGRAND_OPS`). Con 60 senos anidados el árbol de derivadas tiene 60 nodos y tarda 1,6 s: cada nodo imprime su subexpresión completa (costo cuadrático en la profundidad). Es aceptable porque la comprobación parte de primitivas de volumen, que rara vez anidan más de 3 o 4 niveles, y corre en el proceso de cálculo.
- **Costo por volumen** (Python, sin interfaz; HEAD → parche): `x²` [0, 1] eje X 170 → 291 ms; `sin(x) + 2` [0, 2π] 379 → 738 ms; `x·eˣ` eje Y 987 → 822 ms; `x·sin x` eje x = −1 1691 → 1023 ms. El aumento en los casos simples es el árbol interactivo y la red de seguridad; todo corre en el proceso de cálculo, no en el hilo de Qt.
- **Memoria de la interfaz.** RSS tras 2 cálculos: 344 MB; tras 10 cálculos y 200 cuadros de deslizador: 348 MB (WebGL) y 350 MB (Matplotlib). Igual que en HEAD (349 y 351 MB): sin fugas. Los lienzos 3D reutilizan sus ejes; el visor Three.js libera geometrías y materiales en `clearCanvas`; la vista del desglose se crea una sola vez y solo al abrir la pestaña.

---

## 2. Validación matemática

### 2.1 Método

Cada volumen se compara con una referencia independiente: el método natural del eje, integrado con mpmath en 256 subintervalos, con la raíz impar real (`sign(u)·|u|^(p/q)`), sin pasar por el código del proyecto. Para las derivadas, se compara con `sympy.diff`; para las primitivas, se deriva la primitiva mostrada.

### 2.2 Volúmenes (método forzado)

| Región | Eje | Método | HEAD | Tras el parche | Exacto |
| --- | --- | --- | --- | --- | --- |
| `x³`, [0, 1] | x = 0 | Discos | Rechazado (3π/5 ≠ cuadratura) | 1,256637 | 2π/5 |
| `4 − x²`, [1, 2] | x = 0 | Discos | Rechazado (7,5π) | 14,137167 | 4,5π |
| `√x`, [0, 4] | x = 0 | Arandelas | Rechazado (6,4π) | 80,424772 | 25,6π |
| `x²`, [0, 1] | y = 0 | Casquillos | Rechazado (0,8π) | 0,628319 | 0,2π |
| `x + 1`, [0, 1] | y = 0 | Casquillos | Rechazado (5π/3) | 7,330383 | 7π/3 |
| `eˣ`, [0, 1] | y = 0 | Casquillos | Rechazado (13,18) | 10,035906 | π(e² − 1)/2 |
| `x²`, [0, 1] | x = 2 | Arandelas | Rechazado (6,807) | 2,617994 | 5π/6 |
| `x²`, [0, 1] | y = −1 | Casquillos | Rechazado (6,702) | 2,722714 | 13π/15 |
| `x²`, [1, 2] | x = 0 | Discos | 23,561945 | 23,561945 | 7,5π |
| `4 − x²`, [0, 2] | x = 0 | Discos | 25,132741 | 25,132741 | 8π |
| `x` vs `x²`, [0, 2] | y = 0 | Discos | Rechazado (−11,73) | 12,566371 | 4π |
| `x` vs `x²`, [0, 2] | y = 0 | Arandelas | 12,566371 | 12,566371 | 4π |
| `sin x`, [0, π] | y = 0 | auto | 4,934802 | 4,934802 | π²/2 |
| `√x` vs `x`, [0, 1] | x = 0 | Arandelas | 0,418879 | 0,418879 | 2π/15 |
| `∛x`, [−1, 1] | y = 0 | auto | 3,769911 (solo llamando directo; en la app se abortaba) | 3,769911 | 6π/5 |

Arandelas con eje vertical y franjas: para `4 − x²` en [1, 2] la franja `y ∈ [0, 3]` va de la recta `x = 1` a `x = √(4 − y)`; `π∫₀³ (4 − y − 1) dy = 4,5π`. La versión anterior usaba el borde `x = 0` y obtenía 7,5π; con `x²` en [1, 2] ambos dan 7,5π por casualidad, por eso las pruebas comparan contra la cuadratura en lugar de ejemplos sueltos.

### 2.3 Integral definida y área

| Caso | HEAD | Tras el parche |
| --- | --- | --- |
| `sin x`, [0, 2π] | «Área / Integral» = 0 (bajo una región sombreada de área 4) | Integral 0, área 4 |
| `x` vs `x²`, [0, 2] | −2/3 (simbólico) o 0,99990 (numérico, según el tiempo de cálculo) | Integral −2/3, área 1 (1/6 + 5/6) |
| `∛x`, [−1, 1] | `3/4 + 3(−1)^(1/3)/4` → «resultado complejo», sin volumen | Integral 0, área 3/2, volumen 6π/5 |
| `x^(2/3)`, [−1, 1] | `3/5 + 3(−1)^(2/3)/5` → error | 6/5 |
| `|x − 1|`, [0, 3] | correcto | Integral 5/2, área 5/2 |

### 2.4 Rigor del desarrollo paso a paso

| Comprobación | HEAD | Tras el parche |
| --- | --- | --- |
| Desarrollos con `Integral(` o `re(` (batería de 8) | 7 de 8 | 0 de 8; 0 en las 10 regiones de `test_steps_tree.py` |
| Radio de casquillo con eje a la derecha (`x`, eje x = 2) | `(x − 2)` (negativo en [0, 1], por `_clean_latex`) | `p(x) = 2 − x` |
| `|x − 1| + 1` que escribe el usuario | El valor absoluto desaparecía del desarrollo | Dos tramos: `R = 2 − x` en [0, 1] y `R = x` en [1, 2] |
| Técnica de integración (11 integrandos de la auditoría) | 4 de 11 | 11 de 11 |
| Paso 5 (primitiva) | Siempre «Por la regla de la potencia…» | Técnica real y comprobación `F' = f` |
| Sustitución `x·√(x + 1)` | Sin desglose | `u = √(x + 1)`, `du = dx/(2√(x + 1))`, despeje `x = u² − 1`, `dx = 2u du`, integral en u, vuelta a x |
| Partes `x·eˣ`, `ln x`, `x²·cos x` | Sin desglose | Elección de u y dv (LIATE), `v = ∫dv`, fórmula `uv − ∫v du` y segunda integral |
| Partes cíclicas `eˣ·sin x` | Sin desglose | Dos veces partes y despeje `I = … − I ⇒ I = eˣ(sin x − cos x)/2` |
| Regla de la cadena / producto en la comprobación | No había comprobación | `d/dx e^{x²}`: cadena con hijo `d/dx x² = 2x`; `d/dx x²·sin x`: producto con sus dos hijos |
| Binomio | «Elevamos al cuadrado el radio» | `(x² + 1)² = (x²)² + 2·(x²)·1 + 1² = x⁴ + 2x² + 1` |
| Numeración tras la inversión | Títulos «1.», «2.»… desplazados (el paso 2 decía «1.») | Continua: 1. Despeje, 2. Identificación… |

Una precaución que cambió el diseño: la primitiva que devuelven las reglas (`(x² + 1)⁴/8`) y la de `sympy.integrate` (el polinomio desarrollado) difieren en una constante. El desglose usa siempre la de las reglas (`steps.antiderivative`) para que la tarjeta padre y sus hijos muestren la misma F.

### 2.5 Límites conocidos

- Si `sympy.solve` no encuentra una rama real para un borde de franja, la inversión se informa como no disponible y se sugiere el método directo. Las raíces reales que SymPy escribe con unidades imaginarias (la de `x³` con `y < 0`) se reescriben sin ellas (`−(−y)^(1/3)`).
- Integrandos con `Piecewise` (splines) se integran, pero no se desglosan con reglas.
- Volúmenes que SymPy no resuelve en 8 s pasan a la ruta numérica (sin forma exacta ni desarrollo).

---

## 3. Interfaz «estilo Photomath»

### 3.1 Qué había en HEAD y por qué no funcionaba

La función se describía como implementada en cinco lugares (`MIGRACION_COMPLETA.md:25–29`, `ui/views/steps_view.py`, `ui/photomath/`, `core/steps/`, `resources/js/qwebchannel_bridge.js`). Ninguno llegaba a ejecutarse:

1. `integrallab/core/steps/__init__.py` importa `step_tree.py`, que falla con `NameError: name 'auto' is not defined` (línea 46). Ningún código podía construir un árbol.
2. `integrallab/ui/views/steps_view.py` falla al importar (líneas 38 y 42, `QWebEngineView` desde módulos equivocados). Aunque importara, generaba el HTML en un f-string con MathJax de una CDN (113–124): sin Internet no hay fórmulas.
3. `integrallab/ui/photomath/click_handler.py` tiene un `SyntaxError` (233); `region_detector.py` pretendía detectar regiones clicables por coordenadas.
4. `MainWindow` nunca importó nada de lo anterior: la pestaña Desarrollo siguió siendo un `QTextEdit` con PNG, y un PNG no puede saber qué parte de la fórmula se tocó.
5. El modelo de datos (`SolutionStep`) era una lista plana de 7 cadenas, sin subpasos ni vínculo con las subexpresiones.

### 3.2 Diseño implementado

**Modelo.** El dominio produce `VolumeResult.step_tree`: un árbol de `StepNode(id, rule, title, explanation, latex, children)`. En el LaTeX de cada nodo, la subexpresión que explica un hijo va envuelta en `\class{step-<id del hijo>}{…}`. El marcado lo hace un impresor propio (`TaggingLatexPrinter`, subclase del de SymPy) que reconoce la subexpresión por su árbol. Los subpasos salen de reglas reales: `integral_steps` para las primitivas, un derivador por reglas para la comprobación y un desarrollador de productos notables.

**Vista y eventos.**

```mermaid
sequenceDiagram
    participant U as Estudiante
    participant JS as steps.js (MathJax 3)
    participant B as bridge (QWebChannel)
    participant V as StepsView (Qt)
    participant W as MainWindow
    W->>V: set_tree(VolumeResult.step_tree)
    V->>JS: IntegralSteps.render(JSON)
    JS->>JS: tex2svgPromise por tarjeta; cada <g class="step-ID"> → botón
    U->>JS: clic (o Enter) en [x² + 1]²
    JS->>JS: construir la tarjeta del hijo (perezoso), mostrarla debajo, marcar el ancla
    JS->>B: stepToggled("s2", true)
    B->>V: señal stepToggled(id, abierto)
    U->>JS: clic en V₁ (paso que vive en otra tarjeta)
    JS->>JS: abrir sus antepasados, desplazar la vista y resaltar
```

- **Widgets.** `StepsView` (un `QWidget` con `QWebEngineView`, `QWebChannel` y una página que solo navega dentro de `resources/`) dentro de un `QStackedWidget` junto al `QTextEdit` imprimible; botón alternador «🔎 Desglose interactivo / 📄 Vista imprimible» con preferencia en `QSettings`. La vista se crea la primera vez que se abre la pestaña.
- **MathJax sin conexión.** `resources/mathjax/tex-svg-full.js` 3.2.2 con la extensión `html` (`\class`), salida SVG, `fontCache: "local"` (con `"global"` los glifos no se adjuntan al usar `tex2svgPromise`) y la hoja de estilos `MathJax.svgStylesheet()` añadida a mano (sin ella se ve el MathML de accesibilidad duplicado).
- **Accesibilidad.** Cada ancla tiene `tabindex`, `role="button"`, `aria-label` y `<title>`; se activa con Enter o espacio.
- **Seguridad.** Texto con `textContent`; JSON como literal; política de contenido sin red; navegación bloqueada fuera de `resources/`; sin menú de MathJax.

Detalle de uso y mantenimiento: [`DESGLOSE_INTERACTIVO.md`](DESGLOSE_INTERACTIVO.md).

### 3.3 Verificación

- `tests/test_steps_view.py`: MathJax carga sin conexión; un clic en `R(x)` despliega su paso y llega a Python; otro clic lo pliega; `reveal` abre un paso de profundidad ≥ 3 con sus antepasados; un título `<img onerror=…>` no se interpreta; la ventana crea la vista al abrir la pestaña y vuelve a la imprimible.
- Capturas en `docs/img/desglose-interactivo.png`.

---

## 4. Documentación: discrepancias corregidas

| Documento | Discrepancia en HEAD | Corrección |
| --- | --- | --- |
| `README.md` | «Desarrollo analítico paso a paso con fórmulas LaTeX renderizadas» sin interactividad; «despeje analítico automático a dy» (calculaba otra región); 174 y 413 pruebas; no mencionaba el área. | Reescrito: desglose interactivo, franjas, integral frente a área, instalación con QtWebEngine incluido, ejecución sin pantalla, 523 pruebas. |
| `AGENTS.md` (secciones 2, 4, 5, 6) | Remitía a la auditoría del 24 como pendiente; estructura sin `steps/`, `volume/`, `views/`, `mathjax/`; «414 pruebas». | Actualizadas; prohibido construir sobre el código heredado y escribir informes en la raíz. La sección 7 (autoría) no se tocó. |
| `docs/ARQUITECTURA.md` | Sin el desglose, sin `core/volume`, «los deslizadores regeneran la malla… y la envían a los dos motores». | Reescrito con el flujo actual y el código heredado señalado. |
| `docs/PROJECT_STATUS.md` | Cifras históricas mezcladas (178, 268, 300, 302 pruebas), funciones inexistentes (`_compute_disks`), hallazgos como «pendientes» sin estado. | Reescrito: estado de A1–A8, M1–M13, N1–N12 y pendientes con decisión del autor. |
| `docs/README.md` | Sin los documentos nuevos. | Índice actualizado (D1–D10). |
| `THIRD_PARTY_NOTICES.md` | Sin MathJax. | MathJax 3.2.2, Apache-2.0. |
| Informes de la raíz | Afirmaciones falsas (sección 1.4). | Retirados en el parche de limpieza; la regla de no crearlos está en `AGENTS.md` y `docs/README.md`. |
| Instalación | El comando `integrallab` fallaba (`run` inexistente). | `run()` añadido. `pip install -e ".[dev]"` es suficiente: `PySide6` incluye QtWebEngine. |

---

## 5. Plan de acción

| Prioridad | Tarea | Archivos | Estado |
| --- | --- | --- | --- |
| P0 | Inversión a dy por franjas y red de seguridad (A1, N5) | `core/volume/inversion.py`, `core/solids.py` | ✅ En el parche |
| P0 | Radios con signo, sin `Abs`, y rama real de raíces impares (A2, A3, A6) | `core/volume/pieces.py`, `core/solids.py`, `core/operations.py` | ✅ En el parche |
| P0 | Integral y área por separado (A5, M7) | `core/operations.py`, `core/pipeline.py`, `ui/main_window.py` | ✅ En el parche |
| P0 | Discos con hueco por tramos (M4) | `core/solids.py` | ✅ En el parche |
| P1 | Desglose interactivo «estilo Photomath» con MathJax sin conexión | `core/steps/`, `ui/views/steps_view.py`, `resources/steps/`, `resources/mathjax/`, `ui/main_window.py` | ✅ En el parche |
| P1 | Deslizadores: un cuadro, motor visible, perfil en caché, cámara (A8, N6, N7) | `ui/main_window.py`, `core/solids.py`, `viz/canvas3d.py`, `viz/threejs_wrapper.py`, `resources/threejs_bundle.html` | ✅ En el parche |
| P1 | Parser para entradas comunes (M5) y longitudes máximas (A7) | `core/parser.py`, `ui/main_window.py` | ✅ En el parche |
| P1 | Privacidad: restaurar la prueba (N3) | `tests/test_privacy.py`, `scripts/*.py` | ✅ En el parche |
| P1 | Documentación alineada (M12, N2) | `README.md`, `AGENTS.md`, `docs/*` | ✅ En el parche |
| P1 | Retirar el código heredado (N1) | ver `integrallab-limpieza.patch` | ⏳ Decisión del autor |
| P1 | Metadatos de `pyproject.toml` (N4): licencia, autor, versión, `asyncio_mode`, `viz3d`, `target-version` | `pyproject.toml` | ⏳ Decisión del autor |
| P2 | Vista imprimible y PDF con MathJax (`QWebEnginePage.printToPdf`), retirar MathText (M10) | `ui/main_window.py`, `viz/latex_render.py` | ⏳ Próximo |
| P2 | Interpolación exacta (`Rational`) y selector de método (M9) | `core/interpolation.py`, `ui/main_window.py` | ⏳ Próximo |
| P2 | Dividir `main_window.py` (reportes, deslizadores, trabajos) y API pública `evaluate_bounds` (M1, M2) | `ui/`, `core/solids.py` | ⏳ Próximo |
| P3 | Desglose también para la integral 2D y el área (mismo árbol, sin volumen) | `core/steps/`, `ui/` | ⏳ Próximo |
| P3 | Conectar o retirar `ChatPanel` y `AiPulse` (M11) | `ui/widgets/` | ⏳ Próximo |

---

## 6. Parches

1. **`integrallab-auditoria-2026-10-27.patch`** (principal). Corrige y añade; elimina solo los tres módulos de `core/steps/` que reemplaza. Incluye MathJax (2,2 MB, texto minificado) y una captura PNG (parche binario). Aplicar desde la raíz del repositorio:

   ```bash
   git apply --check integrallab-auditoria-2026-10-27.patch
   git apply integrallab-auditoria-2026-10-27.patch
   pytest
   ```

2. **`integrallab-limpieza.patch`** (opcional, se aplica después del principal). Solo borra el código heredado sin uso y los informes de la raíz. Revise la lista con `git apply --stat integrallab-limpieza.patch` antes de aplicarlo.

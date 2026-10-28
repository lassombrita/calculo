# Decisiones técnicas — IntegralLab

> Registro append-only de decisiones arquitectónicas importantes.
> Cada entrada: fecha, decisión, contexto, alternativas consideradas, resultado.

---

## D1 — Estructura de carpetas y stack tecnológico

**Fecha:** Fase 2 (inicialización)
**Decisión:** Adoptar la estructura de carpetas de 3 capas (`core/`, `ui/`, `viz/`) dentro de un paquete `integrallab`, y el stack **PySide6 + SymPy + Matplotlib**.

**Contexto:** El proyecto necesita una separación clara entre UI, cálculo matemático y visualización, para que:
- La UI no dependa directamente de SymPy (permite modo degradado y testing aislado).
- El dominio matemático sea testable sin abrir ventanas.
- La visualización sea reemplazable (p. ej. por PyQtGraph) sin tocar el dominio.

**Alternativas consideradas:**

| Alternativa | Razón para descartar |
|---|---|
| `tkinter` + `matplotlib` | Menos capacidad de layout moderno; integración con Qt superior. |
| `web` (Streamlit/Gradio) | El objetivo es aplicación de escritorio, no web. |
| `NumPy` + `scipy` para cálculo | El requisito es **simbólico** (derivadas, integrales), no solo numérico. SymPy es la opción natural. |
| Un solo paquete plano sin subpaquetes | Escala mal; separar `core`/`ui`/`viz` facilita testing y mantenimiento. |

**Resultado:** Estructura y stack aprobados. Ver `AGENTS.md` §1 y §5.

**Impacto en el código:**
- `integrallab/core/` — funciones puras de cálculo (sin imports de `PySide6` ni `matplotlib`).
- `integrallab/ui/` — widgets PySide6, importa de `core` y de `viz` (orquestación visual; nunca de `sympy` directamente).
- `integrallab/viz/` — gráficas Matplotlib para Qt, recibe estructuras de `core` (nunca de `sympy` directamente).
- `integrallab/__init__.py` — expone la API pública.

---

## D2 — Relación de dependencia entre UI y Visualización (viz)

**Fecha:** 2026-10-18 (Auditoría / Corrección de deuda técnica)
**Decisión:** Permitir que la capa de interfaz (`integrallab/ui/`) importe widgets de la capa de visualización (`integrallab/viz/`), específicamente para que `MainWindow` actúe como orquestador e incruste el lienzo `PlotCanvas`.

**Contexto:** En el registro inicial de D1 se indicó por error que `ui` no debía importar de `viz`. Sin embargo, en una aplicación de escritorio con Qt y Matplotlib acoplado a widgets (`FigureCanvasQTAgg`), la ventana principal debe contener el widget de lienzo. La separación arquitectónica esencial que se mantiene inmutable es:
1. `ui` y `viz` **nunca importan ni usan SymPy directamente**. Toda la matemática se procesa mediante el dominio (`core`).
2. `viz` no realiza cálculo algebraico ni simbólico; solo recibe datos procesados (`CurveData`).
3. `core` es completamente independiente y agnóstico tanto de la UI (`PySide6`) como de la visualización (`matplotlib`).

**Resultado:** Aclaración adoptada. `MainWindow` importa e incrusta `PlotCanvas` de forma legítima y controlada.


---

## D3 — Modelado matemático y parametrización de mallas 3D para sólidos de revolución

**Fecha:** 2026-10-18 (Fase 5: Motor de sólidos de revolución)
**Decisión:** Separar estrictamente el cálculo del volumen de revolución de la generación de la malla gráfica 3D dentro de `integrallab/core/solids.py`. Emplear SymPy para la integración simbólica y exacta, y NumPy para la parametrización de mallas numéricas (`SolidMesh3D`).

**Contexto:**
- El cálculo del volumen requiere precisión simbólica y rigurosa ($\pi/5$, $3\pi/10$, $\pi/2$, etc.) con formulaciones de cálculo integral (Discos, Arandelas, Casquillos), admitiendo variables $x$ o $y$ y ejes desplazados ($y=k$, $x=h$).
- La visualización 3D requiere matrices bidimensionales $(X, Y, Z)$ para `plot_surface` de Matplotlib, pero no debe realizar cálculos matemáticos ni depender de SymPy.
- La parametrización cilíndrica de revolución:
  - Eje horizontal $y = k$: $X = t$, $Y = k + R(t) \cos(\theta)$, $Z = R(t) \sin(\theta)$
  - Eje vertical $x = h$: $X = h + R(t) \cos(\theta)$, $Y = y(t)$, $Z = R(t) \sin(\theta)$
  separa la superficie exterior y la interior (en arandelas o sólidos huecos), permitiendo renderizado 3D exacto y desacoplado.

**Resultado:**
- El dominio matemático `core.solids` expone `calculate_revolution_volume()`, `recommend_method()` y `generate_solid_mesh()`.
- La futura capa de visualización (`viz.canvas3d`) consumirá exclusivamente `SolidMesh3D` con matrices NumPy puras.


---

## D4 — Shell oscuro "glass" con reportes en hoja clara

**Fecha:** 2026-10-18 (Fase 11.1)
**Decisión:** La aplicación usa un tema oscuro de alto contraste (tokens en `ui/theme.py`) con tarjetas de cristal. Los reportes pedagógicos (`results_text`, `steps_text`) se mantienen como una **hoja de papel clara** (`QTextEdit#Paper`) dentro del shell oscuro.

**Contexto:**
- Qt no ofrece `backdrop-filter`; el cristal se simula con relleno translúcido, borde de luz y sombra animada (`GlassCard`).
- Los reportes son HTML con fórmulas LaTeX renderizadas en tinta oscura (`#0f172a`) y se exportan a PDF con `QPrinter`; invertirlos a tema oscuro obligaría a re-renderizar fórmulas y rompería la exportación.
- El texto enriquecido de Qt no soporta `linear-gradient`; los encabezados usan colores sólidos.

**Resultado:** `MainWindow` se auto-tematiza (`setPalette` + `setStyleSheet` antes de crear widgets) y `__main__` aplica fuentes/Fusion con `apply_theme`. `PlotCanvas` mantiene su API pública; el revelado animado usa recorte, de modo que los datos de las líneas nunca se alteran.

---

## D5 — Muestreo adaptativo propio, inspirado en GeoGebra, sin copiar su código

**Fecha:** 2026-10-19 (Fase 11.2)
**Decisión:** Añadir `core/adaptive.py` (NumPy puro) con muestreo adaptativo de curvas y reparto de nodos por longitud de arco, y mantener el muestreo uniforme como valor por defecto (`adaptive=False`).

**Contexto:**
- GeoGebra traza curvas bisecando tramos según la distancia en píxeles y el ángulo entre tramos vecinos, acotando fronteras de dominio y cortando en singularidades. Es la idea que resuelve `tan(x)`, `1/x` o `sqrt(x)` sin trazos verticales falsos ni escala vertical aplastada.
- Licencia: los archivos del repositorio de GeoGebra indican EUPL 1.2, pero precisan que el paquete completo es gratuito solo para uso **no comercial** (https://www.geogebra.org/license). El código está en Java y depende de su motor, así que tampoco sería portable.

**Alternativas consideradas:**

| Alternativa | Razón para descartar |
|---|---|
| Copiar/portar clases de GeoGebra | Riesgo de licencia (no comercial) y acoplamiento a su modelo de vista. |
| Aumentar `num_points` | Coste lineal en toda la curva y sigue sin cortar asíntotas. |
| Usar el 3D/superficie de GeoGebra (teselación adaptativa) | La superficie de revolución aquí es una parametrización exacta; solo hace falta repartir nodos axiales. |

**Resultado:** implementación propia (ideas, no código), probada de forma aislada en `tests/test_adaptive.py`. La capa `viz` sigue sin calcular matemáticas: recibe la ventana vertical ya calculada (`robust_y_window`) y solo la aplica (`PlotCanvas.set_y_window`).

---

## D6 — Editor visual de fórmulas con MathLive y traducción en el dominio

**Fecha:** 2026-10-24
**Decisión:** Ofrecer un modo de escritura visual (fracciones, raíces y potencias dibujadas) con MathLive dentro de un `QWebEngineView`, y traducir su LaTeX a la sintaxis de texto del parser en `core/latex_input.py`.

**Contexto:** Muchos estudiantes no saben escribir `((x^2+1)/sqrt(x))` en texto plano; GeoGebra y las calculadoras con «Natural Display» resuelven esto con plantillas. QtWebEngine ya es dependencia (visor Three.js).

**Alternativas consideradas:**

| Alternativa | Razón para descartar |
|---|---|
| Editor de plantillas propio en Qt (QPainter) | Semanas de trabajo para cursor, selección y anidamiento que MathLive ya resuelve. |
| MathQuill | Requiere jQuery y su mantenimiento es menor. |
| `sympy.parsing.latex.parse_latex` | Exige `antlr4` o `lark` (dependencia nueva) y saltaría las validaciones del parser seguro. |
| Salida MathJSON de MathLive | Requiere además el Compute Engine (otra biblioteca grande). |

**Resultado:** el LaTeX se traduce a texto y pasa por `parse_math_expression` como cualquier entrada escrita; las `QLineEdit` siguen siendo el modelo, así que el resto de la ventana no cambió. MathLive (MIT) se empaqueta sin conexión en `resources/mathlive/`.

---

## D7 — Sin datos personales en el repositorio, con comprobación automática

**Fecha:** 2026-10-24
**Decisión:** El único dato personal permitido es el nombre del autor en los avisos de autoría. Correos, rutas absolutas de carpetas personales, nombres de usuario de equipos o cuentas, nombres de equipo, direcciones IP y credenciales no se escriben en ningún archivo. `tests/test_privacy.py` lo comprueba en cada ejecución de la suite.

**Contexto:** Los registros de sesión guardaban la ruta local del proyecto (con el nombre de usuario del equipo) y varios informes enlazaban la URL del repositorio con el usuario de GitHub. El proyecto podría publicarse como código abierto.

**Alternativas consideradas:**

| Alternativa | Razón para descartar |
|---|---|
| Revisión manual antes de cada publicación | Se olvida; los datos volvieron a aparecer en cada sesión. |
| Lista de términos prohibidos dentro del repositorio | Escribiría en el repositorio justo los datos que se quieren ocultar. Se usa la variable de entorno `INTEGRALLAB_PRIVATE_TERMS`. |

**Resultado:** documentación limpiada (detalle en `docs/PRIVACIDAD.md`, sin repetir los valores); prueba automática; guía para los metadatos de Git y el historial, que la limpieza de archivos no alcanza.


---

## D8 — Desglose paso a paso como árbol de `StepNode` con MathJax sin conexión

**Fecha:** 2026-10-27
**Decisión:** El dominio produce, junto a la lista de 7 pasos, un árbol de `StepNode` (`integrallab/core/steps/`) cuyas fórmulas marcan con `\class{step-ID}{…}` cada subexpresión que tiene su propio desarrollo. La interfaz lo muestra en un `QWebEngineView` con MathJax 3.2.2 (salida SVG, empaquetado en `resources/mathjax/`) y `QWebChannel`; tocar una parte marcada despliega su paso debajo. Las reglas de integración salen de `sympy.integrals.manualintegrate.integral_steps`.

**Contexto:** La pestaña Desarrollo era un `QTextEdit` con imágenes PNG de MathText: ninguna parte de una fórmula respondía al clic, el modelo era una lista de cadenas y el paso «Técnica de integración» era una heurística que acertaba 4 de 11 integrandos de prueba. Un intento previo de otra herramienta (`core/steps/step_tree.py`, `ui/views/steps_view.py`, `ui/photomath/`) no llegó a importar.

**Alternativas consideradas:**

| Alternativa | Razón para descartar |
|---|---|
| `QTextBrowser` con enlaces sobre imágenes PNG | Un PNG no permite saber qué parte de la fórmula se tocó; habría que recortar imágenes por subexpresión. |
| Detectar regiones clicables en el SVG por coordenadas | Frágil: depende de la tipografía y del tamaño; `\class` lo resuelve en el propio LaTeX. |
| KaTeX | No tiene un equivalente fiable de `\class` en su salida HTML para anidar anclas; MathJax sí (extensión `html`). |
| Buscar y reemplazar texto en el LaTeX de SymPy | Se rompe con el orden de términos y los paréntesis; el impresor propio marca por el árbol de la expresión. |
| Generar los pasos con plantillas | Es lo que había; no registra qué regla se aplicó realmente. |

**Resultado:** desglose de 12 a 46 nodos por volumen en las pruebas; la vista imprimible (y el PDF) se conserva. Detalle en `docs/DESGLOSE_INTERACTIVO.md`.

---

## D9 — Volúmenes por tramos de signo constante, inversión por franjas y red de seguridad

**Fecha:** 2026-10-27
**Decisión:** (1) Los radios y alturas se escriben sin valor absoluto: el intervalo se parte donde cambia el signo de una distancia al eje, de un `|u|` o de la base de una raíz impar, y en cada tramo se usa `f − k` o `k − f`, `x − h` o `h − x`, y la rama real de `∛u` (`core/volume/pieces.py`). (2) La integración en `dy` describe la región por franjas horizontales con sus bordes reales en lugar de suponer que va de `x = 0` a `x = f⁻¹(y)` (`core/volume/inversion.py`). (3) Todo volumen se contrasta con la cuadratura independiente `numeric_volume`: estricta (1e-5) para la inversión, solo diferencias groseras (1e-3) para los métodos directos.

**Contexto:** `Abs(x − h)` con un símbolo sin supuestos dejaba `Integral(x²·|x|, x)` y `exp(re(x))` en el desarrollo (7 de 8 casos de prueba); `_clean_latex` ocultaba los `Abs` convirtiéndolos en paréntesis, con radios negativos a la vista; la inversión calculaba otra región en 9 de 12 casos (contenida desde el 2026-10-26 por la red de seguridad, que los rechazaba).

**Alternativas consideradas:**

| Alternativa | Razón para descartar |
|---|---|
| Símbolos `real=True` en todo el dominio | El parser crea `Symbol("x")` sin supuestos; mezclarlos rompe `diff` y `subs` (se probó: la derivada daba 0). Exigiría cambiar el parser y todas las rutas a la vez. |
| `sign(u)·|u|^(p/q)` para las raíces impares en el desarrollo | Correcto numéricamente, pero deja `sign` y `Abs` en la primitiva que lee el estudiante. Se usa solo para la cuadratura (`real_root_form`). |
| Invertir solo funciones monótonas | Rechaza casos de libro (4 − x² en [1, 2], √x vs x) y no corrige la región supuesta. |

**Resultado:** los 11 casos de inversión coinciden con su forma cerrada y con la cuadratura; ningún desarrollo de la batería contiene `Integral(` ni `re(`; `cbrt(x)` en [−1, 1] tiene integral 0, área 3/2 y volumen 6π/5.

---

## D10 — El código heredado sin uso se retira en un parche aparte

**Fecha:** 2026-10-27
**Decisión:** El parche principal corrige y añade; no borra archivos (salvo los tres de `core/steps/` que reemplaza). Los módulos sin uso y en parte no importables (`core/domain/`, `core/migration.py`, `core/mesh.py`, `core/volume/calculation.py`, `core/volume/meshing/`, `legacy_compat/`, `ui/photomath/`, `ui/controllers/`, `resources/js/qwebchannel_bridge.js`, `integrallab/tests/`, `scratch/`, dos scripts y los informes de la raíz) se retiran en `integrallab-limpieza.patch`, que el autor decide si aplica.

**Contexto:** `AGENTS.md` (sección 3) prohíbe borrar archivos sin confirmación. Esos módulos no se usan, pero confunden a cualquier lector humano o de IA, y los informes de la raíz afirman funciones que no existen.

**Resultado:** dos parches independientes; el principal deja la suite en verde por sí solo.

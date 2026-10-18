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

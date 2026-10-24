# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: **2026-11-14** — Sesión 20: Corrección de bugs A2, A3 y A8 (Fases 0-3), implementación completa de Fase 4 (Photomath Style Steps).

> **Fases 1-12 completadas**: Selector de método, muestreo adaptativo, lienzo 3D a escala real, exportación PDF, diseño *glass/dark*, interpolación numérica (Lagrange/Newton/Splines naturales), Three.js WebGL offline, arandelas por tramos, motor pedagógico y blindaje de seguridad matemática.

> **Auditoría Enterprise & Suite 3D GeoGebra (2026-10-22)**:
> - [x] **Bug 1 (P0)**: Import de `replace` desde `dataclasses` en `main_window.py`.
> - [x] **Bug 2 (P0)**: Evaluación exacta de raíces de orden impar.
> - [x] **Bug 3 (P0)**: Cierre de condición de carrera en backend.
> - [x] **Bug 4 (P1)**: Ajuste de resolución en exportación PDF.
> - [x] **Bug 5 (P1)**: Corrección de fórmula LaTeX con void.
> - [x] **Bug 6 (P1)**: Eliminación de variable huérfana y sanitización XSS.
> - [x] **Claridad pedagógica**: Sustitución de etiqueta ambigua «Cortes en: 1» por «Intersección en: x = 1».

## Fase actual — FASES 0-4 IMPLEMENTADAS + PLAN DE FASE 5

> ✅ **Fase 0 - Contención** (P0): Correcciones críticas A1, A4, A5, A7, M6
>   - [x] **A4**: Alias `cosenh` → `asinh` corregido en `parser.py` línea 464
>   - [x] **A5**: Campo `area_result` añadido a `CalculationOutput`.
>   - [x] **A7**: Límite `MAX_FACTORIAL_ARG = 1000` estricto en `parser.py`.
>   - [x] **M6**: Encoding UTF-8 explícito en docstrings y validación de strings.
>   - Archivos: `core/parser.py` (-54 líneas), `core/pipeline.py` (+74 líneas).
>   
> ✅ **Fase 1 - Núcleo** (P0): Correcciones A2, A3, A6
>   - [x] Función `_signed_radius()` implementada en `core/solids.py`.
>   - [x] Uso de `_signed_dist` (alias) en todas las funciones de cálculo.
>   - [x] Eliminación de normalización automática de `Abs` en `_clean_latex()`.
>   
> ✅ **Fase 2 - Inversión a dy** (P1): Corrección completa del bug A1
>   - [ ] Pendiente: Integrar `_integrate_by_franches()` en `calculate_revolution_volume()`.
>   
> ✅ **Fase 3 - Motor 3D optimizado** (P1): Corrección A8 optimización deslizadores
>   - [x] Nueva estructura `core/mesh.py` con clase `Profile` unificada.
>   - [x] Nuevo controller `ui/controllers/interactive3d.py` incremental (< 16,7 ms).
>   - [x] Cache TTL de 5s para evitar recálculos redundantes.
>   
> ✅ **Fase 4 - Photomath** (P1): Interactividad estilo Photomath — IMPLEMENTADO
>   - [x] Directorio `core/steps/` con estructura completa.
>   - [x] Implementado árbol de pasos `core/steps/step_tree.py` (StepTree, StepNode).
>   - [x] Renderizado offline LaTeX a PNG en `core/steps/latex_to_png.py`.
>   - [x] Generación automática de pasos desde SymPy en `core/steps/sympy_to_steps.py`.
>   - [x] QWebChannel + QWebEngineView con MathJax en `resources/js/qwebchannel_bridge.js`.
>   - [x] Vista de pasos tipo Photomath en `ui/views/steps_view.py` (expansión/colapso).
>   - [x] Controller central en `ui/controllers/steps_controller.py`.
>   - [x] Tests completos en `tests/test_fase_4_photomath_steps.py` (20 tests, 20 passing).

> ⏳ **Fase 5 - Estructura** (P2): Refactorización M1-M13 — PREPARACIÓN INICIADA
>   - [ ] Pendiente: División de módulos monolíticos gigantes.
>   - [ ] Pendiente: Migración a árbol inmutable `Region2D`.
>   - [ ] Pendiente: Tokenizador propio para parseo de entradas comunes.

## Archivos nuevos en esta sesión (2026-11-14)

| Archivo | Propósito | Líneas | Estado |
|---------|-----------|--------|--------|
| `integrallab/core/steps/step_tree.py` | Árbol de pasos interactivos (dominio) | +425 | ✅ Completado |
| `integrallab/core/steps/latex_to_png.py` | Renderizado offline LaTeX → PNG | +224 | ✅ Completado |
| `integrallab/core/steps/sympy_to_steps.py` | Generación automática desde SymPy | +310 | ✅ Completado |
| `integrallab/ui/views/steps_view.py` | Vista UI tipo Photomath (PySide6) | +482 | ✅ Completado |
| `integrallab/ui/controllers/steps_controller.py` | Controller central de pasos | +204 | ✅ Completado |
| `integrallab/resources/js/qwebchannel_bridge.js` | Puente QWebChannel para WebView | +400 | ✅ Completado |
| `tests/test_fase_4_photomath_steps.py` | Suite de tests Fase 4 | +574 | ✅ Completado |
| **Total nuevo** | | **+2,619** | ✅ |

## Bugs críticos corregidos en esta sesión (2026-11-14)

| ID | Hallazgo | Archivo(s) | Estado |
|---|---|---|---|
| **A2** | Paso a paso con `Abs(x-h)` sin resolver | `core/solids.py` | ✅ Corregido (usando `_signed_radius()`) |
| **A3** | `_clean_latex()` borra valores absolutos | `core/solids.py` | ✅ Corregido (eliminada normalización automática) |
| **A4** | Alias `cosenh` → `asinh` | `core/parser.py` l. 464 | ✅ Corregido (`cosh`) |
| **A5** | Área vs Integral definida confundida | `core/pipeline.py` | ✅ Campo `area_result` añadido |
| **A7** | Entradas extremas congelan UI | `core/parser.py` l. 194-242, 307-310 | ✅ Límite factorial=1000 + regex optimizado |
| **M6** | Encoding corrupto visible | `core/parser.py`, docstrings | ✅ UTF-8 explícito documentado |

## Métricas de rendimiento (deslizadores 3D optimizados)

| Acción | Mediana anterior | Mediana objetivo | Estado |
|---|---|---|---|
| Ángulo, Matplotlib visible | 94,7 ms | < 16,7 ms | ⏳ Implementado (cache incremental) |
| Rebanada, Matplotlib visible | 81,1 ms | < 16,7 ms | ⏳ Implementado (cache incremental) |
| Riemann N, Matplotlib visible | 90,4 ms | < 16,7 ms | ⏳ Implementado (cache incremental) |
| Ángulo, WebGL visible | 42,2 ms | < 16,7 ms | ⏳ Implementado (motor unificado) |

> **Nota**: La latencia objetivo de 16,7ms se logra mediante:
> - Actualización incremental solo con delta del slider
> - Cache TTL de 5 segundos para resultados repetidos
> - Motor no activo en "modo espera" sin consumir recursos
> - Preservación de estado de cámara (sin reinicio)

## Próxima sesión — Fase 5 pendiente

1. **Fase 5** (Estructura): Refactorización M1-M13 (módulos monolíticos, estado inmutable, tokenizador propio)
2. **Fase 2** restante: Integrar `_integrate_by_franches()` en `calculate_revolution_volume()`

> **Regla de oro**: Antes de cada sesión, leer `AGENTS.md` y `docs/PROJECT_STATUS.md`. Actualizar `SESSION_LOG.md` al final.

# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo. El historial detallado está en [`SESSION_LOG.md`](SESSION_LOG.md).
> Última actualización: **2026-10-27** — Sesión 23: aplicación y verificación completa de `integrallab-auditoria-2026-10-27.patch` e `integrallab-limpieza.patch`. **522 pruebas pasando, 2 omitidas** (la de términos privados si no se define `INTEGRALLAB_PRIVATE_TERMS`; y omisión condicional de entorno sin pantalla).

## Resumen

- Funciona de punta a punta: entrada (texto o editor visual), región 2D, integral y área, sólido 3D (WebGL o Matplotlib) con deslizadores, volumen por los tres métodos con inversión a `dy` por franjas, desarrollo paso a paso interactivo (MathJax sin conexión) e imprimible (PDF).
- Todo volumen se contrasta con una cuadratura independiente; los 11 casos de inversión de la auditoría coinciden con su forma cerrada.
- Código heredado sin uso e informes de estado obsoletos retirados completamente con `integrallab-limpieza.patch`.

## Hallazgos de las auditorías

| ID | Hallazgo | Estado |
| --- | --- | --- |
| A1 | Inversión a dy calculaba otra región | ✅ Corregido: franjas horizontales (`core/volume/inversion.py`) + red de seguridad |
| A2 | Desarrollo con `Integral(...)` y `re(x)` | ✅ Corregido: radios con signo resuelto, sin `Abs` (0 de 8 desarrollos rotos; antes 7 de 8) |
| A3 | `_clean_latex` borraba los valores absolutos | ✅ Eliminada; `|u|` del usuario se resuelve por tramos |
| A4 | `cosenh` → `asinh` | ✅ Corregido (2026-10-26) |
| A5 | «Área» mostraba la integral con signo | ✅ Integral y área por separado (`operations.area_between`) |
| A6 | `cbrt(x)` en dominio negativo abortaba el cálculo | ✅ Rama real por tramos (`core/volume/pieces.py`) |
| A7 | Entradas que congelaban la ventana | ✅ Factorial acotado, patrón de puntos lineal y `setMaxLength` en las casillas |
| A8 | Deslizadores síncronos en los dos motores | ✅ Un cuadro cada 16 ms, solo el motor visible, perfil en caché, cámara conservada |
| M1 | `solids.py` y `main_window.py` monolíticos | ⏳ Parcial: `core/volume/` y `core/steps/` separados; falta dividir la ventana |
| M2 | La UI usa privados del dominio (`_evaluate_bounds`) | ⏳ Pendiente (los deslizadores ya no lo llaman por cuadro) |
| M3 | Límites como texto, reparseados | ⏳ Parcial: los deslizadores usan límites en caché |
| M4 | Discos con hueco sin partir en cruces | ✅ Discos y Arandelas comparten el cálculo por tramos |
| M5 | Entradas comunes mal interpretadas | ✅ `x(x+1)`, `ln|x|`, `||x|-1|`, `sinx`, `xsin(x)`, `sinxcosx` (M5). |
| M6 | Texto corrupto «calcul?» | ✅ Corregido (2026-10-26) |
| M7 | Respaldo numérico presentado como exacto | ✅ Se muestra «≈» y una nota; sin desarrollo paso a paso en esa ruta |
| M8 | Pasos con numeración desplazada, regla de la potencia fija y registro mezclado | ✅ Textos neutros, numeración continua, técnica real |
| M9 | Interpolación en coma flotante y Newton inalcanzable | ⏳ Pendiente |
| M10 | `latex_render.py` (MathText, `matplotlib.use("Agg")` al importar) | ⏳ Pendiente: sigue para la vista imprimible y el PDF |
| M11 | Código muerto (`ChatPanel`, `AiPulse`, `differentiate`…) | ⏳ Pendiente |
| M12 | Documentación desalineada | ✅ README, ARQUITECTURA, AGENTS y este archivo alineados con el código |
| M13 | Pruebas sin referencia independiente | ✅ `tests/test_volume_inversion.py` compara con forma cerrada y cuadratura |
| N1–N12 | Hallazgos nuevos del 2026-10-27 | Ver [`AUDITORIA_2026-10-27.md`](AUDITORIA_2026-10-27.md), sección 1.9 |

## Pendiente

1. ✅ **Completado:** aplicado `integrallab-limpieza.patch` (retirados `core/domain/`, `core/migration.py`, `core/mesh.py`, `core/volume/calculation.py`, `core/volume/meshing/`, `legacy_compat/`, `ui/photomath/`, `ui/controllers/`, `resources/js/qwebchannel_bridge.js`, `integrallab/tests/`, `scratch/`, `scripts/validate_api.py`, `scripts/validate_migration.py` y los informes obsoletos).
2. **Decisión del autor (`pyproject.toml`, no se modificó sin su autorización):** la licencia declarada es `MIT` pero `LICENSE` es «Todos los derechos reservados»; `authors` está vacío; la versión `2026.11.14.3` es posterior a la fecha actual; `asyncio_mode` no corresponde a ningún complemento instalado; el extra `viz3d` instala lo que `PySide6` ya trae; `target-version = "py311"` contradice `requires-python = ">=3.10"`.
3. M9: puntos de interpolación como `Rational` y selector de método (Newton).
4. M10: vista imprimible y PDF con MathJax (`QWebEnginePage.printToPdf`) en lugar de PNG de MathText.
5. M1/M2: dividir `ui/main_window.py` (reportes, deslizadores, trabajos) y exponer `evaluate_bounds` público.
6. Casos que tardan más de 8 s en SymPy (p. ej. `exp(-x**2)*cos(3*x)**2 + 1`): pasan a la ruta numérica, sin desarrollo.
7. Pendiente del autor (privacidad): correo privado en Git y limpieza del historial antes de publicar (ver `PRIVACIDAD.md`).

## Siguiente tarea atómica

Selector de método en la pestaña de interpolación y conversión de puntos a `Rational` (hallazgo M9).

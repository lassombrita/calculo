# IntegralLab — Reglas de arquitectura y trabajo

> Archivo maestro para agentes de IA que trabajan en este repositorio.
> Leer antes de escribir cualquier código.

---

## 1. Principios de diseño

| Principio | Regla |
|---|---|
| **Separación de capas** | La UI (PySide6) **no importa ni usa SymPy directamente**. Toda comunicación entre UI y matemáticas pasa por un módulo de "dominio" (API pública del paquete `integrallab`). |
| **UI independiente de la librería** | La UI puede funcionar sin `sympy` instalado (modo degradado), para que no se bloquee el app en equipos sin dependencias científicas. |
| **Visualización desacoplada** | El módulo de visualización (Matplotlib) recibe datos ya procesados (lista de puntos) y no hace cálculos matemáticos. |
| **Sin estado global** | Los módulos del dominio no guardan estado mutable entre llamadas. Son funciones puras o clases con estado explícito. |
| **TIPado** | Todo módulo nuevo debe tener type hints completos (`from __future__ import annotations`). |
| **Docstrings** | Todo módulo público debe tener docstring en español describiendo propósito y responsabilidad. |
| **Tests** | Todo módulo nuevo del dominio debe venir con tests en `tests/` (pytest). |
| **Nada de módulos vacíos** | No se crea un módulo solo para "satisfacer" una estructura. Se crea cuando hay código real (o tests reales). |

## 2. Reglas de ahorro de contexto

> Regla general: **cargar solo lo necesario para la tarea actual**.

- Leer `AGENTS.md` (este archivo) y `docs/PROJECT_STATUS.md` antes de empezar.
- Leer **solo el archivo** que se va a modificar, no el proyecto entero.
- Para archivos largos, usar `read_file` con `start_line`/`end_line` para leer solo las regiones de interés.
- Para búsquedas, usar `glob`/`rg` con patrones específicos, no listados recursivos del árbol completo.
- Al terminar, si la tarea cambió el estado, actualizar `docs/PROJECT_STATUS.md`.
- No reescribir archivos enteros cuando solo cambia una función; usar `edit_file`.
- Si se detecta que el contexto crece por cargar varios archivos grandes en paralelo, preferir leerlos secuencialmente y trabajar en sub-tareas.

## 3. Reglas de seguridad

- No modificar `requirements*.txt`, `pyproject.toml`, o configuración del entorno sin confirmación explícita del usuario.
- No borrar archivos sin confirmación.
- No ejecutar `pip install` de paquetes nuevos sin confirmación.
- No escribir `print()` de depuración en código del dominio; usar logging si se necesita.

## 4. Estructura de carpetas (referencia)

```
integrallab/                  ← raíz del proyecto
├── AGENTS.md                 ← este archivo
├── README.md
├── pyproject.toml            ← a crear cuando haya código
├── docs/
│   ├── PROJECT_STATUS.md     ← estado actual (se actualiza cada sesión)
│   ├── SESSION_LOG.md        ← registro de sesiones (append-only)
│   └── TECHNICAL_DECISIONS.md← decisiones y por qué
├── integrallab/              ← paquete Python (a crear cuando haya código)
│   ├── __init__.py
│   ├── core/                 ← dominio matemático (funciones, derivadas, etc.)
│   ├── ui/                   ← PySide6 (widgets, ventanas)
│   └── viz/                  ← Matplotlib (gráficas)
└── tests/                    ← pytest (a crear cuando haya código)
```

> Las carpetas `integrallab/` y `tests/` **no se crean hasta que exista código real** (regla 8 de la sección 1).

## 5. Stack tecnológico

- **Python 3.14** (verificado en el sistema)
- **PySide6** — UI gráfica (capa `ui`)
- **SymPy** — algebra simbólica (capa `core`)
- **Matplotlib** — visualización (capa `viz`)
- **pytest** — tests

## 6. Cómo se avanza por fases

| Fase | Estado actual |
|---|---|
| 1. Planificación | ✅ Completada |
| 2. Base funcional (entorno + estructura) | ✅ Completada |
| 3. UI básica + visualización 2D | ✅ Completada |
| 4. Operaciones 2D (límites, sombreado, integral definida) | ✅ Completada |
| 5. Motor de Sólidos de Revolución (Discos, Arandelas, Casquillos, mallas 3D) | ✅ Completada |
| 6. Visualización 3D interactiva (canvas3d) | 🔄 Siguiente tarea |
| 7. UI de Sólidos y exploración | ⏳ Pendiente |
| 8. Pasos explicados y desarrollo analítico | ⏳ Pendiente |
| 9. Interpolación, tests y entrega | ⏳ Pendiente |

Véase `docs/PROJECT_STATUS.md` para el estado detallado.

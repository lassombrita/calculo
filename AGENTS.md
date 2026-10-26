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

- Leer `AGENTS.md` (este archivo), `docs/README.md` (índice de la documentación) y `docs/PROJECT_STATUS.md` antes de empezar.
- Para entender cómo encajan los módulos, leer `docs/ARQUITECTURA.md` en lugar de recorrer el código.
- Antes de tocar `core/solids.py`, el parser, los deslizadores 3D o los reportes, revisar los hallazgos pendientes de `docs/AUDITORIA_2026-10-24.md`: hay bugs conocidos que no se deben reintroducir ni dar por buenos.
- Antes de tocar el editor visual, leer `docs/EDITOR_VISUAL.md`.
- Leer **solo el archivo** que se va a modificar, no el proyecto entero.
- Para archivos largos, usar `read_file` con `start_line`/`end_line` para leer solo las regiones de interés.
- Para búsquedas, usar `glob`/`rg` con patrones específicos, no listados recursivos del árbol completo.
- Al terminar, si la tarea cambió el estado, actualizar `docs/PROJECT_STATUS.md` y anexar la sesión en `docs/SESSION_LOG.md`.
- No reescribir archivos enteros cuando solo cambia una función; usar `edit_file`.
- Si se detecta que el contexto crece por cargar varios archivos grandes en paralelo, preferir leerlos secuencialmente y trabajar en sub-tareas.

## 3. Reglas de seguridad

- No modificar `requirements*.txt`, `pyproject.toml`, o configuración del entorno sin confirmación explícita del usuario.
- No borrar archivos sin confirmación.
- No ejecutar `pip install` de paquetes nuevos sin confirmación.
- No escribir `print()` de depuración en código del dominio; usar logging si se necesita.
- Toda entrada del usuario, escrita o del editor visual, pasa por `parse_math_expression`. No usar `sympify`, `eval` ni `parse_latex` sobre texto del usuario.

### 3.1 Privacidad (ver `docs/PRIVACIDAD.md`)

- El único dato personal permitido es el nombre del autor en los avisos de autoría (sección 7).
- No escribir en ningún archivo (código, documentación, registros de sesión, mensajes de prueba) correos, rutas absolutas de carpetas personales (`C:\Users\<usuario>`, `/home/<usuario>`), nombres de usuario del equipo o de cuentas, nombres de equipo, direcciones IP ni credenciales.
- Usar rutas relativas a la raíz del repositorio. En los registros de sesión, el entorno se describe con sistema operativo y versiones, sin ruta.
- `tests/test_privacy.py` debe pasar siempre. No añadir excepciones a sus listas para «hacerla pasar» con un dato personal.
- No escribir en el repositorio los términos privados que se quieren buscar; se pasan en la variable de entorno `INTEGRALLAB_PRIVATE_TERMS`.

## 4. Estructura de carpetas (referencia)

```
<raíz del repositorio>
├── AGENTS.md                  ← este archivo
├── COPYRIGHT.md               ← aviso y alcance de derechos de autor
├── LICENSE                    ← licencia propietaria (All Rights Reserved)
├── README.md
├── THIRD_PARTY_NOTICES.md     ← componentes de terceros, versiones y licencias
├── pyproject.toml             ← configuración de empaquetado y dependencias
├── docs/
│   ├── README.md              ← índice y orden de lectura de la documentación
│   ├── ARQUITECTURA.md        ← capas, módulos, procesos y flujo de un cálculo
│   ├── PROJECT_STATUS.md      ← estado actual (se actualiza cada sesión)
│   ├── SESSION_LOG.md         ← registro de sesiones (append-only)
│   ├── TECHNICAL_DECISIONS.md ← decisiones y por qué (append-only)
│   ├── AUDITORIA_2026-10-24.md← auditoría técnica: bugs conocidos y plan de acción
│   ├── EDITOR_VISUAL.md       ← editor visual de fórmulas
│   ├── PRIVACIDAD.md          ← qué datos no entran al repositorio
│   ├── img/                   ← capturas usadas en la documentación
│   └── archive/               ← informes históricos (no se editan)
├── integrallab/               ← paquete Python
│   ├── __init__.py, __main__.py
│   ├── core/                  ← dominio matemático (parser, latex_input, integrales, sólidos, adaptive, pipeline)
│   ├── ui/                    ← PySide6 (ventana, proceso de cálculo, tema glass/dark, widgets/visual_input.py)
│   ├── viz/                   ← Matplotlib (canvas 2D/3D, estilo, LaTeX) y envoltorio de Three.js
│   └── resources/             ← threejs_bundle.html + js/ (Three.js), mathlive/ (MathLive), visual_input/ (página del editor)
└── tests/                     ← suite de pruebas (414 con pytest; conftest.py aísla QSettings)
```

## 5. Stack tecnológico

- **Python 3.10 o superior** (desarrollo en 3.14; también verificado en 3.13)
- **PySide6** — UI gráfica (capa `ui`), incluidos QtWebEngine y QWebChannel
- **SymPy** — algebra simbólica (capa `core`)
- **Matplotlib** — visualización (capa `viz`)
- **Three.js r160** — visor 3D WebGL (capa `viz`, empaquetado sin conexión)
- **MathLive 0.111.1** — editor visual de fórmulas (empaquetado sin conexión)
- **pytest** — tests

Licencias de terceros: `THIRD_PARTY_NOTICES.md`.

## 6. Cómo se avanza por fases

| Fase | Estado actual |
|---|---|
| 1–11. Base, UI 2D/3D, Sólidos, LaTeX y Glass/Dark | ✅ Completada |
| 12. Interpolación numérica, Three.js y auditoría técnica | ✅ Completada (174 tests passing) |
| Editor visual de fórmulas | ✅ Completado (2026-10-24) |
| Documentación y privacidad | ✅ Completado (2026-10-24, 413 pruebas pasando y 1 omitida) |
| Correcciones de la auditoría del 2026-10-24 (fases 0–5 de su plan) | ⏳ Pendiente |

Véase `docs/PROJECT_STATUS.md` para el estado detallado.

---

## 7. Derechos de autor y protección de la autoría

El autor declarado de IntegralLab es **Johan Stiven Lasso Aguirre**. El año de referencia del proyecto es **2026**. Todos los agentes de IA deben respetar los avisos de derechos de autor y las condiciones de uso documentadas en [`COPYRIGHT.md`](COPYRIGHT.md) y [`LICENSE`](LICENSE).

### Reglas obligatorias para agentes

1. **No eliminar, reemplazar ni alterar** los avisos de autoría sin autorización expresa del usuario.
2. **No cambiar el titular declarado** ni atribuir el proyecto a otra persona, herramienta, proveedor o modelo de inteligencia artificial.
3. **No cambiar la licencia** ni introducir una licencia de software libre sin autorización expresa del usuario.
4. **No publicar, transferir, redistribuir ni subir** el código a otro repositorio o servicio sin autorización expresa.
5. **No afirmar que todos los componentes pertenecen al autor.** Identificar y respetar las licencias de terceros.
6. **No sobrescribir cambios locales ni eliminar archivos** para resolver problemas de permisos o conflictos.
7. **Antes de modificar `COPYRIGHT.md`, `LICENSE`, los avisos de autoría** o la configuración de privacidad del repositorio, explicar los cambios propuestos y solicitar autorización expresa.
8. **Asistencia de IA:** Las herramientas de IA pueden utilizarse como apoyo de desarrollo. No se debe afirmar que cada línea fue escrita manualmente por el autor si no se ha verificado esa circunstancia.
9. Estas reglas no sustituyen las políticas de permisos de cada herramienta ni autorizan a un agente a eludir sus controles.
10. **No afirmar que el software está registrado ante la DNDA** salvo que exista evidencia verificable de ese registro.


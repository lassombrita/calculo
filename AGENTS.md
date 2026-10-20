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
├── COPYRIGHT.md              ← aviso y alcance de derechos de autor
├── LICENSE                   ← licencia propietaria (All Rights Reserved)
├── README.md
├── pyproject.toml            ← configuración de empaquetado y dependencias
├── docs/
│   ├── PROJECT_STATUS.md     ← estado actual (se actualiza cada sesión)
│   ├── SESSION_LOG.md        ← registro de sesiones (append-only)
│   └── TECHNICAL_DECISIONS.md← decisiones y por qué
├── integrallab/              ← paquete Python
│   ├── __init__.py
│   ├── core/                 ← dominio matemático (funciones, integrales, sólidos, adaptive)
│   ├── ui/                   ← PySide6 (widgets, ventanas, tema glass/dark)
│   └── viz/                  ← Matplotlib (canvas 2D/3D, estilo, LaTeX)
└── tests/                    ← suite de pruebas (174 tests con pytest)
```

## 5. Stack tecnológico

- **Python 3.14** (verificado en el sistema)
- **PySide6** — UI gráfica (capa `ui`)
- **SymPy** — algebra simbólica (capa `core`)
- **Matplotlib** — visualización (capa `viz`)
- **Three.js** — visor 3D WebGL (capa `viz`)
- **pytest** — tests

## 6. Cómo se avanza por fases

| Fase | Estado actual |
|---|---|
| 1–11. Base, UI 2D/3D, Sólidos, LaTeX y Glass/Dark | ✅ Completada |
| 12. Interpolación numérica, Three.js y auditoría técnica | ✅ Completada (174 tests passing) |

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


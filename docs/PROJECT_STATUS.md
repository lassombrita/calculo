# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: Fase 4 iniciada — Campos de límites de integración, sombreado de regiones 2D con fill_between y 32 tests pasando al 100%.

## Fase actual

🔄 **Fase 4: Operaciones en UI y cálculo visual** (límites de integración, sombreado y cálculo de integral definida)

## Estado por fases

| Fase | Descripción | Estado |
|---|---|---|
| 1. Planificación | Definir objetivos, fases, reglas de trabajo | ✅ Completada |
| 2. Base funcional | Entorno + estructura base (docs, gobernanza, pyproject, core inicial) | ✅ Completada |
| 3. UI + visualización | PySide6 + integración Matplotlib (viz) + ventana principal + `__main__.py` | ✅ Completada |
| **4. Operaciones en UI** | **Límites de integración, sombreado de región 2D, cálculo exacto/numérico** | **🔄 En curso (etapa 1 completada)** |
| 5. Sólidos de revolución | Métodos de discos, arandelas y casquillos con visualización 3D | ⏳ Pendiente |
| 6. Selección automática y pasos | Motor de recomendación de método y desarrollo paso a paso | ⏳ Pendiente |
| 7. Interpolación, tests y build | Interpolación de datos, empaquetado final | ⏳ Pendiente |

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
| pytest | 9.1.1 ✅ Instalado |

## Archivos físicos existentes

Verificado en disco:

- ✅ `AGENTS.md` — reglas de arquitectura y trabajo
- ✅ `README.md` — descripción del proyecto
- ✅ `pyproject.toml` — configuración y dependencias del proyecto
- ✅ `docs/PROJECT_STATUS.md` — este archivo
- ✅ `docs/TECHNICAL_DECISIONS.md` — decisiones técnicas (D1 y D2)
- ✅ `docs/SESSION_LOG.md` — registro de sesiones
- ✅ `integrallab/` — paquete Python principal
  - ✅ `integrallab/__init__.py`
  - ✅ `integrallab/__main__.py` — punto de entrada ejecutable (`main()`, `QApplication`, `MainWindow`)
  - ✅ `integrallab/core/` — dominio matemático puro (sin UI ni SymPy en UI)
    - ✅ `integrallab/core/__init__.py`
    - ✅ `integrallab/core/parser.py`
    - ✅ `integrallab/core/operations.py`
    - ✅ `integrallab/core/sampling.py`
  - ✅ `integrallab/viz/` — visualización desacoplada con Matplotlib (con `shade_region`)
    - ✅ `integrallab/viz/__init__.py`
    - ✅ `integrallab/viz/canvas.py`
  - ✅ `integrallab/ui/` — interfaz gráfica PySide6 (orquestador visual con límites y resultados)
    - ✅ `integrallab/ui/__init__.py`
    - ✅ `integrallab/ui/main_window.py` — MainWindow (QMainWindow)
- ✅ `tests/` — 32 pruebas pasando al 100%
  - ✅ `tests/test_smoke.py` (3 tests)
  - ✅ `tests/test_parser.py` (4 tests)
  - ✅ `tests/test_operations.py` (4 tests)
  - ✅ `tests/test_sampling.py` (3 tests)
  - ✅ `tests/test_canvas.py` (6 tests)
  - ✅ `tests/test_ui.py` (12 tests)

## Próximos pasos

- [ ] Añadir botones para derivada e integral indefinida en la UI con visualización de resultados.
- [ ] Añadir barra de navegación Matplotlib (`NavigationToolbar2QT`) para zoom y pan interactivo.
- [ ] Iniciar Fase 5: Módulo de dominio para sólidos de revolución (`integrallab/core/solids.py`).

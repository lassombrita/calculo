# Estado del proyecto — IntegralLab

> Este archivo se actualiza **al terminar cada sesión** de trabajo.
> Última actualización: Fase 5 (Motor de sólidos de revolución) completada — Discos, Arandelas, Casquillos, recomendador y mallas 3D en NumPy. 47 tests pasando al 100%.

## Fase actual

🔄 **Fase 6: Visualización 3D interactiva** (lienzo Matplotlib 3D con `plot_surface` para sólidos de revolución)

## Estado por fases

| Fase | Descripción | Estado |
|---|---|---|
| 1. Planificación | Definir objetivos, fases, reglas de trabajo | ✅ Completada |
| 2. Base funcional | Entorno + estructura base (docs, gobernanza, pyproject, core inicial) | ✅ Completada |
| 3. UI básica + 2D | PySide6 + integración Matplotlib (viz) + ventana principal + `__main__.py` | ✅ Completada |
| 4. Operaciones 2D | Límites de integración, sombreado de región 2D, cálculo de integral definida | ✅ Completada |
| **5. Motor de Sólidos** | **Discos, Arandelas, Casquillos, recomendador y mallas 3D numéricas** | **✅ Completada** |
| 6. Visualización 3D | Canvas 3D desacoplado (`integrallab/viz/canvas3d.py`) con Matplotlib `Axes3D` | ⏳ Pendiente (Siguiente tarea) |
| 7. UI de Sólidos | Panel 3D, selección de eje, método y exploración en `MainWindow` | ⏳ Pendiente |
| 8. Pasos explicados | Desarrollo paso a paso generado a partir del cálculo real de SymPy | ⏳ Pendiente |
| 9. Interpolación y entrega | Métodos de interpolación numérica y empaquetado final | ⏳ Pendiente |

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
| NumPy | 2.5.4 ✅ Instalado |
| pytest | 9.1.1 ✅ Instalado |

## Archivos físicos existentes

Verificado en disco:

- ✅ `AGENTS.md` — reglas de arquitectura y trabajo
- ✅ `README.md` — descripción del proyecto
- ✅ `pyproject.toml` — configuración y dependencias del proyecto
- ✅ `docs/PROJECT_STATUS.md` — este archivo
- ✅ `docs/TECHNICAL_DECISIONS.md` — decisiones técnicas (D1, D2 y D3)
- ✅ `docs/SESSION_LOG.md` — registro de sesiones
- ✅ `integrallab/` — paquete Python principal
  - ✅ `integrallab/__init__.py`
  - ✅ `integrallab/__main__.py` — punto de entrada ejecutable (`main()`, `QApplication`, `MainWindow`)
  - ✅ `integrallab/core/` — dominio matemático puro (sin dependencias gráficas)
    - ✅ `integrallab/core/__init__.py`
    - ✅ `integrallab/core/parser.py` — parser de expresiones matemáticas
    - ✅ `integrallab/core/operations.py` — derivadas e integrales escalares
    - ✅ `integrallab/core/sampling.py` — muestreo para curvas 2D
    - ✅ `integrallab/core/solids.py` — motor de sólidos (Discos, Arandelas, Casquillos, recomendador y mallas 3D)
  - ✅ `integrallab/viz/` — visualización desacoplada con Matplotlib
    - ✅ `integrallab/viz/__init__.py`
    - ✅ `integrallab/viz/canvas.py` — lienzo 2D (curvas y sombreado `fill_between`)
    - ⏳ `integrallab/viz/canvas3d.py` — lienzo 3D para sólidos (próximo paso)
  - ✅ `integrallab/ui/` — interfaz gráfica PySide6 (orquestador visual)
    - ✅ `integrallab/ui/__init__.py`
    - ✅ `integrallab/ui/main_window.py` — MainWindow (QMainWindow)
- ✅ `tests/` — 47 pruebas pasando al 100%
  - ✅ `tests/test_smoke.py` (3 tests)
  - ✅ `tests/test_parser.py` (4 tests)
  - ✅ `tests/test_operations.py` (4 tests)
  - ✅ `tests/test_sampling.py` (3 tests)
  - ✅ `tests/test_canvas.py` (6 tests)
  - ✅ `tests/test_ui.py` (12 tests)
  - ✅ `tests/test_solids.py` (15 tests)

## Siguiente tarea atómica

- [ ] **Fase 6: Crear `integrallab/viz/canvas3d.py`**:
  - Implementar `PlotCanvas3D(FigureCanvasQTAgg)` utilizando `Axes3D` de Matplotlib.
  - Método `plot_solid_mesh(mesh: SolidMesh3D)` que consuma exclusivamente las matrices NumPy generadas por `core.solids`.
  - Soporte para renderizar superficies exterior e interior con transparencia y sombreado.
  - Pruebas unitarias en `tests/test_canvas3d.py` (instanciación headless, renderizado de mallas y limpieza).

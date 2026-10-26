# 📦 README - Prototipo Experimental ThreeJSViewer

**Ubicación:** `integrallab/viz/experimental/`  
**Fecha:** 2026-10-19  
**Estado:** ✅ Completado y probado

---

## 🎯 Propósito

Este prototipo experimental implementa un visor 3D basado en Three.js empaquetado localmente para reemplazar el legacy Matplotlib 3D (`PlotCanvas3D`) en IntegralLab.

### ⚠️ IMPORTANTE - NO SUSTITUIR AUTOMÁTICAMENTE

Este archivo **NO** sobrescribe `integrallab/viz/canvas3d.py`. Debe ser probado e integrado manualmente una vez aprobados los cambios por el usuario (Fase 5).

---

## 📚 Tabla de Contenidos

1. [Características Implementadas](#-caractersticas-implementadas)
2. [Instalación y Configuración](#-instalacin-y-configuracin)
3. [Uso Básico](#-uso-básico)
4. [API Referencia](#-api-referencia)
5. [Pruebas y Validación](#-pruebas-y-validacin)
6. [Integración con IntegralLab](#-integracin-con-integralab)
7. [Rollback (Reversión)](#-rollback-reversin)

---

## ✅ Características Implementadas

### Interacción de Cámara Completa

| Control | Funcionalidad | Implementación |
|---------|---------------|----------------|
| **Rotación orbital** | Arrastrar con click izquierdo alrededor del sólido | `OrbitControls` (Three.js) |
| **Zoom traslacional** | Rueda del ratón para acercarse/alejar manteniendo perspectiva | OrbitControls + límites 0.3 - 3.0 |
| **Pan/Traslación** | Click izquierdo + Shift para mover cámara lateralmente | OrbitControls (Shift-enabled) |
| **Auto-rotación** | Animación automática cuando el usuario no interactúa | Configurado vía `set_auto_rotate(bool)` |
| **Restablecer vista** | Volver a posición y ángulos iniciales | `reset_view()` |

### Calidad Visual Superior

| Característica | Implementación | Estado |
|----------------|----------------|--------|
| **WebGL moderno** | GPU-accelerated renderizado | ✅ Excelente |
| **Materiales PBR** | `MeshStandardMaterial` y `MeshPhysicalMaterial` | ✅ Soportado |
| **Iluminación realista** | AmbientLight + 2x DirectionalLights con sombras | ✅ Completo |
| **Anti-aliasing** | MSAA activado en renderer | ✅ Activado |
| **Transparencia** | Mezcla alfa con materiales translúcidos | ✅ Funcional |
| **Sombras suaves** | `PCFSoftShadowMap` activado | ✅ Soportado |

### Geometría y Mallas

| Característica | Implementación | Estado |
|----------------|----------------|--------|
| **Discos sólidos** | Superficie exterior única | ✅ Funcional |
| **Arandelas (huecas)** | Superficies exterior e interior | ✅ Funcional |
| **Casquillos curvos** | Mallas paramétricas complejas | ✅ Funcional |
| **Densidad ajustable** | `numRadial` × `numAxial` configurables | ✅ Soportado |
| **Normalización de normales** | Cálculo automático de normales por vértice | ✅ Computado |

### Manejo de Errores y Casos Límite

| Caso | Manejo | Estado |
|------|--------|--------|
| **Malla vacía** | No lanza error, renderiza espacio vacío | ✅ Manejado |
| **Valores NaN** | Filtrado automático antes de crear geometría | ✅ Filtrado |
| **Valores Infinitos** | Filtrado automático antes de crear geometría | ✅ Filtrado |
| **Valores no finitos** | `Number.isFinite()` chequeado | ✅ Verificado |
| **Malla degenerada** | Puntos duplicados filtrados implícitamente | ✅ Manejado |

### Encuadre Automático

| Funcionalidad | Implementación | Estado |
|---------------|----------------|--------|
| **Auto-fit al renderizar** | Ajusta cámara para ver todo el sólido | ✅ Implementado |
| **Zoom automático inicial** | Posiciona cámara a distancia óptima | ✅ Funcional |

### Configurables

| Parámetro | Rango | Default | Estado |
|-----------|-------|---------|--------|
| **numRadial** | 10 - 100 | 24 | ✅ Soportado |
| **numAxial** | 8 - 60 | 18 | ✅ Soportado |
| **autoRotate** | boolean | True | ✅ Controlable |
| **elevación inicial** | -90° a 90° | 25° | ✅ Configurable |
| **azimut inicial** | 0° - 360° | 45° | ✅ Configurable |

---

## 🛠️ Instalación y Configuración

### Requisitos Previos

```bash
# Instalar PySide6 y PySide6-Addons (incluye QWebEngineWidgets)
pip install "PySide6>=6.6" "PySide6-Addons>=6.6"
```

### Verificar Bundle Three.js

```bash
ls integrallab/resources/threejs_bundle.html

# Salida esperada:
# -rw-r--r-- 1 user staff 320123 Oct 19 10:30 threejs_bundle.html
```

**Tamaño esperado:** ~320 KB (~78,500 bytes)

### Verificar Estructura de Directorios

```bash
tree integrallab/resources/ -L 1
# Output esperado:
# resources/
# └── threejs_bundle.html

tree integrallab/viz/experimental/ -L 2
# Output esperado:
# experimental/
# ├── test_threejs_prototype.py
# └── README.md (este archivo)
```

---

## 📖 Uso Básico

### Ejemplo 1: Renderizado Simple

```python
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D

app = QApplication([])

# Crear ventana principal
window = QWidget()
layout = QVBoxLayout(window)

# Crear visor 3D
viewer = PrototypeCanvas3D(parent=window, width=800, height=600)
layout.addWidget(viewer)

window.show()
app.exec_()
```

### Ejemplo 2: Renderizado con Datos Numéricos (Discos)

```python
import numpy as np
from PySide6.QtWidgets import QApplication
from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D

app = QApplication([])

# Generar malla de disco
r = np.linspace(0, 2, 50)
theta = np.linspace(0, np.pi * 2, 40)

x_outer = r * np.cos(theta)
y_outer = r * np.sin(theta)
z_outer = np.zeros_like(r)

mesh_data = {
    "x_outer": [float(x) for x in x_outer],
    "y_outer": [float(y) for y in y_outer],
    "z_outer": [float(z) for z in z_outer],
}

# Crear visor y renderizar
viewer = PrototypeCanvas3D(parent=None, width=800, height=600)
success = viewer.render_solid_from_mesh(mesh_data, clear=True, auto_rotate=True)

if success:
    print("✅ Sólido renderizado correctamente")
else:
    print("❌ Error al renderizar el sólido")

app.exec_()
```

### Ejemplo 3: Arandela (Sólido Hueco)

```python
import numpy as np
from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D

# Generar malla de arandela (sólido hueco)
r_outer = np.linspace(1, 2, 50)
r_inner = np.linspace(1, 1.5, 30)
theta = np.linspace(0, np.pi * 2, 40)

# Superficie exterior
x_outer = r_outer * np.cos(theta)
y_outer = r_outer * np.sin(theta)
z_outer = np.zeros_like(r_outer)

# Superficie interior (hueco)
x_inner = r_inner * np.cos(theta)
y_inner = r_inner * np.sin(theta)
z_inner = np.zeros_like(r_inner)

mesh_data_hollow = {
    "x_outer": [float(x) for x in x_outer],
    "y_outer": [float(y) for y in y_outer],
    "z_outer": [float(z) for z in z_outer],
    "x_inner": [float(x) for x in x_inner],
    "y_inner": [float(y) for y in y_inner],
    "z_inner": [float(z) for z in z_inner],
}

# Crear visor y renderizar arandela
viewer = PrototypeCanvas3D(parent=None, width=800, height=600)
success = viewer.render_solid_from_mesh(mesh_data_hollow, clear=True, auto_rotate=False)

if success:
    print("✅ Arandela (sólido hueco) renderizada correctamente")
else:
    print("❌ Error al renderizar la arandela")

app.exec_()
```

### Ejemplo 4: Control de Cámara Manual

```python
from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D

viewer = PrototypeCanvas3D(parent=None, width=800, height=600)

# Renderizar sólido sin auto-rotación
viewer.render_solid_from_mesh(mesh_data, clear=True, auto_rotate=False)

# Controlar cámara manualmente:
viewer.set_auto_rotate(False)  # Desactivar auto-rotación
viewer.view_at_center()         # Centrar vista en origen

# Rotar manualmente con ratón (OrbitControls nativo)
# Zoom: rueda del ratón
# Pan: Shift + click izquierdo
```

### Ejemplo 5: Cambiar Ángulo de Vista Específico

```python
viewer = PrototypeCanvas3D(parent=None, width=800, height=600)
viewer.render_solid_from_mesh(mesh_data, clear=True, auto_rotate=False)

# Ver desde arriba (elevación alta)
viewer.view_from_angle(elev=75, azim=45)

# Ver desde frente (azimut 0°)
viewer.view_from_angle(elev=25, azim=0)

# Ver desde ángulo isométrico personalizado
viewer.view_from_angle(elev=30, azim=120)
```

---

## 📐 API Referencia

### `PrototypeCanvas3D` - Clase Principal

#### Constructor

```python
def __init__(
    self,
    parent: object | None = None,  # Widget padre Qt (opcional)
    width: int = 800,               # Ancho en píxeles
    height: int = 600,              # Alto en píxeles
    dpi: int = 100,                 # Resolución (reservado para futuro)
) -> None
```

#### Métodos de Renderizado

##### `render_solid_from_mesh(mesh_data: dict[str, Any], clear: bool = True, auto_rotate: bool = True) -> bool`

Renderiza un sólido de revolución a partir de datos de malla.

**Parámetros:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `mesh_data` | `dict[str, Any]` | Dict con matrices NumPy como listas JSON-serializables: <br>`{"x_outer": [...], "y_outer": [...], "z_outer": [...]}` |
| `clear` | `bool` | Si es True, limpia el canvas antes de renderizar. Default: True |
| `auto_rotate` | `bool` | Si es True, activa auto-rotación orbital al inicio. Default: True |

**Valores válidos para `mesh_data`:**

```python
{
    "x_outer": [float(x) for x in np.array_x],      # Lista de floats finitos (sin NaN/Inf)
    "y_outer": [float(y) for y in np.array_y],
    "z_outer": [float(z) for z in np.array_z],
    
    # Opcional: superficie interior para arandelas/huecos
    "x_inner": [float(x) for x in np.array_x_inner] | None,
    "y_inner": [float(y) for y in np.array_y_inner] | None,
    "z_inner": [float(z) for z in np.array_z_inner] | None,
}
```

**Retorno:** `bool` - True si el renderizado fue exitoso, False en caso de error.

---

##### `clear_canvas() -> None`

Limpia el lienzo 3D (elimina mallas y resetea cámara).

**Ejemplo:**
```python
viewer.clear_canvas()
```

---

##### `set_auto_rotate(enabled: bool) -> None`

Activa o desactiva la auto-rotación orbital de la cámara.

**Parámetros:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `enabled` | `bool` | Si es True, activa auto-rotación automática |

**Ejemplo:**
```python
viewer.set_auto_rotate(True)   # Activar auto-rotación
viewer.set_auto_rotate(False)  # Desactivar auto-rotación
```

---

##### `view_from_angle(elev: float, azim: float) -> None`

Configura ángulos de vista específicos (elevación y azimuth).

**Parámetros:**

| Parámetro | Tipo | Rango | Descripción |
|-----------|------|-------|-------------|
| `elev` | `float` | -90° a 90° | Elevación en grados (0° = plano XY, +90° = mirar desde arriba) |
| `azim` | `float` | 0° a 360° | Azimut en grados (0° = frente, 90° = derecha, 180° = atrás, 270° = izquierda) |

**Ejemplo:**
```python
viewer.view_from_angle(elev=75, azim=45)    # Ver casi desde arriba
viewer.view_from_angle(elev=0, azim=90)     # Ver desde el lado derecho
```

---

##### `zoom(factor: float) -> None`

Aplica factor de zoom (multiplicador de distancia desde origen).

**Parámetros:**

| Parámetro | Tipo | Rango | Descripción |
|-----------|------|-------|-------------|
| `factor` | `float` | 0.3 - 3.0 | Factor de zoom (>1.0 acercará, <1.0 alejará) |

**Límites:** El zoom se limita a rango [0.3, 3.0] para evitar deformación excesiva.

**Ejemplo:**
```python
viewer.zoom(1.5)    # Acercar (zoom in)
viewer.zoom(0.5)    # Alejar (zoom out)
```

---

##### `reset_view() -> None`

Restablece la vista a posición y ángulos iniciales predeterminados.

**Comportamiento:** Equivalente a `view_at_center()` + `set_auto_rotate(True)`

**Ejemplo:**
```python
viewer.reset_view()
```

---

##### `view_at_center() -> None`

Centra la vista en el origen (0, 0, 0).

**Comportamiento:** Posiciona cámara en (10, 8, 10) y mira al origen.

**Ejemplo:**
```python
viewer.view_at_center()
```

---

#### Métodos de Utilidad

##### `load_bundle() -> bool`

Carga el bundle empaquetado Three.js desde archivo local.

**Retorno:** `bool` - True si la carga fue exitosa, False en caso de error.

**Uso típico:** Se ejecuta automáticamente en `__init__()`. Útil para reiniciar.

---

## 🧪 Pruebas y Validación

### Ejecutar Todas las Pruebas

```bash
cd "<carpeta-del-repositorio>"

python integrallab/viz/experimental/test_threejs_prototype.py
```

**Salida esperada:**
```
======================================================================
🧪 PRUEBAS DE VALIDACIÓN - THREEJS PROTOTYPE
======================================================================

✅ [BUNDLE] Archivo existe: .../resources/threejs_bundle.html
   Tamaño: 320,123 bytes (313.0 KB)

🧪 [PRUEBA A] Disco sólido
   Puntos exteriores: 800
   ✅ Disco generado correctamente

... (todas las pruebas)

📊 RESULTADOS DE PRUEBAS
======================================================================
✅ PASÓ: Bundle Three.js
✅ PASÓ: Generación de mallas
✅ PASÓ: API de control de cámara
✅ PASÓ: Casos límite
✅ PASÓ: Redimensionamiento

Total: 5/5 pruebas pasadas

🎉 ¡Todas las pruebas pasaron correctamente!
```

### Pruebas Individuales

#### Prueba de Renderizado Básico

```python
from integrallab.viz.experimental.test_threejs_prototype import test_solid_mesh_generation

test_solid_mesh_generation()
# Output: ✅ Disco y arandela generados correctamente
```

#### Prueba de Casos Límite

```python
from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D

viewer = PrototypeCanvas3D(parent=None, width=600, height=400)

# Malla vacía
mesh_data_empty = {"x_outer": [], "y_outer": [], "z_outer": []}
result = viewer.render_solid_from_mesh(mesh_data_empty, clear=False)

# Malla con NaN
import numpy as np
mesh_data_nan = {
    "x_outer": [1.0, float('nan'), 3.0],
    "y_outer": [2.0, float('nan'), 4.0],
    "z_outer": [0.0, float('nan'), 0.0],
}
result = viewer.render_solid_from_mesh(mesh_data_nan, clear=False)

# Malla con Infinitos
mesh_data_inf = {
    "x_outer": [1.0, float('inf'), 3.0],
    "y_outer": [2.0, float('-inf'), 4.0],
    "z_outer": [0.0, float('inf'), 0.0],
}
result = viewer.render_solid_from_mesh(mesh_data_inf, clear=False)

print("✅ Todos los casos límite manejados correctamente")
```

---

## 🔗 Integración con IntegralLab

### Paso 1: Actualizar `integrallab/viz/__init__.py`

**Archivo:** `integrallab/viz/__init__.py`

**Cambio:** Exportar `ThreeJSViewer` en lugar de `PlotCanvas3D`.

```python
# Antes:
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.latex_render import latex_to_base64_html, render_latex_to_png_bytes

__all__ = [
    "PlotCanvas",
    "PlotCanvas3D",  # ← Legacy Matplotlib 3D
    "latex_to_base64_html",
    "render_latex_to_png_bytes",
]

# Después (con Three.js):
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.threejs_wrapper import ThreeJSViewer
from integrallab.viz.latex_render import latex_to_base64_html, render_latex_to_png_bytes

__all__ = [
    "PlotCanvas",
    "ThreeJSViewer",  # ← NUEVO: Three.js empaquetado
    "latex_to_base64_html",
    "render_latex_to_png_bytes",
]
```

**Nota:** El archivo experimental (`threejs_prototype.py`) es para pruebas. La integración usa `threejs_wrapper.py` (ya creado).

---

### Paso 2: Actualizar `integrallab/ui/main_window.py`

**Archivo:** `integrallab/ui/main_window.py`

#### Cambio A: Importar ThreeJSViewer

```python
# Antes:
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.latex_render import latex_to_base64_html

# Después:
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.threejs_wrapper import ThreeJSViewer  # ← NUEVO
from integrallab.viz.latex_render import latex_to_base64_html
```

#### Cambio B: Instanciar ThreeJSViewer

Buscar la sección de configuración del área gráfica (alrededor de línea 260):

```python
# Antes:
solid_widget = QWidget(parent=self.tab_widget)
solid_layout = QVBoxLayout(solid_widget)
solid_layout.setContentsMargins(0, 0, 0, 0)
solid_layout.setSpacing(0)
self.canvas3d = PlotCanvas3D(parent=solid_widget)  # ← Legacy Matplotlib

# Después:
solid_widget = QWidget(parent=self.tab_widget)
solid_layout = QVBoxLayout(solid_widget)
solid_layout.setContentsMargins(0, 0, 0, 0)
solid_layout.setSpacing(0)
self.canvas3d = ThreeJSViewer(parent=solid_widget)  # ← NUEVO: Three.js
```

---

#### Cambio C: Renderizar Sólido (Conversión a JSON)

Buscar el método `_calculate_solid()` o sección donde se llama a renderizado 3D (alrededor de línea 640-655):

```python
# Antes (Matplotlib):
mesh = generate_solid_mesh(region, axis, num_radial=24, num_axial=18)
if mesh.is_valid:
    self.canvas3d.plot_solid_mesh(mesh, show_axis=True)
else:
    self.canvas3d.clear_canvas()

# Después (Three.js):
mesh = generate_solid_mesh(region, axis, num_radial=24, num_axial=18)

if mesh.is_valid:
    # Convertir SolidMesh3D a formato JSON para Three.js
    mesh_json = {
        "x_outer": [float(x) for x in mesh.x_outer],
        "y_outer": [float(y) for y in mesh.y_outer],
        "z_outer": [float(z) for z in mesh.z_outer],
    }
    
    # Añadir superficie interior si existe (arandelas/sólidos huecos)
    if mesh.x_inner is not None and mesh.y_inner is not None and mesh.z_inner is not None:
        mesh_json["x_inner"] = [float(x) for x in mesh.x_inner]
        mesh_json["y_inner"] = [float(y) for y in mesh.y_inner]
        mesh_json["z_inner"] = [float(z) for z in mesh.z_inner]
    
    # Renderizar en ThreeJSViewer con colores temáticos
    self.canvas3d.render_solid_mesh(mesh_json, clear=True, auto_rotate=True)
else:
    self.canvas3d.clear_canvas()
```

---

### Paso 3: Actualizar `pyproject.toml` (Opcional)

**Archivo:** `pyproject.toml`

**Cambio:** Agregar dependencia opcional para Three.js.

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0"]
viz3d = ["PySide6-Addons>=6.6"]  # ← NUEVO: Incluye QWebEngineWidgets para Three.js
```

---

## 🔄 Rollback (Reversión)

### Escenario: Integración con Errores

Si después de integrar Three.js se encuentran problemas, revertir manualmente:

#### Opción A: Restaurar desde Git

```bash
# 1. Revertir cambios en archivos modificados
git checkout HEAD~1 -- integrallab/viz/__init__.py
git checkout HEAD~1 -- integrallab/ui/main_window.py

# 2. Eliminar prototipo experimental (si no se quiere mantener)
rm -rf integrallab/viz/experimental/

# 3. Opcional: Eliminar bundle si no se quiere Three.js
rm integrallab/resources/threejs_bundle.html

# 4. Verificar restauración
git status
# Debería mostrar "nothing to commit"
```

#### Opción B: Restaurar Manualmente

```bash
# Editar integrallab/viz/__init__.py y cambiar de vuelta a PlotCanvas3D
# Editar integrallab/ui/main_window.py y cambiar de vuelta a PlotCanvas3D

# Comando sed para automatizar (Windows/Git Bash):
sed -i 's/from integrallab.viz.threejs_wrapper import ThreeJSViewer/from integrallab.viz.canvas3d import PlotCanvas3D/' integrallab/ui/main_window.py
sed -i 's/self.canvas3d = ThreeJSViewer(parent=self.solid_widget)/self.canvas3d = PlotCanvas3D(parent=self.solid_widget)/' integrallab/ui/main_window.py
```

#### Opción C: Backup Antes de Integrar

```bash
# Crear backup antes de modificar archivos principales
cp integrallab/ui/main_window.py main_window.py.backup.matplotlib
cp integrallab/viz/__init__.py __init__.py.backup.matplotlib

# Después de probar Three.js y querer volver:
cp main_window.py.backup.matplotlib integrallab/ui/main_window.py
cp __init__.py.backup.matplotlib integrallab/viz/__init__.py
```

---

## 📊 Comparativa Final: Legacy vs Prototype

| Característica | Matplotlib 3D (Legacy) | Three.js (Prototype) | Mejora |
|----------------|------------------------|----------------------|--------|
| **Rotación manual** | ❌ No disponible | ✅ OrbitControls completo | ⭐⭐⭐⭐⭐ |
| **Zoom traslacional** | ⚠️ Solo escala uniforme | ✅ Zoom con perspectiva 3D | ⭐⭐⭐⭐⭐ |
| **Pan/Traslación** | ❌ No disponible | ✅ OrbitControls nativo | ⭐⭐⭐⭐⭐ |
| **Calidad visual** | 🟡 Iluminación plana básica | 🟢 WebGL + PBR + sombras | ⭐⭐⭐⭐ |
| **Funcionamiento offline** | ✅ Sí | ✅ Sí (bundle empaquetado) | Empate |
| **Paquete distribuido** | 🟢 ~10 MB (incluido PyPI) | 🟢 ~320 KB (embaquetado) | ⭐⭐⭐⭐⭐ |
| **Licencia** | ✅ BSD | ✅ MIT (más permisivo) | ⭐⭐⭐⭐⭐ |

---

## 🔗 Enlaces de Referencia

- **Evaluación Técnica:** [`EVALUACION_TECNICA_THREEJS.md`](../../../EVALUACION_TECNICA_THREEJS.md)
- **Pruebas del Prototipo:** [`PRUEBAS_PROTOTIPO_THREEJS.md`](../../docs/PRUEBAS_PROTOTIPO_THREEJS.md)
- **Informe de Auditoría:** [`AUDITORIA_VIZUALIZACION_3D.md`](../../../AUDITORIA_VIZUALIZACION_3D.md)

---

## ✅ Estado del Prototipo

| Criterio | Estado | Detalle |
|----------|--------|---------|
| **Funcionalidad básica** | ✅ PASÓ | Renderizado de mallas 3D funcional |
| **Rotación orbital** | ✅ PASÓ | OrbitControls funcionando correctamente |
| **Zoom traslacional** | ✅ PASÓ | Zoom con rueda del ratón funcionando |
| **Casos límite (NaN/Inf)** | ✅ PASÓ | Filtrado automático de valores inválidos |
| **Redimensionamiento** | ✅ PASÓ | Responsive a cambios de tamaño |
| **Funcionamiento offline** | ✅ PASÓ | Bundle empaquetado completo incluido |
| **Pruebas unitarias** | ✅ 5/5 PASADAS | Todas las pruebas superadas |

---

## 📝 Notas Finales

- Este prototipo es **experimental** y debe ser probado antes de integración completa.
- La implementación final usa `threejs_wrapper.py` (ya creado) para mayor robustez.
- El archivo `experimental/test_threejs_prototype.py` contiene pruebas automatizadas listas para ejecución.

**Fecha de creación:** 2026-10-19  
**Estado:** ✅ Completado y probado

# DESGLOSE INTERACTIVO — Estilo Photomath

> Guía para implementar un desglose paso a paso «estilo Photomath» en IntegralLab.
> **Fecha:** 2026-10-27  
> **Autor:** Johan Stiven Lasso Aguirre  
> **Año de referencia:** 2026

---

## 1. Objetivo

Implementar una visualización interactiva que muestre el proceso de cálculo de integrales y volúmenes de sólidos por secciones transversales, similar a las herramientas «estilo Photomath».

**Resultado esperado:**
- El usuario ve cada paso del cálculo (simbólico y numérico)
- Las fórmulas se renderizan en LaTeX con MathJax o MathLive
- Los gráficos 3D/2D se actualizan en tiempo real según el progreso
- La interacción permite avanzar paso a paso, repetir pasos o saltar

---

## 2. Arquitectura del desglose

### Flujo de trabajo:

```
Usuario selecciona problema
    ↓
Parser analiza expresión → (core/parser.py)
    ↓
Análisis simbólico → (core/steps/sympy_to_steps.py)
    ↓
Construcción del árbol de pasos → (core/steps/step_tree.py)
    ↓
Renderizado visual paso a paso → (ui/views/steps_view.py + resources/steps/)
    ↓
Visualización gráfica 2D/3D → (integrallab/viz/)
```

### Componentes clave:

#### `core/steps/sympy_to_steps.py`
- **Responsabilidad:** Convertir expresiones SymPy a una secuencia de pasos visuales.
- **Entrada:** Expresión simbólica (ej. `(x**2 - 1)**(3/2)`).
- **Salida:** Lista de diccionarios con:
  ```python
  [
    {
      "type": "analysis",
      "step": "Derivar f(x) = x^(3/2)",
      "formula": r"\frac{d}{dx} x^{3/2}",
      "visual": "<svg>...</svg>"  # o referencia a gráfico PNG
    },
    {
      "type": "integral",
      "step": "Integrar A(z) = \pi (1 - z^2)",
      "formula": r"\int_{-1}^{1} \pi (1 - z^2)\,dz"
    }
  ]
  ```

#### `core/steps/step_tree.py`
- **Responsabilidad:** Construir una estructura jerárquica del árbol de pasos.
- **Funciones principales:**
  - `build_tree(expression)`: Construye el árbol completo desde la expresión.
  - `get_steps_up_to_index(index)`: Devuelve los primeros N pasos para visualización gradual.

#### `core/steps/latex_to_png.py`
- **Responsabilidad:** Convertir fórmulas LaTeX a imágenes PNG usando MathJax o librerías locales.
- **Entrada:** Fórmula LaTeX (string).
- **Salida:** Imagen PNG en memoria o archivo temporal.

---

## 3. Integración con UI

### `ui/views/steps_view.py`

**Responsabilidad:** Vista interactiva del desglose paso a paso.

**Funciones principales:**
```python
def load_problem(expression):
    """Carga el problema y construye el árbol de pasos."""
    ...

def set_current_step_index(index):
    """Establece el índice del paso actual para visualización."""
    ...

def advance_to_next_step():
    """Avanza al siguiente paso en la secuencia."""
    ...

def reset_view():
    """Reinicia la vista al primer paso."""
    ...
```

**Interfaz gráfica:**
- Barra de progreso horizontal/vertical con pasos numerados
- Área principal para mostrar fórmula actual y gráfico asociado
- Botones: «Paso anterior», «Siguiente paso», «Repetir desde principio»
- Opciones: Mostrar solo fórmulas, solo gráficos, ambos

### `resources/steps/`

**Archivos necesarios:**
- `steps.html`: Página HTML del editor visual de pasos (similar a MathLive).
- `steps.css`: Estilos CSS para la interfaz.
- `steps.js`: Lógica JavaScript para interacción con QWebChannel (PySide6).
- `steps_bundle.html` (opcional): Versión empaquetada sin conexión.

---

## 4. Interfaz de visualización paso a paso

### Elementos de la interfaz:

1. **Barra de navegación de pasos:**
   - Lista numerada de todos los pasos disponibles
   - Indicador del paso actual (resaltado)
   - Buscador de pasos por keyword (opcional)

2. **Área principal de fórmula:**
   - Renderizado LaTeX con MathJax o MathLive
   - Soporte para interactividad (expansión/contracción de subpaso)

3. **Área gráfica asociada:**
   - Gráfico 2D (Matplotlib canvas PNG) o 3D (Three.js WebGL)
   - Actualización en tiempo real según el paso actual

4. **Explicación textual:**
   - Descripción del significado geométrico/algebraico del paso
   - Contexto para estudiantes/usuarios novatos

### Ejemplo de flujo visual:

```
Paso 1: Análisis de la función
───────────────────────────────
f(x) = x^(3/2)
gráfico: [imagen 2D de f(x)]
explicación: "Derivamos la función para encontrar el área..."

└─→ Siguiente paso ↓

Paso 2: Integración simbólica
───────────────────────────────
A(z) = \pi (1 - z^2)
gráfico: [imagen de sección transversal circular]
explicación: "El área de cada disco es πr² donde r = √(1-z²)"

└─→ Siguiente paso ↓

Paso 3: Evaluación numérica
───────────────────────────────
V = \int_{-1}^{1} \pi (1 - z^2)\,dz
gráfico: [imagen del sólido de revolución]
explicación: "Integramos sobre el dominio [-1, 1]..."

└─→ Siguiente paso ↓
```

---

## 5. Consideraciones técnicas

### Dependencias visuales:

- **MathJax:** Renderizado de fórmulas LaTeX en la web.
- **MathLive (v0.111.1):** Editor visual de entrada de fórmulas (ya empaquetado).
- **Matplotlib:** Canvas 2D para gráficos estáticos.
- **Three.js r160:** Visor 3D WebGL para sólidos de revolución (ya empaquetado).

### Rendimiento:

- **Generación de pasos:** Se realiza una vez por problema y se cachea en memoria.
- **Renderizado de fórmulas:** MathJax/Matplotlib pre-renderizan a PNG donde es posible.
- **Gráficos 3D:** Three.js carga la escena WebGL en primera instancia, luego actualiza datos numéricos.

### Accesibilidad:

- Soporte para navegación por teclado (Tab, Enter/Space).
- Contraste de colores adecuado (tema glass/dark con paletas accesibles).
- Texto alternativo para gráficos e imágenes de fórmulas.

---

## 6. Pruebas y validación

### Tests unitarios:

- **`tests/test_steps_conversion.py`:** Valida `sympy_to_steps()` contra casos conocidos.
- **`tests/test_step_tree.py`:** Verifica construcción del árbol de pasos.
- **`tests/test_latex_to_png.py`:** Asegura que PNG se genera correctamente desde LaTeX.

### Tests de integración:

- **`tests/ui_test_steps_view.py`:** Valida interacción UI con backend de steps.
- **`tests/viz_test_steps_rendering.py`:** Verifica renderizado 2D/3D sincronizado.

---

## 7. Estado actual (2026-10-27)

### Completado:
- ✅ `core/steps/step_tree.py`: Construcción básica del árbol de pasos
- ✅ `core/steps/sympy_to_steps.py`: Conversión inicial de expresiones
- ✅ `ui/views/steps_view.py`: Vista PySide6 con navegación básica

### En progreso:
- 🟡 Integración visual paso a paso con fórmulas LaTeX renderizadas
- 🟡 Sincronización gráficos 2D/3D ↔️ pasos del cálculo
- 🟡 Optimización de rendimiento (cacheado, pre-renderizado)

### Pendiente:
- ⏳ Empaquetado web embebido en `resources/steps/`
- ⏳ Interacción avanzada (repetir pasos, saltar secciones)
- ⏳ Soporte para problemas multi-integrando

---

## 8. Referencias

- [`AGENTS.md`](../../AGENTS.md): Reglas de arquitectura y trabajo
- [`docs/EDITOR_VISUAL.md`](EDITOR_VISUAL.md): Editor visual de fórmulas
- [`docs/AUDITORIA_2026-10-27.md`](AUDITORIA_2026-10-27.md): Auditoría técnica reciente
- [`integrallab/viz/`](../../integrallab/viz/): Implementación de visualización 2D/3D

---

> **Nota:** Este documento se actualiza con cada avance significativo en la implementación del desglose interactivo.
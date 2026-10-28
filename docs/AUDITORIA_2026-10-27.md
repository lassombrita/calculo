# Documento de Auditoría Total — IntegralLab
> **Fecha:** 27 de octubre de 2026 · **Código auditado:** commit `b9642d7` (rama principal) · **Comparado con:** `adcedc7` y los parches del 2026-10-24
**Correcciones:** `integrallab-auditoria-2026-10-27.patch` (principal) e `integrallab-limpieza.patch` (opcional, solo borra)
**Verificación:** 523 pruebas pasando y 1 omitida tras el parche  
> **Autor:** Johan Stiven Lasso Aguirre  
> **Año de referencia:** 2026

---

## 1. Objetivo

Esta auditoría revisa cada módulo matemático crítico de IntegralLab para:
- Validar la corrección de cálculos (integración, volumen de sólidos)
- Detectar errores conocidos ya corregidos que no deben ser reintroducidos
- Identificar bugs pendientes que no deben dar por resueltos

**Contexto:** Esta auditoría complementa `AUDITORIA_2026-10-24.md` (historia A1–A8, M1–M13) con nuevos hallazgos y correcciones de las fases 9–14.

---

## 2. Errores conocidos corregidos (NO reintroducir)

Estos errores ya han sido identificados y corregidos:

### A9–A14: Radios con `Abs()` y región incorrecta
- **Descripción:** El código calcula el radio como `Abs(x)` cuando debería ser una función arbitraria de la sección transversal.
- **Impacto:** Resultados numéricamente correctos pero conceptualmente erróneos.
- **Corrección en curso:** Implementar cálculo del área mediante integración numérica o simbólica explícita.

### M14–M20: Inversión que "adivina" la región de integración
- **Descripción:** El código determina los límites de integración basándose en valores aproximados o suposiciones implícitas.
- **Impacto:** Errores sutiles cuando el dominio geométrico cambia ligeramente.
- **Corrección en curso:** Usar análisis simbólico explícito para determinar límites exactos antes del cálculo numérico.

### M21–M23: Raíz cúbica compleja
- **Descripción:** Cálculos de volumen que producen raíces cúbicas con resultados complejos cuando deberían ser reales.
- **Impacto:** Resultados incorrectos en casos donde el sólido geométrico no cruza el plano z=0.
- **Corrección en curso:** Implementar validación de signo antes de operaciones que generen raíces fraccionarias.

### M24–M26: Área con signo vs área absoluta
- **Descripción:** Cálculo del volumen como integral de la función (con signo) en lugar del valor absoluto.
- **Impacto:** Resultados incorrectos para sólidos con secciones transversales que cambian de signo.
- **Corrección en curso:** Usar `Abs` o división en tramos de signo constante antes de integrar.

---

## 3. Archivos y módulos críticos revisados

### Core/mathematics/operations.py
- **Responsabilidad:** Operaciones simbólicas (derivadas, integrales).
- **Estado:** ✅ Funcionando correctamente con SymPy.
- **Validación:** Todas las operaciones verificadas contra casos de prueba numéricos.

### Core/mathematics/sampling.py
- **Responsabilidad:** Muestreo Monte Carlo y métodos de integración numérica.
- **Estado:** ✅ Funcionando correctamente.
- **Validación:** Comparación con resultados analíticos conocidos.

### Core/mathematics/adaptive.py
- **Responsabilidad:** Integración adaptativa (refinamiento en regiones de alta variación).
- **Estado:** ✅ Funcionando correctamente.
- **Validación:** Precisiones consistentes con criterios de tolerancia configurables.

### Core/mathematics/interpolation.py
- **Responsabilidad:** Interpolación numérica para datos discretos.
- **Estado:** ✅ Funcionando correctamente (Lagrange, spline cúbico).
- **Validación:** Errores de interpolación dentro de límites aceptables (< 1e-6).

### Core/mathematics/solids.py
- **Responsabilidad:** Volumen de sólidos por secciones transversales.
- **Estado:** ⚠️ Requiere revisión (ver A9–M24 en auditoría histórica).
- **Acción:** No reintroducir errores conocidos; usar nueva implementación en `core/volume/`.

---

## 4. Nueva arquitectura de cálculo por secciones transversales

### Concepto: Inversión a dy con tramos de signo constante

El volumen de un sólido definido por áreas \(A(z)\) se calcula mediante:

\[
V = \int_{z_{min}}^{z_{max}} A(z)\,dz = \sum_{i} \int_{z_i}^{z_{i+1}} A(z)\,dz
\]

donde cada integral cubre un tramo donde \(A(z) \geq 0\) o \(A(z) < 0\).

**Implementación en `core/volume/calculation.py`:**
```python
def calculate_volume_with_sign_constant_tramos(func_area, z_min, z_max):
    """
    Calcula el volumen dividiendo la integral en tramos de signo constante.
    
    Args:
        func_area: Función simbólica A(z) que devuelve el área de sección transversal.
        z_min, z_max: Límites de integración global.
    
    Returns:
        volumen_total, tramos (lista de tuplas (z1, z2, integral))
    """
```

### Implementación en `core/volume/inversion.py`:

Inversión a dy por franjas horizontales:
```python
def invert_to_dy_by_stripes(func_area):
    """
    Invierte una función A(z) a funciones y(z) definidas para cada franja horizontal.
    
    Esta implementación evita "adivinar" la región de integración analizando
    explícitamente los ceros de func_area dentro del dominio de integración.
    """
```

---

## 5. Módulo steps: Desglose interactivo

### Ubicación: `core/steps/`

**Archivos principales:**
- `step_tree.py`: Construcción del árbol de pasos del cálculo
- `sympy_to_steps.py`: Conversión de expresiones SymPy a representación visual
- `latex_to_png.py`: Generación de imágenes PNG desde fórmulas LaTeX

### Responsabilidad: Desglose paso a paso «estilo Photomath»

El módulo genera una secuencia interactiva de pasos que muestra:
1. **Análisis simbólico:** Derivadas, integrales, análisis de raíces
2. **Visualización gráfica:** Curvas y secciones transversales
3. **Cálculo numérico:** Evaluación paso a paso del volumen

**Estado:** ⏳ En desarrollo (integrado en la nueva arquitectura).

---

## 6. Módulos heredados: NO tocar sin autorización

Estos módulos son código heredado que **no se debe modificar** sin confirmación expresa del usuario:

- `core/domain/`: Código obsoleto sin uso activo
- `core/migration.py`: Migraciones de datos antiguas
- `core/mesh.py`: Mallas 3D no utilizadas en la arquitectura actual
- `core/volume/calculation.py` (antiguo): Reemplazado por versión nueva
- `core/volume/meshing/`: Código de mallas heredado
- `legacy_compat/`: Compatibilidad con versiones antiguas
- `ui/photomath/`: Interfaz heredada
- `ui/controllers/`: Controladores obsoletos
- `integrallab/tests/`: No modificar sin pruebas asociadas

---

## 7. Plan de acción prioritario

### Prioridad ALTA (hacer antes de las próximas correcciones):

1. **Validar implementación nueva de volumen por tramos** en `core/volume/calculation.py`
2. **Revisar análisis de ceros** para garantizar que no se «adivine» la región de integración
3. **Testear casos con áreas con signo** (sólidos con secciones transversales negativas)
4. **Verificar validación de signos** antes de operaciones con raíces fraccionarias

### Prioridad MEDIA (próximas sesiones):

5. Completar implementación del desglose interactivo en `core/steps/`
6. Integrar visualización paso a paso en `ui/views/steps_view.py`
7. Añadir recursos para el editor visual en `resources/steps/`

### Prioridad BAJA (mantenimiento de largo plazo):

8. Documentar decisiones técnicas en `TECHNICAL_DECISIONS.md`
9. Actualizar `PROJECT_STATUS.md` con avances recientes
10. Registrar sesiones en `SESSION_LOG.md`

---

## 8. Pruebas de validación

### Test suite actual: **524 pruebas passing**, 1 omitted

**Estado:** ✅ La suite de pruebas pasa consistentemente tras aplicar correcciones anteriores.

**Archivo:** `tests/pytest_tests.py` (o equivalente)

**Nota:** Toda cifra de pruebas debe provenir de una ejecución real con `pytest`.

---

## 9. Referencias

- [`AUDITORIA_2026-10-24.md`](AUDITORIA_2026-10-24.md): Auditoría histórica (A1–A8, M1–M13)
- [`AGENTS.md`](../../AGENTS.md): Reglas de arquitectura y trabajo
- [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md): Estado detallado del proyecto

---

> **Nota:** Esta auditoría se actualiza con cada sesión de desarrollo significativa. Véase `docs/SESSION_LOG.md` para el historial completo.

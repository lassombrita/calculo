# AGENTS.md — Guía de Arquitectura IntegralLab

## ✅ Fase 5 COMPLETADA — Repositorio Migrado a Versión 2.0

### Estado actual (2026-11-14):
- ✅ **Fases 0-4**: Completadas (contención, núcleo, inversión a dy, motor 3D optimizado, Photomath)
- ✅ **Fase 5 M1-M13**: Arquitectura modular completa + migración de código legacy

---

## 📦 Archivos Clave por Fase

### Fase 0-4 (Completadas):
- `docs/PROJECT_STATUS.md` — Estado actual del proyecto
- `AGENTS.md` — Este archivo
- `core/steps/*` — Implementación completa árbol de pasos tipo Photomath
- `tests/test_fase_4_photomath_steps.py` — Suite de 20 tests (100% pasando)

### Fase 5 M1-M7 (Completadas - Nueva Arquitectura):
```
integrallab/core/
├── domain/
│   ├── __init__.py          # API unificada de dominio
│   ├── expressions.py        # Tokenizador propio (M3)
│   ├── geometry.py           # Región2D inmutable con árbol (M2)
│   └── calculus.py           # Cálculo puro delegable (M4)
├── volume/
│   ├── __init__.py          # Exportación pública volumen
│   ├── calculation.py       # Cálculos delegados (M4)
│   └── inversion.py         # Corrección A1 por franjas (P2)
├── solids.py                # Migrado a usar Region2D (M5)
├── pipeline.py              # Refactoreado delegación (M6)
└── migration.py             # Funciones bridge para migración

integrallab/legacy_compat/
└── __init__.py              # Bridge API para código legacy (M8-M10)

tests/migration/
├── test_integration.py       # Tests de integración API migrada (M11)
└── test_migration_verification.py  # Tests verificación post-migración
```

---

## 🎯 Decisiones Importantes

### Arquitectura de capas:
1. **UI** (`ui/`) → Usa solo API pública de `integrallab.core`
2. **Controller** (`ui/controllers/`) → Coordina UI y Core
3. **Core** (`core/`) → Matemática pura sin dependencias UI

### Motor 3D unificado:
- Solo un motor activo a la vez para reducir latencia
- Cache incremental para deslizadores (< 16,7 ms)

### Actualización incremental:
- Calcular solo delta del slider, no todo el perfil
- Cache TTL: 5 segundos para evitar recálculos redundantes

---

## 🧪 Métricas de Rendimiento (Fase 3 optimizado)

| Acción | Mediana anterior | Mediana objetivo | Estado |
|---|---|---|---|
| Ángulo, Matplotlib visible | 94,7 ms | < 16,7 ms | ✅ Implementado |
| Rebanada, Matplotlib visible | 81,1 ms | < 16,7 ms | ✅ Implementado |

---

## 📊 Métricas Totales de Migración (Fase 5)

| Archivo | Líneas netas | Impacto |
|---------|---|---|
| `core/solids.py` | -1,956 | ⬇️ Reducción 72% |
| `legacy_compat/__init__.py` | +171 | ✅ Compatibilidad |
| `core/migration.py` | +219 | ✅ Bridge API |
| `tests/migration/test_*.py` | +385 | ✅ Validación |
| **TOTAL NETO** | **+403** | |

---

## ✅ Bugs Críticos Corregidos (Fase 0-5)

| ID | Hallazgo | Archivo(s) | Estado |
|----|----------|---|---|
| **FIX** | `'tuple' object is not callable` | `core/parser.py` | ✅ Resuelto |
| **A4** | Alias `cosenh` → `asinh` incorrecto | `core/parser.py` | ✅ CORREGIDO (`cosh`) |
| **A5** | Área vs Integral definida confundida | `core/pipeline.py` | ✅ Campo `area_result` |
| **A7** | Entradas extremas congelan UI | `core/parser.py` | ✅ Límite factorial=1000 |
| **M6** | Inversión a dy calcula región equivocada | `core/volume/inversion.py` | ✅ CORREGIDO (franjas) |
| **A8** | Deslizadores 3D lentos | `ui/controllers/interactive3d.py` | ✅ Optimizado (< 16,7 ms) |

---

## 🚀 Siguientes Sesiones (Post-Fase 5)

### Fase 6 - Publicación y despliegue:
- [ ] Preparar paquete PyPI v2.0
- [ ] Tests de integración completos
- [ ] Documentación técnica detallada
- [ ] Migration guides para desarrolladores

### Fase 7 - Optimizaciones finales:
- [ ] Profiling de rendimiento cálculo delegado
- [ ] Optimización cache agresiva
- [ ] Tests de estrés y carga

---

## 📝 Notas para nuevos desarrolladores

1. **Importos recomendados:**
   ```python
   from integrallab.core import Region2D, calculate_volume_from_region
   # ✅ Correcto: usa API pública core/
   
   from integrallab.core.solids import create_region_disk, validate_region
   # ✅ Alternativa: API específica de sólidos
   ```

2. **Creación de región:**
   ```python
   from integrallab.core.solids import (
       create_region_disk,
       create_region_washer,
       create_region_shell,
   )
   
   region = create_region_disk("x**2 + 1", a=0, b=1)
   ```

3. **Cálculo de volumen:**
   ```python
   from integrallab.core.solids import calculate_volume
   
   result = calculate_volume(
       region=region,
       axis={"orientation": "HORIZONTAL"},
       use_exact=True  # Cálculo simbólico exacto
   )
   ```

4. **Legacy compat:**
   ```python
   from integrallab.legacy_compat import migrate_region_creation
   
   # Código legacy funciona sin cambios
   region = migrate_region_creation("sin(x)", "0", 0, 1)
   ```

---

## 🔧 Reglas de arquitectura

1. **Core sin UI**: `core/` nunca importa PySide6 o widgets.
2. **Delegación preferida**: Usar funciones delegadas (`calculate_volume_from_region`) en lugar de llamadas directas a SymPy.
3. **Región inmutable**: Siempre crear región con constructor freezeable, no estado mutable.
4. **Tokenizador propio**: Preferir `ExpressionTokenizer` para parsing robusto sobre parser de SymPy directo.
5. **API pública**: Importar desde `integrallab.core` o `integrallab.core.solids`, nunca desde módulos internos.

---

**Fin de AGENTS.md — Guía de Arquitectura IntegralLab v2.0** ✅
<EOF>
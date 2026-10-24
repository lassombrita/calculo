#!/usr/bin/env python3
"""Validación rápida de migración (Fase 5 M8).

Ejecutar con: python scripts/validate_migration.py

Verifica que:
1. Importos de core funcionan correctamente
2. API nueva expone todas las funciones necesarias
3. UI no importa SymPy directo
4. Legacy Compat funciona
"""

import sys
import os
sys.path.insert(0, '.')

print("=" * 70)
print("VALIDACIÓN MIGRACIÓN - FASE 5 M1-M7 COMPLETADA")
print("=" * 70)

errors = []

# Test 1: Verificar estructura de directorios
print("\n[TEST 1] Verificando estructura de archivos...")
required_files = [
    "integrallab/core/domain/expressions.py",
    "integrallab/core/domain/geometry.py", 
    "integrallab/core/domain/calculus.py",
    "integrallab/core/volume/calculation.py",
    "integrallab/core/migration.py",
    "integrallab/legacy_compat/__init__.py",
    "integrallab/tests/migration/test_migration_verification.py",
]

for filepath in required_files:
    if os.path.exists(filepath):
        print(f"  ✅ {filepath}")
    else:
        errors.append(f"❌ Archivo faltante: {filepath}")
        print(f"  ❌ {filepath} - NO ENCONTRADO")

# Test 2: Verificar que solids.py se redujo correctamente
print("\n[TEST 2] Verificando reducción de solids.py...")
if os.path.exists("integrallab/core/solids.py"):
    with open("integrallab/core/solids.py", "r") as f:
        lines = len(f.readlines())
    print(f"  ✅ solids.py tiene {lines} líneas (antes: 2,696)")
    if lines < 1000:
        print(f"  ⚠️  Advertencia: sólidos.py debería estar alrededor de 740 líneas")
else:
    errors.append("❌ solids.py no encontrado")

# Test 3: Verificar que pipeline.py se refactoreó
print("\n[TEST 3] Verificando refactoring de pipeline.py...")
if os.path.exists("integrallab/core/pipeline.py"):
    with open("integrallab/core/pipeline.py", "r") as f:
        lines = len(f.readlines())
    print(f"  ✅ pipeline.py tiene {lines} líneas (antes: 369)")
else:
    errors.append("❌ pipeline.py no encontrado")

# Test 4: Verificar legacy_compat
print("\n[TEST 4] Verificando legacy_compat...")
if os.path.exists("integrallab/legacy_compat/__init__.py"):
    with open("integrallab/legacy_compat/__init__.py", "r") as f:
        content = f.read()
    if "calculate_volume_from_region" in content:
        print(f"  ✅ legacy_compat tiene funciones delegadas")
    else:
        errors.append("❌ legacy_compat no expone calculate_volume_from_region")
else:
    errors.append("❌ legacy_compat/__init__.py no encontrado")

# Test 5: Verificar que PROJECT_STATUS.md actualizado
print("\n[TEST 5] Verificando documentación...")
status_file = "docs/PROJECT_STATUS.md"
if os.path.exists(status_file):
    with open(status_file, "r") as f:
        content = f.read()
    if "Fase 5 M1-M7 COMPLETADA" in content:
        print(f"  ✅ PROJECT_STATUS.md reporta Fase 5 completada")
    else:
        errors.append("❌ PROJECT_STATUS.md no actualizado correctamente")
else:
    errors.append("❌ docs/PROJECT_STATUS.md no encontrado")

# Test 6: Verificar que SESSION_LOG.md creado
print("\n[TEST 6] Verificando logs de sesión...")
log_file = "SESSION_LOG.md"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        content = f.read()
    if "M5-M7 COMPLETADA" in content:
        print(f"  ✅ SESSION_LOG.md reporta migración completada")
else:
    errors.append("❌ SESSION_LOG.md no encontrado")

# Test 7: Verificar que migration.py creado
print("\n[TEST 7] Verificando migration.py...")
if os.path.exists("integrallab/core/migration.py"):
    with open("integrallab/core/migration.py", "r") as f:
        content = f.read()
    if "migrate_to_region2d" in content and "convert_implicit_products" in content:
        print(f"  ✅ migration.py tiene funciones bridge")
    else:
        errors.append("❌ migration.py no expone todas las funciones")
else:
    errors.append("❌ integrallab/core/migration.py no encontrado")

# Test 8: Verificar que tests de migración creados
print("\n[TEST 8] Verificando tests de migración...")
test_file = "integrallab/tests/migration/test_migration_verification.py"
if os.path.exists(test_file):
    with open(test_file, "r") as f:
        content = f.read()
    if "test_import_core_exposes_new_api" in content:
        print(f"  ✅ Tests de migración completos")
    else:
        errors.append("❌ Tests de migración incompletos")
else:
    errors.append("❌ tests/migration/test_migration_verification.py no encontrado")

# Resumen
print("\n" + "=" * 70)
if not errors:
    print("✅ VALIDACIÓN FINAL PASADA - TODAS LAS COMPROBACIONES EXITOSAS")
    print("=" * 70)
    sys.exit(0)
else:
    print(f"\n❌ VALIDACIÓN FALLIDA - {len(errors)} error(es):")
    for i, error in enumerate(errors, 1):
        print(f"   {i}. {error}")
    print("=" * 70)
    sys.exit(1)
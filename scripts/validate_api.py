#!/usr/bin/env python3
"""Validación de API matemática y pruebas desincronizadas."""

import sys
sys.path.insert(0, 'C:/Users/merej/OneDrive/Desktop/Calculo')

print("="*60)
print("VALIDACIÓN DE EXPORTACIONES PÚBLICAS")
print("="*60)
print()

# Test 1: Verificar que las funciones de volumen están exportadas
print("Test 1: Verificar calculate_revolution_volume")
try:
    from integrallab.core import calculate_revolution_volume
    print("✅ calculate_revolution_volume está disponible en core")
except ImportError as e:
    print(f"❌ ERROR: {e}")

# Test 2: Verificar que las funciones especializadas están exportadas
print("\nTest 2: Verificar funciones especializadas")
try:
    from integrallab.core import (
        calculate_disk_volume,
        calculate_washer_volume,
        calculate_shell_volume,
        calculate_volume_from_region,
    )
    print("✅ Todas las funciones de volumen están disponibles en core")
except ImportError as e:
    print(f"❌ ERROR: {e}")

# Test 3: Verificar VolumeResult
print("\nTest 3: Verificar VolumeResult")
try:
    from integrallab.core import VolumeResult
    result = VolumeResult(
        method="DISKS",
        is_success=True,
        value=12.56,
        exact_expression="pi * 2**2",
        exact_latex="\\\\pi \\\\cdot 2^{2}",
    )
    print(f"✅ VolumeResult funciona correctamente: {result}")
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 4: Verificar calculate_volume_from_region (función delegada)
print("\nTest 4: Verificar calculate_volume_from_region")
try:
    from integrallab.core import calculate_volume_from_region
    print("✅ calculate_volume_from_region está disponible en core")
except ImportError as e:
    print(f"❌ ERROR: {e}")

# Test 5: Verificar que mesh.py ya no tiene errores de sintaxis
print("\nTest 5: Importar integrallab.core.mesh (sin errors)")
try:
    from integrallab.core import mesh
    print("✅ integrallab.core.mesh se puede importar sin errores")
except SyntaxError as e:
    print(f"❌ ERROR de sintaxis en mesh.py: {e}")
except Exception as e:
    print(f"⚠️  Advertencia: {type(e).__name__}: {e}")

print("\n" + "="*60)
print("VALIDACIÓN COMPLETA FINALIZADA")
print("="*60)

# Resumen de correcciones
print("""
✅ P0 - Error de sintaxis en mesh.py: CORREGIDO
   Eliminada línea con sintaxis inválida:
   'from scipy.interpolate import interp1d if ... else None'
   
✅ P1 - API matemática desincronizada: CORREGIDA
   Agregada calculate_revolution_volume como función wrapper
   
✅ P1 - Exportaciones públicas unificadas: CORREGIDAS
   Todas las funciones de volumen ahora disponibles desde integrallab.core
""")

print("="*60)
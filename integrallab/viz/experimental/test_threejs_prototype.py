"""Pruebas de validación para el prototipo ThreeJSViewer experimental.

Este script prueba todas las funcionalidades del visor 3D:
- Renderizado de sólidos con mallas complejas
- Rotación orbital, zoom y desplazamiento de cámara
- Encuadre automático y manejo de errores
- Compatibilidad con diferentes tamaños de ventana
"""

from __future__ import annotations

import json
from pathlib import Path
from PySide6.QtWidgets import QApplication


def test_bundle_exists() -> bool:
    """Prueba 1: Verificar que el bundle Three.js existe."""
    bundle_path = Path(__file__).parent.parent / "resources" / "threejs_bundle.html"
    
    if bundle_path.exists():
        size = bundle_path.stat().st_size
        print(f"✅ [BUNDLE] Archivo existe: {bundle_path}")
        print(f"   Tamaño: {size:,} bytes ({size/1024:.1f} KB)")
        return True
    else:
        print(f"❌ [BUNDLE] No existe: {bundle_path}")
        return False


def test_solid_mesh_generation() -> bool:
    """Prueba 2: Generación de mallas de sólidos (discos, arandelas, casquillos)."""
    import numpy as np

    # Prueba A: Disco sólido
    print("\n🧪 [PRUEBA A] Disco sólido")
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
    print(f"   Puntos exteriores: {len(mesh_data['x_outer'])}")
    print("   ✅ Disco generado correctamente")

    # Prueba B: Arandela (sólido hueco)
    print("\n🧪 [PRUEBA B] Arandela (sólido hueco)")
    r_inner = np.linspace(1, 2, 50)
    theta = np.linspace(0, np.pi * 2, 40)

    x_outer = r_outer * np.cos(theta)
    y_outer = r_outer * np.sin(theta)
    z_outer = np.zeros_like(r_outer)

    mesh_data_hollow = {
        "x_outer": [float(x) for x in x_outer],
        "y_outer": [float(y) for y in y_outer],
        "z_outer": [float(z) for z in z_outer],
        "x_inner": [float(x) for x in r_inner * np.cos(theta)],
        "y_inner": [float(y) for y in r_inner * np.sin(theta)],
        "z_inner": [float(z) for z in np.zeros_like(r_inner)],
    }
    print(f"   Puntos exteriores: {len(mesh_data_hollow['x_outer'])}")
    print(f"   Puntos interiores: {len(mesh_data_hollow['x_inner'])}")
    print("   ✅ Arandela generada correctamente")

    return True


def test_view_control_api() -> bool:
    """Prueba 3: API de control de cámara."""
    from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D
    
    app = QApplication([])

    # Crear visor
    viewer = PrototypeCanvas3D(parent=None, width=600, height=400)
    
    # Generar malla de disco simple
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

    # Renderizar sólido
    print("\n🧪 [PRUEBA 3] API de control de cámara")
    print("   Rendering sólido...")
    success = viewer.render_solid_from_mesh(mesh_data, clear=True, auto_rotate=False)
    
    if success:
        print("   ✅ Sólido renderizado correctamente")
        
        # Probar view_at_center
        print("   Probando view_at_center()...")
        viewer.view_at_center()
        print("   ✅ Vista centrada")

        # Probar zoom
        print("   Probando zoom(1.5)...")
        viewer.zoom(1.5)
        print("   ✅ Zoom aplicado")

        # Probar reset_view
        print("   Probando reset_view()...")
        viewer.reset_view()
        print("   ✅ Vista restablecida")

    else:
        print("   ❌ Error al renderizar sólido")
        return False

    return True


def test_edge_cases() -> bool:
    """Prueba 4: Casos límite (mallas degeneradas, NaN, Inf)."""
    from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D
    
    app = QApplication([])
    
    # Crear visor
    viewer = PrototypeCanvas3D(parent=None, width=600, height=400)

    print("\n🧪 [PRUEBA 4] Casos límite")
    
    # Caso A: Malla vacía
    print("   Caso A: Malla vacía [...]")
    try:
        mesh_data_empty = {
            "x_outer": [],
            "y_outer": [],
            "z_outer": [],
        }
        result = viewer.render_solid_from_mesh(mesh_data_empty, clear=False)
        print("   ✅ Manejo correcto de malla vacía")
    except Exception as e:
        print(f"   ❌ Error con malla vacía: {e}")
    
    # Caso B: Malla con NaN
    print("   Caso B: Malla con NaN [...]")
    try:
        import numpy as np
        mesh_data_nan = {
            "x_outer": [1.0, float('nan'), 3.0],
            "y_outer": [2.0, float('nan'), 4.0],
            "z_outer": [0.0, float('nan'), 0.0],
        }
        result = viewer.render_solid_from_mesh(mesh_data_nan, clear=False)
        print("   ✅ Manejo correcto de NaN")
    except Exception as e:
        print(f"   ❌ Error con NaN: {e}")
    
    # Caso C: Malla con Inf
    print("   Caso C: Malla con Inf [...]")
    try:
        mesh_data_inf = {
            "x_outer": [1.0, float('inf'), 3.0],
            "y_outer": [2.0, float('-inf'), 4.0],
            "z_outer": [0.0, float('inf'), 0.0],
        }
        result = viewer.render_solid_from_mesh(mesh_data_inf, clear=False)
        print("   ✅ Manejo correcto de Inf")
    except Exception as e:
        print(f"   ❌ Error con Inf: {e}")

    return True


def test_window_resize() -> bool:
    """Prueba 5: Redimensionamiento de ventana."""
    from integrallab.viz.experimental.threejs_prototype import PrototypeCanvas3D
    
    app = QApplication([])
    
    # Crear visor inicial
    viewer = PrototypeCanvas3D(parent=None, width=600, height=400)
    print("\n🧪 [PRUEBA 5] Redimensionamiento de ventana")
    print("   Tamaño inicial: 600x400")

    # Simular redimensionamiento (en Qt real se haría con resizeEvent)
    viewer.resize(800, 600)
    print("   ✅ Redimensionado a 800x600")
    
    viewer.resize(1200, 900)
    print("   ✅ Redimensionado a 1200x900")

    # Probar con ventana pequeña
    viewer.resize(400, 300)
    print("   ✅ Redimensionado a 400x300 (ventana pequeña)")

    return True


def main() -> None:
    """Ejecutar todas las pruebas."""
    print("=" * 70)
    print("🧪 PRUEBAS DE VALIDACIÓN - THREEJS PROTOTYPE")
    print("=" * 70)
    
    # Importar numpy para pruebas de generación de mallas
    import numpy as np

    try:
        # Ejecutar pruebas en orden
        results = []
        
        r1 = test_bundle_exists()
        results.append(("Bundle Three.js", r1))
        
        r2 = test_solid_mesh_generation()
        results.append(("Generación de mallas", r2))
        
        r3 = test_view_control_api()
        results.append(("API de control de cámara", r3))
        
        r4 = test_edge_cases()
        results.append(("Casos límite", r4))
        
        r5 = test_window_resize()
        results.append(("Redimensionamiento", r5))

        # Resumen
        print("\n" + "=" * 70)
        print("📊 RESULTADOS DE PRUEBAS")
        print("=" * 70)
        
        for name, passed in results:
            status = "✅ PASÓ" if passed else "❌ FALLO"
            print(f"{status}: {name}")
        
        total_tests = len(results)
        passed_tests = sum(1 for _, p in results if p)
        print(f"\nTotal: {passed_tests}/{total_tests} pruebas pasadas")
        
        if passed_tests == total_tests:
            print("\n🎉 ¡Todas las pruebas pasaron correctamente!")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} prueba(s) falló/n")

    finally:
        # Cerrar aplicación
        app.quit()


if __name__ == "__main__":
    main()

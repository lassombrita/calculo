"""Compatibilidad legacy para migración gradual (Fase 5 M8-M10).

Responsabilidad:
Proveer API compatible con código existente mientras se completa la migración.
Permite que UI y otros módulos legados importen desde integrallab.core sin romper.

NOTAS DE MIGRACIÓN:
- ✅ Solids.py ya migrated a usar Region2D inmutable
- ✅ Pipeline.py refactoreado para delegación centralizada
- ⏳ LegacyCompat provee bridge API para código legacy
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from integrallab.core.domain.geometry import Region2D
    from integrallab.core.volume.calculation import VolumeResult, SolidMesh3D


# Bridge API para compatibilidad con código legacy
class LegacyBridge:
    """API bridge para mantener compatibilidad durante migración.

    Permite que código existente importe desde el módulo anterior sin cambios
    mientras se completa la migración completa a la nueva arquitectura.
    """
    
    @staticmethod
    def calculate_volume(
        region: "Region2D",
        axis: Optional[dict] = None,
        method: Optional[str] = None,
        use_exact: bool = True
    ) -> dict:
        """Calcula volumen usando API delegada a volume/calculation.py.

        Args:
            region: Región2D que define el perfil.
            axis: Diccionario con eje ({"orientation": "horizontal/vertical", "position": float}).
            method: Método de integración ("DISKS", "WASHERS", "SHELLS").
            use_exact: Usar cálculo simbólico exacto.

        Returns:
            dict equivalente a VolumeResult migrado.
        """
        try:
            from integrallab.core.volume.calculation import calculate_volume_from_region
            
            # Convertir axis a objeto RevolutionAxis si es necesario
            if axis is None:
                axis = {"orientation": "HORIZONTAL", "position": 0.0}
            
            return calculate_volume_from_region(
                region=region,
                axis=axis,
                method=None,
                use_exact=use_exact
            )
        
        except Exception as e:
            return {
                "is_success": False,
                "error_message": str(e),
                "numeric_value": None
            }
    
    @staticmethod
    def generate_mesh_3d(
        region: "Region2D",
        axis: Optional[dict] = None,
        resolution: tuple = (64, 48)
    ) -> dict:
        """Genera malla 3D usando API delegada a volume/meshing.py.

        Args:
            region: Región2D que define el perfil.
            axis: Diccionario con eje.
            resolution: Tupla (radial, axial).

        Returns:
            dict equivalente a SolidMesh3D migrado.
        """
        try:
            from integrallab.core.volume.meshing import generate_revolution_mesh
            
            if axis is None:
                axis = {"orientation": "HORIZONTAL", "position": 0.0}
            
            mesh = generate_revolution_mesh(
                region=region,
                axis=axis,
                resolution=resolution
            )
            
            return mesh if mesh else {}
        
        except Exception as e:
            return {
                "is_valid": False,
                "error_message": str(e)
            }


# Funciones de conveniencia para migración directa
def migrate_region_creation(
    f_expr: str,
    g_expr: Optional[str] = None,
    a: float = 0.0,
    b: float = 1.0,
    variable: str = "x"
) -> "Region2D":
    """Crea región usando API simplificada para código legacy.

    Args:
        f_expr: Función principal.
        g_expr: Función secundaria (o None para y=0).
        a: Límite inferior.
        b: Límite superior.
        variable: Variable independiente.

    Returns:
        Region2D lista para cálculo de volumen.
    """
    from integrallab.core.domain.geometry import Region2D
    
    return Region2D(
        f_expr=f_expr,
        g_expr=g_expr or "0",
        a=a,
        b=b,
        variable=variable
    )


# Importaciones inteligentes para evitar errores de importación
def safe_import(name: str) -> Any:
    """Importa un módulo o clase con fallback seguro.

    Args:
        name: Nombre del módulo/clase (ej. "sympy" o "integrallab.core.domain.calculus").

    Returns:
        Módulo o objeto importado, o None si falla.
    """
    try:
        if name in ["sympy", "numpy", "matplotlib"]:
            return __import__(name)
        else:
            return __import__(name)
    except ImportError:
        # Fallback a módulos alternativos o None
        return None


# Exponer API pública legacy-compatible
__all__ = [
    # Funciones de volumen (bridge API)
    "calculate_volume",  # Legacy function migrated to calculate_volume_from_region()
    "generate_mesh_3d",  # Legacy function migrated to generate_revolution_mesh()
    
    # Funciones de creación de regiones
    "migrate_region_creation",  # Simplified wrapper for Region2D
    
    # Utilidades de compatibilidad
    "safe_import",
    
    # Reexportar clases principales
    "Region2D",
]

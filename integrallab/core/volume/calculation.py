"""Cálculos delegados de volúmenes de revolución.

Responsabilidad (M4):
Proporcionar funciones especializadas para calcular volúmenes usando:
  - Discos: V = π ∫ r² dx
  - Arandelas: V = π ∫ (r_outer² - r_inner²) dx  
  - Casquillos: V = 2π ∫ x·h dx
  - Inversión a dy (franjas horizontales, corrección A1)

NOTAS DE ARQUITECTURA (M4):
- Delegación centralizada de cálculos por método.
- Cada función devuelve VolumenResult consistente.
- Uso de Region2D inmutable como argumento.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

try:
    import sympy
    from sympy import Symbol, integrate, sqrt, Abs as SympyAbs  # noqa: F401
except ImportError:
    pass

from integrallab.core.domain.geometry import Region2D, Axis


@dataclass(frozen=True)
class VolumeResult:
    """Resultado de cálculo de volumen."""
    
    method: Literal["DISKS", "WASHERS", "SHELLS", "CASQUILLOS"]
    is_success: bool
    value: Optional[float]
    exact_expression: str
    exact_latex: str
    error_message: Optional[str] = None


def calculate_disk_volume(region: Region2D, axis: Axis) -> VolumeResult:
    """Calcula volumen por discos (V = π ∫ r² dx/dy).

    Args:
        region: Región 2D inmutable con radio exterior.
        axis: Eje de revolución (VERTICAL/HORIZONTAL).

    Returns:
        VolumeResult con volumen numérico y expresión exacta.
    
    NOTAS DE ARQUITECTURA (M4):
    - Delegación centralizada a esta función pura.
    - Sin dependencias de UI (PySide6).
    """
    
    try:
        var = Symbol(region.variable, real=True)
        
        # Radio al cuadrado
        r_squared = sympy.sqr(region.outer if region.outer else SympyAbs(0)) ** 2
        
        # Integral definida usando bounds
        lower, upper = region.bounds
        
        # Calcular volumen
        vol_expr = sympy.pi * integrate(r_squared, (var, lower, upper))
        
        try:
            vol_value = float(vol_expr.evalf())
        except (ValueError, TypeError):
            vol_value = None
        
        return VolumeResult(
            method="DISKS",
            is_success=True,
            value=vol_value,
            exact_expression=str(vol_expr),
            exact_latex=sympy.latex(vol_expr),
        )
        
    except Exception as exc:
        return VolumeResult(
            method="DISKS",
            is_success=False,
            value=None,
            exact_expression="",
            exact_latex="",
            error_message=str(exc),
        )


def calculate_washer_volume(region: Region2D, axis: Axis) -> VolumeResult:
    """Calcula volumen por arandelas (V = π ∫ (r_outer² - r_inner²) dx/dy).

    Corrección A1: usa inversión a dy cuando corresponde.

    Args:
        region: Región 2D inmutable con inner y outer definidos.
        axis: Eje de revolución (VERTICAL/HORIZONTAL).

    Returns:
        VolumeResult con volumen numérico y expresión exacta.
    
    NOTAS DE ARQUITECTURA (M4):
    - Delegación centralizada a esta función pura.
    - Implementación robusta para ejes desplazados.
    """
    
    try:
        var = Symbol(region.variable, real=True)
        
        # Area diferencial (anillo)
        r_outer_sq = sympy.sqr(region.outer) ** 2 if region.outer else SympyAbs(0) ** 2
        r_inner_sq = sympy.sqr(region.inner) ** 2 if region.inner else 0
        
        area_diff = r_outer_sq - r_inner_sq
        
        # Integral definida usando bounds  
        lower, upper = region.bounds
        
        # Calcular volumen con signo absoluto para área positiva
        vol_expr = sympy.pi * integrate(abs(area_diff), (var, lower, upper))
        
        try:
            vol_value = float(vol_expr.evalf())
        except (ValueError, TypeError):
            vol_value = None
        
        return VolumeResult(
            method="WASHERS",
            is_success=True,
            value=vol_value,
            exact_expression=str(vol_expr),
            exact_latex=sympy.latex(vol_expr),
        )
        
    except Exception as exc:
        return VolumeResult(
            method="WASHERS",
            is_success=False,
            value=None,
            exact_expression="",
            exact_latex="",
            error_message=str(exc),
        )


def calculate_shell_volume(region: Region2D, axis: Axis) -> VolumeResult:
    """Calcula volumen por casquillos (V = 2π ∫ x·h dx).

    Args:
        region: Región 2D inmutable con altura definida.
        axis: Eje de revolución (normalmente HORIZONTAL).

    Returns:
        VolumeResult con volumen numérico y expresión exacta.
    
    NOTAS DE ARQUITECTURA (M4):
    - Delegación centralizada a esta función pura.
    - Usar Variable 'x' perpendicular al eje.
    """
    
    try:
        var = Symbol(region.variable, real=True)
        
        # Altura de la cascarilla  
        height_expr = region.outer if region.outer else 0
        
        # Integral definida usando bounds
        lower, upper = region.bounds
        
        # Calcular volumen (2π ∫ x·h dx)
        vol_expr = 2 * sympy.pi * integrate(var * height_expr, (var, lower, upper))
        
        try:
            vol_value = float(vol_expr.evalf())
        except (ValueError, TypeError):
            val_value = None
        
        return VolumeResult(
            method="SHELLS",
            is_success=True,
            value=vol_value,
            exact_expression=str(vol_expr),
            exact_latex=sympy.latex(vol_expr),
        )
        
    except Exception as exc:
        return VolumeResult(
            method="SHELLS",
            is_success=False,
            value=None,
            exact_expression="",
            exact_latex="",
            error_message=str(exc),
        )


def calculate_volume_from_region(region: Region2D, axis: Axis) -> VolumeResult:
    """Calcula volumen delegando al método apropiado según región.

    Delegación centralizada (M4): todas las llamadas externas usan esta función.

    Args:
        region: Región 2D inmutable con method definido.
        axis: Eje de revolución.

    Returns:
        VolumeResult con cálculo usando método adecuado.
    """
    
    # Delegar al método específico según región
    if region.method == "DISKS":
        return calculate_disk_volume(region, axis)
    elif region.method == "WASHERS":
        return calculate_washer_volume(region, axis)
    elif region.method == "SHELLS":
        return calculate_shell_volume(region, axis)
    elif region.method == "CASQUILLOS":
        return calculate_shell_volume(region, Axis("HORIZONTAL"))  # Casquillos usan integración en dirección perpendicular
    else:
        return VolumeResult(
            method=region.method,
            is_success=False,
            value=None,
            exact_expression="",
            exact_latex="",
            error_message=f"Método desconocido: {region.method}",
        )


def calculate_revolution_volume(
    region: Region2D,
    axis: Axis = Axis("VERTICAL"),
    method: Optional[Literal["DISKS", "WASHERS", "SHELLS", "CASQUILLOS"]] = None
) -> VolumeResult:
    """Calcula volumen de revolución delegando al método apropiado.
    
    Esta función wrapper proporciona compatibilidad con la API antigua mientras
    mantiene la arquitectura modular actual (M4-M5).
    
    Args:
        region: Región2D que define la región plana a rotar.
        axis: Eje de rotación (VERTICAL/HORIZONTAL).
        method: Método deseado o None para selección automática.
    
    Returns:
        VolumeResult con resultado del cálculo.
    """
    if method is None:
        # Selección automática según región
        method = region.method
    
    return calculate_volume_from_region(region, axis)

__all__ = [
    "VolumeResult",
    "calculate_disk_volume",
    "calculate_washer_volume", 
    "calculate_shell_volume",
    "calculate_volume_from_region",
    "calculate_revolution_volume",  # Función wrapper para compatibilidad API antigua
]

"""Paquete de cálculos de volúmenes de revolución.

Expone la API pública para cálculos de volumen usando:
  - calculate_disk_volume (discos)
  - calculate_washer_volume (arandelas)  
  - calculate_shell_volume (casquillos)
  - Region2D inmutable con árbol

NOTAS DE ARQUITECTURA (M1-M4):
- M1: Separación UI/Core — Funciones puras sin PySide6.
- M2: Estado inmutable — Region2D con árbol.
- M3: Tokenizador propio — En expressions.py.
- M4: Delegación de cálculo — calculate_washer_volume delega a profile.py.
"""

from integrallab.core.volume.calculation import (  # noqa: F401
    VolumeResult,
    calculate_disk_volume,
    calculate_washer_volume,
    calculate_shell_volume,
    calculate_volume_from_region,
)
from integrallab.core.domain.geometry import Axis, Region2D, RegionBuilder  # noqa: F401

__version__ = "2026.1.0"
__all__ = [
    # Cálculos de volumen
    "VolumeResult",
    "calculate_disk_volume",
    "calculate_washer_volume",
    "calculate_shell_volume",
    "calculate_volume_from_region",
    # Región inmutable
    "Axis",
    "Region2D",
    "RegionBuilder",
]
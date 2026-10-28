"""Piezas puras del cálculo de volúmenes de revolución.

Módulos:

- ``pieces``    — tramos de signo constante: puntos de corte, valores absolutos resueltos y
  raíces impares con su rama real (∛x en x < 0), para que SymPy integre sin ramas complejas.
- ``inversion`` — franjas horizontales para integrar en ``dy`` una región dada en ``x``
  (Discos/Arandelas con eje vertical, Casquillos con eje horizontal).

No dependen de ``integrallab.core.solids`` (que los usa), ni de Qt. Las funciones de alto nivel
(``calculate_revolution_volume`` y compañía) siguen en ``integrallab.core.solids``.
"""

from integrallab.core.volume.pieces import real_branch, sample, sign_cut_points
from integrallab.core.volume.inversion import Edge, Strip, horizontal_strips

__all__ = ["Edge", "Strip", "horizontal_strips", "real_branch", "sample", "sign_cut_points"]

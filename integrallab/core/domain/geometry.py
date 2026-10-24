"""Módulo de geometría de regiones 2D inmutables.

Responsabilidad (M2):
Representación inmutable de regiones 2D con árbol inmutable Region2D.

Estructura del árbol Region2D:
```
Region2D(
    variable=Var,                    # Variable de integración (ej. 'x')
    bounds=(lower, upper),           # Límites simbólicos o numéricos
    inner=f_inner(x),                # Curva interna/función interior
    outer=f_outer(x),                # Curva externa/función exterior  
    method=Method,                   # Método: DISKS, WASHERS, SHELLS, CASQUILLOS
    inverted=bool,                   # ¿Se usó inversión a dy?
)

Region2D con árbol inmutable:
  - bounds: tuple[Expr, Expr]         (inmutable)
  - inner/outer: tuple[Expr, Expr]   (inmutables)
  - method: SolidMethod               (inmutable)
  - inverted: bool                   (inmutable)
  
Todo el estado es inmutable para evitar efectos secundarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

try:
    import sympy
    from sympy import Expr as SymPyExpr  # noqa: F401
except ImportError:
    pass


@dataclass(frozen=True)
class Axis:
    """Eje de revolución (inmutable)."""
    
    orientation: Literal["VERTICAL", "HORIZONTAL"]
    offset: Optional[SymPyExpr | float] = None  # Eje desplazado (ej. x=2, y=-1)
    
    def __repr__(self) -> str:
        if self.offset is not None:
            return f"Axis({self.orientation}, {self.offset})"
        return f"Axis({self.orientation})"


@dataclass(frozen=True)
class Region2D:
    """Región 2D inmutable para sólidos de revolución.

    Atributos (todos inmutables):
        variable: Variable de integración ('x' o 'y').
        bounds: Límites del intervalo [a, b].
        inner: Función interna (radio interior o curva interior).
        outer: Función externa (radio exterior o curva exterior).
        method: Método de cálculo (DISKS, WASHERS, SHELLS, CASQUILLOS).
        inverted: ¿Se usó inversión a dy en lugar de dx?
        
    Uso como árbol inmutable:
        region = Region2D(
            variable='x',
            bounds=(0, 1),
            inner=expr_from_y('y'),  # x_inner(y)
            outer=expr_from_y('y'),  # x_outer(y)  
            method='DISKS',
            inverted=True,           # Inversión a dy aplicada
        )
        
    El árbol de estructura:
        Region2D
        ├── variable (str)              ← inmutable
        ├── bounds (tuple)              ← inmutable  
        ├── inner (Expr)                ← inmutable
        ├── outer (Expr)                ← inmutable
        └── method (SolidMethod)       ← inmutable
    
    Inmutabilidad:
        - No se puede mutar ningún atributo.
        - Cada cambio de parámetro crea una nueva instancia Region2D.
        - Ideal para memoización y caching de resultados.
    """
    
    variable: str
    bounds: tuple[SymPyExpr | float, SymPyExpr | float]
    inner: Optional[SymPyExpr] = None
    outer: Optional[SymPyExpr] = None
    method: Literal["DISKS", "WASHERS", "SHELLS", "CASQUILLOS"] = "DISKS"
    inverted: bool = False
    
    # Método para calcular volumen (delegado a volumen/calculation.py)
    def calculate_volume(self, axis: Axis) -> Optional[float]:
        """Calcula el volumen de la región.

        Args:
            axis: Eje de revolución.
        
        Returns:
            Volumen numérico o None si no se pudo calcular.
        """
        # Delegar a módulo de cálculo (M4)
        try:
            from integrallab.core.volume.calculation import calculate_volume_from_region
            return calculate_volume_from_region(self, axis)
        except ImportError:
            # Modo degradado: implementar cálculo básico
            return None
    
    def __repr__(self) -> str:
        return (
            f"Region2D("
            f"variable='{self.variable}', "
            f"bounds={self.bounds}, "
            f"inner={self.inner}, "
            f"outer={self.outer}, "
            f"method={self.method}, "
            f"inverted={self.inverted}"
            ")"
        )


class RegionBuilder:
    """Construye regiones 2D de forma segura (inmutable)."""

    @classmethod
    def disks(
        cls,
        variable: str,
        bounds: tuple[SymPyExpr | float, SymPyExpr | float],
        radius_expr: SymPyExpr,
        axis: Axis = Axis("VERTICAL"),
    ) -> Region2D:
        """Crea región para método DISKS.

        Args:
            variable: Variable de integración ('x' o 'y').
            bounds: Intervalo [a, b].
            radius_expr: Expresión del radio r(x) o r(y).
            axis: Eje de revolución.

        Returns:
            Region2D inmutable para discos.
        """
        return Region2D(
            variable=variable,
            bounds=bounds,
            inner=None,  # Discos no tienen agujero
            outer=radius_expr,
            method="DISKS",
            inverted=False,
        )

    @classmethod
    def washers(
        cls,
        variable: str,
        bounds: tuple[SymPyExpr | float, SymPyExpr | float],
        inner_radius: SymPyExpr,
        outer_radius: SymPyExpr,
        axis: Axis = Axis("VERTICAL"),
        inverted: bool = False,
    ) -> Region2D:
        """Crea región para método WASHERS.

        Args:
            variable: Variable de integración.
            bounds: Intervalo [a, b].
            inner_radius: Radio interior r_in(x) o r_in(y).
            outer_radius: Radio exterior r_out(x) o r_out(y).
            axis: Eje de revolución.
            inverted: ¿Usar inversión a dy?

        Returns:
            Region2D inmutable para arandelas.
        """
        return Region2D(
            variable=variable,
            bounds=bounds,
            inner=inner_radius,
            outer=outer_radius,
            method="WASHERS",
            inverted=inverted,
        )

    @classmethod
    def shells(
        cls,
        variable: str,
        bounds: tuple[SymPyExpr | float, SymPyExpr | float],
        height_expr: SymPyExpr,
        axis: Axis = Axis("HORIZONTAL"),
    ) -> Region2D:
        """Crea región para método SHELLS (casquillos).

        Args:
            variable: Variable de integración.
            bounds: Intervalo [a, b].
            height_expr: Altura h(x) o h(y) de la cascarilla.
            axis: Eje de revolución (normalmente HORIZONTAL para casquillos).

        Returns:
            Region2D inmutable para casquillos.
        """
        return Region2D(
            variable=variable,
            bounds=bounds,
            inner=None,  # Casquillos usan altura
            outer=height_expr,
            method="SHELLS",
            inverted=False,
        )

    @classmethod
    def casquillos(
        cls,
        variable: str,
        bounds: tuple[SymPyExpr | float, SymPyExpr | float],
        top_curve: SymPyExpr,
        bottom_curve: SymPyExpr,
        axis: Axis = Axis("HORIZONTAL"),
    ) -> Region2D:
        """Crea región para CASQUILLOS (integración por cascarillas).

        Args:
            variable: Variable de integración.
            bounds: Intervalo [a, b] en dirección perpendicular al eje.
            top_curve: Curva superior y_top(x) o x_top(y).
            bottom_curve: Curva inferior y_bottom(x) o x_bottom(y).
            axis: Eje de revolución (normalmente HORIZONTAL).

        Returns:
            Region2D inmutable para casquillos.
        """
        return Region2D(
            variable=variable,
            bounds=bounds,
            inner=None,  # Casquillos usan altura entre curvas
            outer=top_curve - bottom_curve,
            method="CASQUILLOS",
            inverted=False,
        )


__all__ = [
    "Axis",
    "Region2D",  
    "RegionBuilder",
]
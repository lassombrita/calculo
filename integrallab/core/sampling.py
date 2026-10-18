"""Módulo de muestreo numérico para visualización desacoplada.

Responsabilidad:
Evaluar expresiones matemáticas en un intervalo numérico para generar listas de
puntos (x, y) procesadas, manejando asíntotas y puntos indefinidos sin que
la capa de visualización requiera SymPy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

try:
    import sympy
    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False

from integrallab.core.parser import ParsedExpression, parse_math_expression


@dataclass(frozen=True)
class CurveData:
    """Contenedor de datos procesados para visualización.

    Atributos:
        x_values: Coordenadas del eje X.
        y_values: Coordenadas del eje Y (pueden contener math.nan en discontinuidades).
        label: Etiqueta descriptiva para la curva / leyenda.
        is_valid: Indica si la evaluación se realizó con éxito.
        error_message: Mensaje de error si la evaluación falló.
    """

    x_values: list[float] = field(default_factory=list)
    y_values: list[float] = field(default_factory=list)
    label: str = ""
    is_valid: bool = True
    error_message: str | None = None


def sample_expression(
    expression: ParsedExpression | str,
    x_min: float = -10.0,
    x_max: float = 10.0,
    num_points: int = 400,
    variable: str = "x",
    label: str = "f(x)",
) -> CurveData:
    """Muestrea una expresión matemática en un rango numérico [x_min, x_max].

    Args:
        expression: Expresión matemática parseada o cadena.
        x_min: Límite inferior del dominio a graficar.
        x_max: Límite superior del dominio a graficar.
        num_points: Cantidad de muestras equidistantes.
        variable: Variable independiente (por defecto 'x').
        label: Nombre representativo para la curva.

    Returns:
        CurveData con listas de coordenadas listas para ser graficadas.
    """
    if x_min >= x_max:
        return CurveData(
            label=label,
            is_valid=False,
            error_message="El valor de x_min debe ser estrictamente menor que x_max.",
        )

    if num_points < 2:
        return CurveData(
            label=label,
            is_valid=False,
            error_message="El número de puntos debe ser al menos 2.",
        )

    if not _SYMPY_AVAILABLE:
        return CurveData(
            label=label,
            is_valid=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        parsed = expression if isinstance(expression, ParsedExpression) else parse_math_expression(expression)
        sym_var = sympy.Symbol(variable)

        # Usar lambdify con el módulo math para evaluación numérica rápida y segura
        f_lambdified = sympy.lambdify(sym_var, parsed.sympy_expr, modules=["math"])

        step = (x_max - x_min) / (num_points - 1)
        xs: list[float] = []
        ys: list[float] = []

        for i in range(num_points):
            x = x_min + i * step
            try:
                val = f_lambdified(x)
                # Convertir a float real si es un número válido
                if isinstance(val, complex):
                    y = float(val.real) if abs(val.imag) < 1e-12 else math.nan
                else:
                    y = float(val)
                # Acotar valores infinitos
                if math.isinf(y):
                    y = math.nan
            except (ZeroDivisionError, ValueError, OverflowError):
                y = math.nan

            xs.append(x)
            ys.append(y)

        return CurveData(
            x_values=xs,
            y_values=ys,
            label=label or parsed.plain_text,
            is_valid=True,
        )
    except Exception as exc:
        return CurveData(
            label=label,
            is_valid=False,
            error_message=str(exc),
        )


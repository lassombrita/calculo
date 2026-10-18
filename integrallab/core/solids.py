"""Módulo de cálculo matemático y modelado geométrico para sólidos de revolución.

Responsabilidad:
1. Representar regiones bidimensionales delimitadas por curvas y límites (en 'x' o 'y').
2. Calcular analítica y numéricamente volúmenes de revolución mediante los métodos de
   Discos, Arandelas y Casquillos cilíndricos, soportando ejes estándar y desplazados.
3. Proveer un motor de recomendación explicable que justifique el método óptimo o
   declare explícitamente limitaciones geométricas (ej. autointersecciones).
4. Generar mallas numéricas tridimensionales (NumPy) para visualización sin acoplar
   la capa gráfica a SymPy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Sequence

import numpy as np

try:
    import sympy
    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False

from integrallab.core.parser import ParsedExpression, parse_math_expression


class AxisOrientation(str, Enum):
    """Orientación espacial del eje de rotación."""

    HORIZONTAL = "horizontal"  # Ejes de la forma y = k
    VERTICAL = "vertical"      # Ejes de la forma x = h


class SolidMethod(str, Enum):
    """Método de integración para sólidos de revolución."""

    DISKS = "Discos"
    WASHERS = "Arandelas"
    SHELLS = "Casquillos cilíndricos"


@dataclass(frozen=True)
class RevolutionAxis:
    """Representa el eje de rotación en el plano cartesiano.

    Atributos:
        orientation: HORIZONTAL (recta y=k) o VERTICAL (recta x=h).
        position: Valor numérico de la coordenada constante (k o h).
    """

    orientation: AxisOrientation
    position: float = 0.0

    @classmethod
    def x_axis(cls) -> RevolutionAxis:
        """Crea el eje X cartesiano estándar (y = 0)."""
        return cls(orientation=AxisOrientation.HORIZONTAL, position=0.0)

    @classmethod
    def y_axis(cls) -> RevolutionAxis:
        """Crea el eje Y cartesiano estándar (x = 0)."""
        return cls(orientation=AxisOrientation.VERTICAL, position=0.0)

    @classmethod
    def horizontal(cls, y_pos: float) -> RevolutionAxis:
        """Crea un eje horizontal desplazado (y = y_pos)."""
        return cls(orientation=AxisOrientation.HORIZONTAL, position=float(y_pos))

    @classmethod
    def vertical(cls, x_pos: float) -> RevolutionAxis:
        """Crea un eje vertical desplazado (x = x_pos)."""
        return cls(orientation=AxisOrientation.VERTICAL, position=float(x_pos))

    @property
    def label(self) -> str:
        """Etiqueta matemática legible del eje (ej. 'y = 0', 'x = 2')."""
        var_name = "y" if self.orientation == AxisOrientation.HORIZONTAL else "x"
        pos_str = f"{self.position:g}"
        return f"{var_name} = {pos_str}"


@dataclass(frozen=True)
class Region2D:
    """Define una región plana acotada entre dos funciones y dos límites.

    Atributos:
        f_expr: Primera función límite (ParsedExpression o str).
        g_expr: Segunda función límite (opcional; por defecto y=0 o x=0).
        a: Límite inferior de integración.
        b: Límite superior de integración.
        variable: Variable independiente ('x' o 'y').
    """

    f_expr: ParsedExpression | str
    g_expr: ParsedExpression | str | None = None
    a: float | int | str = 0.0
    b: float | int | str = 1.0
    variable: str = "x"


@dataclass(frozen=True)
class VolumeResult:
    """Resultado del cálculo de volumen de un sólido de revolución.

    Atributos:
        method: Método empleado (Discos, Arandelas o Casquillos).
        exact_plain_text: Expresión exacta del volumen en texto plano.
        exact_latex: Expresión exacta en formato LaTeX.
        numeric_value: Valor numérico aproximado (float) o None si falla.
        integrand_plain_text: Expresión del integrando en texto plano.
        integrand_latex: Expresión del integrando en LaTeX.
        integral_setup_latex: Expresión completa de la integral planteada en LaTeX.
        is_success: True si el cálculo concluyó sin errores.
        error_message: Detalle del error en caso de fallo.
    """

    method: SolidMethod
    exact_plain_text: str = ""
    exact_latex: str = ""
    numeric_value: float | None = None
    integrand_plain_text: str = ""
    integrand_latex: str = ""
    integral_setup_latex: str = ""
    is_success: bool = True
    error_message: str | None = None


@dataclass(frozen=True)
class MethodRecommendation:
    """Recomendación justificada del método de integración más conveniente.

    Atributos:
        recommended_method: Método aconsejado (o None si no es decidible).
        justification: Explicación pedagógica y geométrica de la recomendación.
        integral_setup: Expresión simbólica de la integral a plantear.
        alternatives: Métodos alternativos viables con notas sobre su complejidad.
        is_decidable: True si la geometría permite formular la integral con certeza.
        limitations_or_warnings: Advertencias detectadas (ej. autointersección).
    """

    recommended_method: SolidMethod | None
    justification: str
    integral_setup: str = ""
    alternatives: list[tuple[SolidMethod, str]] = field(default_factory=list)
    is_decidable: bool = True
    limitations_or_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SolidMesh3D:
    """Estructura de datos puramente numérica para renderizado 3D con Matplotlib.

    Atributos:
        x_outer: Matriz 2D de coordenadas X para la superficie exterior.
        y_outer: Matriz 2D de coordenadas Y para la superficie exterior.
        z_outer: Matriz 2D de coordenadas Z para la superficie exterior.
        x_inner: Matriz 2D de coordenadas X para la superficie interior (o None si es macizo).
        y_inner: Matriz 2D de coordenadas Y para la superficie interior.
        z_inner: Matriz 2D de coordenadas Z para la superficie interior.
        axis: Eje alrededor del cual se generó la revolución.
        is_valid: True si las matrices se generaron correctamente sin errores geométricos.
        error_message: Detalle del error si la generación falló.
    """

    x_outer: np.ndarray
    y_outer: np.ndarray
    z_outer: np.ndarray
    x_inner: np.ndarray | None = None
    y_inner: np.ndarray | None = None
    z_inner: np.ndarray | None = None
    axis: RevolutionAxis = field(default_factory=RevolutionAxis.x_axis)
    is_valid: bool = True
    error_message: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades internas de normalización y análisis geométrico
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_parsed(expr: ParsedExpression | str | None, default_zero: bool = False) -> ParsedExpression:
    """Convierte cadenas o None a ParsedExpression de manera segura."""
    if expr is None:
        if default_zero:
            return parse_math_expression("0")
        raise ValueError("Se esperaba una expresión matemática y se recibió None.")
    if isinstance(expr, ParsedExpression):
        return expr
    return parse_math_expression(str(expr))


def _evaluate_bounds(
    a_in: float | int | str,
    b_in: float | int | str,
) -> tuple[float, float, sympy.Expr, sympy.Expr]:
    """Evalúa los límites de integración a valores numéricos (float) y simbólicos (SymPy)."""
    sym_a = sympy.sympify(a_in)
    sym_b = sympy.sympify(b_in)
    try:
        num_a = float(sym_a.evalf())
        num_b = float(sym_b.evalf())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Los límites [{a_in}, {b_in}] no se pueden evaluar a números reales: {exc}") from exc

    if num_a >= num_b:
        raise ValueError(f"El límite inferior 'a' ({num_a}) debe ser estrictamente menor que 'b' ({num_b}).")

    return num_a, num_b, sym_a, sym_b


def _order_curves_by_distance(
    f_sym: sympy.Expr,
    g_sym: sympy.Expr,
    var_sym: sympy.Symbol,
    axis_val: float,
    num_a: float,
    num_b: float,
) -> tuple[sympy.Expr, sympy.Expr, bool]:
    """Ordena dos curvas en R_outer y R_inner según su distancia al eje de rotación.

    Returns:
        (r_outer_expr, r_inner_expr, has_inner_void)
    """
    # Expresiones de distancia exacta respecto al eje
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)

    # Evaluar en el punto medio del intervalo para determinar la relación de orden
    mid_val = (num_a + num_b) / 2.0
    try:
        val_f = float(dist_f.subs(var_sym, mid_val).evalf())
        val_g = float(dist_g.subs(var_sym, mid_val).evalf())
    except Exception:
        val_f = 1.0
        val_g = 0.0

    if val_f >= val_g:
        r_outer_dist = dist_f
        r_inner_dist = dist_g
    else:
        r_outer_dist = dist_g
        r_inner_dist = dist_f

    # Comprobar si el radio interior es idénticamente cero
    is_inner_zero = r_inner_dist.is_zero or r_inner_dist == 0
    return r_outer_dist, r_inner_dist, not is_inner_zero


# ─────────────────────────────────────────────────────────────────────────────
# Métodos de Cálculo de Volumen
# ─────────────────────────────────────────────────────────────────────────────

def calculate_disk_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
) -> VolumeResult:
    """Calcula el volumen de un sólido de revolución macizo mediante el método de Discos.

    Fórmula:
        V = π ∫_a^b [R(t)]² dt

    Args:
        region: Definición de la región plana y límites.
        axis: Eje de rotación (por defecto el eje X).

    Returns:
        VolumeResult con el valor exacto, decimal y la integral formulada.
    """
    if not _SYMPY_AVAILABLE:
        return VolumeResult(
            method=SolidMethod.DISKS,
            is_success=False,
            error_message="SymPy no está disponible.",
        )

    axis = axis or RevolutionAxis.x_axis()

    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)

        # Para discos perpendiculares:
        # Si la región es en x y el eje es horizontal (y = k): cortes perpendiculares con espesor dx
        # Si la región es en y y el eje es vertical (x = h): cortes perpendiculares con espesor dy
        is_perpendicular = (
            (region.variable == "x" and axis.orientation == AxisOrientation.HORIZONTAL)
            or (region.variable == "y" and axis.orientation == AxisOrientation.VERTICAL)
        )
        if not is_perpendicular:
            return VolumeResult(
                method=SolidMethod.DISKS,
                is_success=False,
                error_message=(
                    f"El método de discos requiere cortes perpendiculares al eje {axis.label}. "
                    f"Para la variable '{region.variable}', considere el método de Casquillos cilíndricos."
                ),
            )

        r_outer, r_inner, has_void = _order_curves_by_distance(
            f_parsed.sympy_expr,
            g_parsed.sympy_expr,
            var_sym,
            axis.position,
            num_a,
            num_b,
        )

        if has_void:
            # Si hay vacío interior, redirigir conceptualmente o calcular como arandela
            integrand = sympy.pi * (r_outer**2 - r_inner**2)
        else:
            integrand = sympy.pi * (r_outer**2)

        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        try:
            num_val = float(vol_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

        return VolumeResult(
            method=SolidMethod.DISKS if not has_void else SolidMethod.WASHERS,
            exact_plain_text=str(vol_sym),
            exact_latex=sympy.latex(vol_sym),
            numeric_value=num_val,
            integrand_plain_text=str(integrand),
            integrand_latex=sympy.latex(integrand),
            integral_setup_latex=f"\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} \\left({sympy.latex(r_outer**2)}\\right) d{region.variable}",
            is_success=True,
        )
    except Exception as exc:
        return VolumeResult(
            method=SolidMethod.DISKS,
            is_success=False,
            error_message=str(exc),
        )


def calculate_washer_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
) -> VolumeResult:
    """Calcula el volumen mediante el método de Arandelas (corte transversal con vacío interior).

    Fórmula:
        V = π ∫_a^b [R_ext(t)² − R_int(t)²] dt

    Args:
        region: Definición de la región plana delimitada por dos funciones y límites.
        axis: Eje de rotación (por defecto el eje X).

    Returns:
        VolumeResult con el volumen exacto, integrando y desarrollo simbólico.
    """
    if not _SYMPY_AVAILABLE:
        return VolumeResult(
            method=SolidMethod.WASHERS,
            is_success=False,
            error_message="SymPy no está disponible.",
        )

    axis = axis or RevolutionAxis.x_axis()

    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)

        is_perpendicular = (
            (region.variable == "x" and axis.orientation == AxisOrientation.HORIZONTAL)
            or (region.variable == "y" and axis.orientation == AxisOrientation.VERTICAL)
        )
        if not is_perpendicular:
            return VolumeResult(
                method=SolidMethod.WASHERS,
                is_success=False,
                error_message=(
                    f"El método de arandelas requiere cortes perpendiculares al eje {axis.label}. "
                    f"Para integrar en '{region.variable}', considere el método de Casquillos."
                ),
            )

        r_outer, r_inner, _ = _order_curves_by_distance(
            f_parsed.sympy_expr,
            g_parsed.sympy_expr,
            var_sym,
            axis.position,
            num_a,
            num_b,
        )

        integrand = sympy.pi * (r_outer**2 - r_inner**2)
        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        try:
            num_val = float(vol_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

        return VolumeResult(
            method=SolidMethod.WASHERS,
            exact_plain_text=str(vol_sym),
            exact_latex=sympy.latex(vol_sym),
            numeric_value=num_val,
            integrand_plain_text=str(integrand),
            integrand_latex=sympy.latex(integrand),
            integral_setup_latex=(
                f"\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} "
                f"\\left[ {sympy.latex(r_outer)}^2 - {sympy.latex(r_inner)}^2 \\right] d{region.variable}"
            ),
            is_success=True,
        )
    except Exception as exc:
        return VolumeResult(
            method=SolidMethod.WASHERS,
            is_success=False,
            error_message=str(exc),
        )


def calculate_shell_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
) -> VolumeResult:
    """Calcula el volumen de un sólido mediante el método de Casquillos Cilíndricos (capas cilíndricas).

    Fórmula:
        V = 2π ∫_a^b [radio(t) · altura(t)] dt

    Args:
        region: Región plana y límites.
        axis: Eje de rotación (por defecto el eje Y).

    Returns:
        VolumeResult con el volumen exacto y la integral formulada.
    """
    if not _SYMPY_AVAILABLE:
        return VolumeResult(
            method=SolidMethod.SHELLS,
            is_success=False,
            error_message="SymPy no está disponible.",
        )

    axis = axis or RevolutionAxis.y_axis()

    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)

        # En casquillos, el espesor diferencial (dt) es PARALELO al eje de rotación:
        # Si variable es x, el corte vertical es paralelo a un eje vertical (x = h).
        # Si variable es y, el corte horizontal es paralelo a un eje horizontal (y = k).
        is_parallel = (
            (region.variable == "x" and axis.orientation == AxisOrientation.VERTICAL)
            or (region.variable == "y" and axis.orientation == AxisOrientation.HORIZONTAL)
        )
        if not is_parallel:
            return VolumeResult(
                method=SolidMethod.SHELLS,
                is_success=False,
                error_message=(
                    f"El método de casquillos requiere que los cortes sean paralelos al eje {axis.label}. "
                    f"Para integrar en '{region.variable}', considere Discos o Arandelas."
                ),
            )

        # Radio del casquillo: distancia desde la variable 't' al eje
        axis_pos_sym = sympy.nsimplify(axis.position)
        radius_expr = sympy.Abs(var_sym - axis_pos_sym)

        # Altura del casquillo: diferencia entre la curva superior y la inferior
        mid_val = (num_a + num_b) / 2.0
        val_f = float(f_parsed.sympy_expr.subs(var_sym, mid_val).evalf())
        val_g = float(g_parsed.sympy_expr.subs(var_sym, mid_val).evalf())

        if val_f >= val_g:
            height_expr = f_parsed.sympy_expr - g_parsed.sympy_expr
        else:
            height_expr = g_parsed.sympy_expr - f_parsed.sympy_expr

        integrand = 2 * sympy.pi * radius_expr * height_expr
        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        try:
            num_val = float(vol_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

        return VolumeResult(
            method=SolidMethod.SHELLS,
            exact_plain_text=str(vol_sym),
            exact_latex=sympy.latex(vol_sym),
            numeric_value=num_val,
            integrand_plain_text=str(integrand),
            integrand_latex=sympy.latex(integrand),
            integral_setup_latex=(
                f"2\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} "
                f"\\left({sympy.latex(radius_expr)}\\right) \\left({sympy.latex(height_expr)}\\right) d{region.variable}"
            ),
            is_success=True,
        )
    except Exception as exc:
        return VolumeResult(
            method=SolidMethod.SHELLS,
            is_success=False,
            error_message=str(exc),
        )


def calculate_revolution_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    method: SolidMethod | None = None,
) -> VolumeResult:
    """Función de alto nivel para calcular el volumen según el método seleccionado o recomendado."""
    axis = axis or RevolutionAxis.x_axis()

    if method is None:
        rec = recommend_method(region, axis)
        if not rec.is_decidable or rec.recommended_method is None:
            return VolumeResult(
                method=SolidMethod.DISKS,
                is_success=False,
                error_message=f"No se pudo determinar un método viable: {'; '.join(rec.limitations_or_warnings)}",
            )
        method = rec.recommended_method

    if method == SolidMethod.DISKS:
        return calculate_disk_volume(region, axis)
    elif method == SolidMethod.WASHERS:
        return calculate_washer_volume(region, axis)
    elif method == SolidMethod.SHELLS:
        return calculate_shell_volume(region, axis)
    else:
        return VolumeResult(
            method=SolidMethod.DISKS,
            is_success=False,
            error_message=f"Método desconocido: {method}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Motor de Recomendación Explicable
# ─────────────────────────────────────────────────────────────────────────────

def recommend_method(
    region: Region2D,
    axis: RevolutionAxis,
) -> MethodRecommendation:
    """Analiza la geometría de la región y el eje para recomendar el método más adecuado.

    Evalúa:
    1. Si los cortes en la variable dada son perpendiculares (Discos/Arandelas) o paralelos (Casquillos).
    2. Si el sólido tiene sección maciza o corona circular.
    3. Si el eje corta el interior de la región (autointersección no permitida).
    """
    if not _SYMPY_AVAILABLE:
        return MethodRecommendation(
            recommended_method=None,
            justification="SymPy no está disponible para evaluar la geometría.",
            is_decidable=False,
            limitations_or_warnings=["Motor matemático SymPy ausente."],
        )

    warnings: list[str] = []

    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)
    except Exception as exc:
        return MethodRecommendation(
            recommended_method=None,
            justification=f"Definición inválida de la región: {exc}",
            is_decidable=False,
            limitations_or_warnings=[str(exc)],
        )

    # 1. Comprobar si el eje intersecta el interior de la región
    mid_t = (num_a + num_b) / 2.0
    val_f_mid = float(f_parsed.sympy_expr.subs(var_sym, mid_t).evalf())
    val_g_mid = float(g_parsed.sympy_expr.subs(var_sym, mid_t).evalf())
    top_mid = max(val_f_mid, val_g_mid)
    bot_mid = min(val_f_mid, val_g_mid)

    if region.variable == "x":
        if axis.orientation == AxisOrientation.HORIZONTAL:
            # Eje horizontal y = k vs región vertical en y
            if bot_mid < axis.position < top_mid:
                warnings.append(
                    f"El eje {axis.label} atraviesa el interior de la región entre y={bot_mid:.2f} y y={top_mid:.2f}, "
                    "lo cual provocaría autointersecciones."
                )
        else:
            # Eje vertical x = h vs límites en x
            if num_a < axis.position < num_b:
                warnings.append(
                    f"El eje {axis.label} atraviesa el interior del intervalo de integración x ∈ [{num_a}, {num_b}]."
                )

    if warnings:
        return MethodRecommendation(
            recommended_method=None,
            justification="No se puede recomendar un método con el eje dentro de la región.",
            is_decidable=False,
            limitations_or_warnings=warnings,
        )

    # 2. Determinar método natural según paralelismo/perpendicularidad
    # Cortes diferenciales perpendiculares al eje -> Discos o Arandelas
    is_perpendicular = (
        (region.variable == "x" and axis.orientation == AxisOrientation.HORIZONTAL)
        or (region.variable == "y" and axis.orientation == AxisOrientation.VERTICAL)
    )

    if is_perpendicular:
        # Comprobar si hay vacío interior
        _, _, has_void = _order_curves_by_distance(
            f_parsed.sympy_expr,
            g_parsed.sympy_expr,
            var_sym,
            axis.position,
            num_a,
            num_b,
        )
        if not has_void:
            return MethodRecommendation(
                recommended_method=SolidMethod.DISKS,
                justification=(
                    f"Los cortes perpendiculares al eje {axis.label} con respecto a d{region.variable} forman discos macizos "
                    "sin espacio vacío interior respecto al eje de rotación."
                ),
                integral_setup=f"V = π ∫ R({region.variable})² d{region.variable}",
                alternatives=[(SolidMethod.SHELLS, f"Requeriría despejar la función inversa en la otra variable.")],
                is_decidable=True,
            )
        else:
            return MethodRecommendation(
                recommended_method=SolidMethod.WASHERS,
                justification=(
                    f"Los cortes perpendiculares al eje {axis.label} con respecto a d{region.variable} generan secciones "
                    "con radio exterior y radio interior (corona circular o arandela)."
                ),
                integral_setup=f"V = π ∫ [R_ext({region.variable})² - R_int({region.variable})²] d{region.variable}",
                alternatives=[(SolidMethod.SHELLS, f"Requeriría despejar la función inversa en la otra variable.")],
                is_decidable=True,
            )
    else:
        # Cortes diferenciales paralelos al eje -> Casquillos cilíndricos
        return MethodRecommendation(
            recommended_method=SolidMethod.SHELLS,
            justification=(
                f"Los cortes en la variable d{region.variable} son paralelos al eje {axis.label}. "
                "El método de casquillos cilíndricos evita tener que invertir algebraicamente las funciones."
            ),
            integral_setup=f"V = 2π ∫ radio({region.variable}) · altura({region.variable}) d{region.variable}",
            alternatives=[
                (SolidMethod.WASHERS, "Requeriría expresar la región en la variable perpendicular invirtiendo f y g.")
            ],
            is_decidable=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Generación de Malla 3D para Visualización (NumPy puro)
# ─────────────────────────────────────────────────────────────────────────────

def generate_solid_mesh(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    num_radial: int = 36,
    num_axial: int = 40,
) -> SolidMesh3D:
    """Genera matrices numéricas (X, Y, Z) en NumPy para renderizar el sólido en 3D.

    Parametriza la superficie de revolución de manera exacta:
    - Rotación en eje horizontal (y = k):
        X = t
        Y = k + R(t) · cos(θ)
        Z = R(t) · sin(θ)
    - Rotación en eje vertical (x = h):
        X = h + R(t) · cos(θ)
        Y = y(t)
        Z = R(t) · sin(θ)

    Args:
        region: Región plana a revolucionar.
        axis: Eje de giro (horizontal o vertical, estándar o desplazado).
        num_radial: Número de subdivisiones angulares en [0, 2π].
        num_axial: Número de subdivisiones en el intervalo [a, b].

    Returns:
        SolidMesh3D con matrices numéricas para superficies exterior e interior.
    """
    axis = axis or RevolutionAxis.x_axis()

    if num_radial < 8 or num_axial < 2:
        return SolidMesh3D(
            x_outer=np.empty((0, 0)),
            y_outer=np.empty((0, 0)),
            z_outer=np.empty((0, 0)),
            is_valid=False,
            error_message="Dimensiones de malla insuficientes (mínimo 8 radiales y 2 axiales).",
        )

    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)

        # Muestrear el intervalo axial [a, b] y el ángulo angular [0, 2π]
        t_vals = np.linspace(num_a, num_b, num_axial)
        theta_vals = np.linspace(0, 2 * np.pi, num_radial)
        T_grid, Theta_grid = np.meshgrid(t_vals, theta_vals, indexing="ij")

        # Lambdificar funciones a NumPy/math para evaluación vectorial rápida
        f_lamb = sympy.lambdify(var_sym, f_parsed.sympy_expr, modules=["numpy", "math"])
        g_lamb = sympy.lambdify(var_sym, g_parsed.sympy_expr, modules=["numpy", "math"])

        # Evaluar valores de las funciones sobre el eje t
        f_vals = np.array([float(f_lamb(t)) if np.isreal(f_lamb(t)) else np.nan for t in t_vals])
        g_vals = np.array([float(g_lamb(t)) if np.isreal(g_lamb(t)) else np.nan for t in t_vals])

        if axis.orientation == AxisOrientation.HORIZONTAL:
            # Eje horizontal y = k
            dist_f = np.abs(f_vals - axis.position)
            dist_g = np.abs(g_vals - axis.position)

            r_outer_1d = np.maximum(dist_f, dist_g)
            r_inner_1d = np.minimum(dist_f, dist_g)

            # Expandir a rejilla 2D (num_axial, num_radial)
            R_outer = np.repeat(r_outer_1d[:, np.newaxis], num_radial, axis=1)
            R_inner = np.repeat(r_inner_1d[:, np.newaxis], num_radial, axis=1)

            # Parametrización en eje horizontal
            X_out = T_grid
            Y_out = axis.position + R_outer * np.cos(Theta_grid)
            Z_out = R_outer * np.sin(Theta_grid)

            # Superficie interior si existe hueco significativo
            has_inner = bool(np.any(r_inner_1d > 1e-6))
            if has_inner:
                X_in = T_grid
                Y_in = axis.position + R_inner * np.cos(Theta_grid)
                Z_in = R_inner * np.sin(Theta_grid)
            else:
                X_in = Y_in = Z_in = None

        else:
            # Eje vertical x = h
            # En rotación sobre x = h con variable x:
            # El radio horizontal respecto al eje es |x - h|
            r_axial = np.abs(t_vals - axis.position)
            R_grid = np.repeat(r_axial[:, np.newaxis], num_radial, axis=1)

            # Superficie exterior: generada por la curva superior
            y_top_1d = np.maximum(f_vals, g_vals)
            y_bot_1d = np.minimum(f_vals, g_vals)

            Y_out = np.repeat(y_top_1d[:, np.newaxis], num_radial, axis=1)
            X_out = axis.position + R_grid * np.cos(Theta_grid)
            Z_out = R_grid * np.sin(Theta_grid)

            # Superficie inferior / interior generada por la curva inferior
            has_inner = bool(np.any(np.abs(y_top_1d - y_bot_1d) > 1e-6))
            if has_inner:
                Y_in = np.repeat(y_bot_1d[:, np.newaxis], num_radial, axis=1)
                X_in = axis.position + R_grid * np.cos(Theta_grid)
                Z_in = R_grid * np.sin(Theta_grid)
            else:
                X_in = Y_in = Z_in = None

        return SolidMesh3D(
            x_outer=X_out,
            y_outer=Y_out,
            z_outer=Z_out,
            x_inner=X_in,
            y_inner=Y_in,
            z_inner=Z_in,
            axis=axis,
            is_valid=True,
        )
    except Exception as exc:
        return SolidMesh3D(
            x_outer=np.empty((0, 0)),
            y_outer=np.empty((0, 0)),
            z_outer=np.empty((0, 0)),
            axis=axis,
            is_valid=False,
            error_message=str(exc),
        )

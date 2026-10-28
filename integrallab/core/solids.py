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

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence

import numpy as np

try:
    import sympy
    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False

from integrallab.core.adaptive import equidistributed_nodes
from integrallab.core.parser import ParsedExpression, parse_math_expression
from integrallab.core.sampling import REAL_EVAL_MODULES, prepare_expr_for_real_eval
from integrallab.core.steps import (
    IdGenerator,
    RadiusInfo,
    StepNode,
    antiderivative,
    build_volume_tree,
    describe_technique,
)
from integrallab.core.steps import Piece as StepPiece
from integrallab.core.steps import latex as step_latex
from integrallab.core.volume.inversion import InversionFailed, Strip, horizontal_strips
from integrallab.core.volume.pieces import real_branch, real_root_form, sign_cut_points, sign_on

logger = logging.getLogger(__name__)


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
class SolutionStep:
    """Representa un paso intermedio en la resolución analítica de la integral.

    Atributos:
        step_number: Número secuencial del paso (1, 2, ...).
        title: Título descriptivo del paso (ej. 'Planteamiento del radio').
        explanation: Explicación pedagógica de la operación realizada.
        expression_plain_text: Expresión matemática en texto plano legible.
        expression_latex: Expresión en notación LaTeX (opcional).
    """

    step_number: int
    title: str
    explanation: str
    expression_plain_text: str = ""
    expression_latex: str = ""


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
        steps: Lista ordenada de pasos analíticos de resolución (vista imprimible).
        warnings: Advertencias sobre cruces de curvas que pueden afectar el resultado.
        step_tree: Árbol del desglose interactivo (``integrallab.core.steps``); ``None`` si no
            se pudo construir. Cada fórmula marca con ``\\class{step-ID}`` las partes clicables.
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
    steps: list[SolutionStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    step_tree: StepNode | None = None


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
    """Evalúa los límites de integración a valores numéricos (float) y simbólicos (SymPy).

    Raises:
        ValueError: Si los límites son nan, inf o si a >= b.
    """
    import math as _math
    from integrallab.core.parser import parse_numeric_or_symbolic

    try:
        sym_a = parse_numeric_or_symbolic(a_in)
        sym_b = parse_numeric_or_symbolic(b_in)
    except Exception as exc:
        raise ValueError(f"Los límites no son expresiones válidas: {exc}") from exc
    try:
        num_a = float(sym_a.evalf())
        num_b = float(sym_b.evalf())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Los límites [{a_in}, {b_in}] no se pueden evaluar a números reales: {exc}") from exc

    if not (_math.isfinite(num_a) and _math.isfinite(num_b)):
        raise ValueError(
            f"Los límites de integración deben ser finitos. Obtenido: [{num_a}, {num_b}]."
        )

    if num_a >= num_b:
        raise ValueError(f"El límite inferior 'a' ({num_a}) debe ser estrictamente menor que 'b' ({num_b}).")

    return num_a, num_b, sym_a, sym_b


class InversionError(ValueError):
    """Excepción lanzada cuando una curva o región no puede invertirse analíticamente."""


def invert_symbolic_expression(
    expr: sympy.Expr,
    from_var: sympy.Symbol,
    to_var: sympy.Symbol,
    a_num: float,
    b_num: float,
) -> sympy.Expr:
    """Despeja analíticamente from_var en función de to_var seleccionando la rama en [a_num, b_num].

    Raises:
        InversionError: Si SymPy no puede despejar analíticamente la expresión.
    """
    if not _SYMPY_AVAILABLE:
        raise InversionError("SymPy no está disponible.")

    if from_var not in expr.free_symbols:
        return expr

    try:
        eq = sympy.Eq(to_var, expr)
        sols = sympy.solve(eq, from_var)
    except Exception as exc:
        raise InversionError(f"No fue posible resolver {to_var} = {expr} para {from_var}: {exc}") from exc

    if not sols:
        raise InversionError(f"No se encontraron soluciones analíticas para {to_var} = {expr} respecto a {from_var}.")

    if len(sols) == 1:
        return sols[0]

    mid_x = (a_num + b_num) / 2.0
    try:
        mid_y = float(expr.subs(from_var, mid_x).evalf())
    except Exception:
        return sols[0]

    best_sol = None
    min_dist = float("inf")
    for sol in sols:
        try:
            val = float(sol.subs(to_var, mid_y).evalf())
            dist = abs(val - mid_x)
            if dist < min_dist:
                min_dist = dist
                best_sol = sol
        except Exception:
            continue

    return best_sol if best_sol is not None else sols[0]


def inversion_is_cheap(region: Region2D) -> bool:
    """True si invertir la región es barato: f y g polinomios de grado ≤ 4 en la variable."""
    try:
        var_sym = sympy.Symbol(region.variable)
        for expr in (region.f_expr, region.g_expr):
            parsed = _ensure_parsed(expr, default_zero=True)
            poly = sympy.Poly(parsed.sympy_expr, var_sym)
            if poly.degree() > 4 or len(poly.free_symbols - {var_sym}) > 0:
                return False
        return True
    except Exception:  # noqa: BLE001 - no polinómica
        return False


def can_invert_for_method(
    region: Region2D,
    axis: RevolutionAxis,
    method: SolidMethod,
) -> bool:
    """True si el método se aplica directamente o si la región se puede describir por franjas
    horizontales con despejes exactos (ver ``integrallab.core.volume.inversion``)."""
    if is_method_compatible(method, axis, region.variable):
        return True
    if region.variable != "x":
        return False
    try:
        f = _ensure_parsed(region.f_expr).sympy_expr
        g = _ensure_parsed(region.g_expr, default_zero=True).sympy_expr
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)
        x_sym = sympy.Symbol("x")
        crossings = find_curve_crossings(f, g, x_sym, 0.0, num_a, num_b, method=SolidMethod.SHELLS)
        horizontal_strips(f, g, x_sym, sympy.Symbol("y"), num_a, num_b, sym_a, sym_b, crossings)
        return True
    except Exception:  # noqa: BLE001 - cualquier fallo significa «no invertible»
        return False


def _evaluate_profile(func: Callable[[float], object], ts: np.ndarray) -> np.ndarray:
    """Evalúa una curva de contorno punto a punto; nan donde no es real o no está definida."""
    out = np.full(ts.size, np.nan)
    for i, t in enumerate(ts):
        try:
            value = func(float(t))
            if np.isreal(value):
                out[i] = float(np.real(value))
        except (ArithmeticError, ValueError, TypeError):
            continue
    return out


_CROSSING_EPS = 1e-6


def _interior_real_roots(
    solutions: object,
    num_a: float,
    num_b: float,
    eps: float = _CROSSING_EPS,
) -> list[float]:
    """Convierte las soluciones de ``sympy.solve`` en raíces reales estrictamente interiores.

    Acepta soluciones racionales, decimales e irracionales (p. ej. ``sqrt(2)``, ``pi/4``) y
    descarta las complejas, las no numéricas y las que caen en los extremos de ``[a, b]``,
    donde un cruce no divide la región. Elimina duplicados numéricos.
    """
    if not isinstance(solutions, (list, tuple, set)):
        solutions = [solutions]
    roots: list[float] = []
    for sol in solutions:
        try:
            value = complex(sympy.sympify(sol).evalf())
        except (TypeError, ValueError, ArithmeticError):
            continue
        if abs(value.imag) >= 1e-9:
            continue
        real = float(value.real)
        if num_a + eps < real < num_b - eps and not any(abs(real - r) < 1e-5 for r in roots):
            roots.append(real)
    return sorted(roots)


# ─────────────────────────────────────────────────────────────────────────────
# Barrido numérico previo a sympy.solve (evita bloqueos de decenas de segundos)
# ─────────────────────────────────────────────────────────────────────────────

_SCAN_SAMPLES = 2001
_SCAN_EDGE_SKIP = 10       # muestras junto a cada extremo que no cuentan como "casi cero"
_SCAN_NEAR_ZERO = 1e-6     # |h| relativo por debajo del cual se sospecha una tangencia


def _has_piecewise(*exprs: object) -> bool:
    """True si alguna expresión contiene ``Piecewise`` (p. ej. un spline cúbico)."""
    return any(isinstance(e, sympy.Basic) and e.has(sympy.Piecewise) for e in exprs)


def _scan_interior_roots(
    expr: sympy.Expr,
    var_sym: sympy.Symbol,
    num_a: float,
    num_b: float,
) -> tuple[str, list[float]]:
    """Barre ``expr`` en (a, b) con NumPy y clasifica sus raíces interiores.

    Returns:
        ``("none", [])`` si no hay cambio de signo y ``|expr|`` se mantiene lejos de cero en el
        interior: no existe cruce y no hace falta ``sympy.solve``.
        ``("roots", raíces)`` con las raíces de cada cambio de signo, refinadas por bisección.
        ``("unknown", raíces)`` si no se pudo evaluar o hay un mínimo casi nulo (posible
        tangencia): quien llama debe usar el método simbólico de siempre.
    """
    if not num_a < num_b:
        return "unknown", []
    ts = np.linspace(num_a, num_b, _SCAN_SAMPLES)
    hs = _sample_profile(expr, var_sym, ts)
    if hs is None or hs.shape != ts.shape or not np.all(np.isfinite(hs)):
        return "unknown", []

    try:
        real_expr = prepare_expr_for_real_eval(expr)
        fn = sympy.lambdify(var_sym, real_expr, modules=REAL_EVAL_MODULES)
    except Exception:
        return "unknown", []

    def h(t: float) -> float:
        with np.errstate(all="ignore"):
            v = complex(fn(t))
        return v.real if abs(v.imag) < 1e-12 else float("nan")

    roots: list[float] = []
    eps = _CROSSING_EPS
    sign = np.sign(hs)
    for i in np.flatnonzero(sign[:-1] * sign[1:] < 0):
        lo, hi = float(ts[i]), float(ts[i + 1])
        h_lo = hs[i]
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            h_mid = h(mid)
            if not np.isfinite(h_mid):
                break
            if (h_mid < 0) == (h_lo < 0):
                lo, h_lo = mid, h_mid
            else:
                hi = mid
        root = 0.5 * (lo + hi)
        if num_a + eps < root < num_b - eps:
            roots.append(root)
    # Ceros exactos en muestras interiores
    for i in np.flatnonzero(hs[1:-1] == 0.0) + 1:
        t = float(ts[i])
        if num_a + eps < t < num_b - eps and not any(abs(t - r) < 1e-9 for r in roots):
            roots.append(t)
    roots.sort()

    scale = max(1.0, float(np.max(np.abs(hs))))
    inner = np.abs(hs[_SCAN_EDGE_SKIP:-_SCAN_EDGE_SKIP])
    near_zero = inner.size > 0 and float(np.min(inner)) < _SCAN_NEAR_ZERO * scale
    if roots:
        return ("unknown" if near_zero else "roots"), roots
    return ("unknown" if near_zero else "none"), []


def _dominates(
    hi_expr: sympy.Expr,
    lo_expr: sympy.Expr,
    var_sym: sympy.Symbol,
    t0: float,
    t1: float,
) -> bool:
    """True si ``hi_expr >= lo_expr`` en (t0, t1), decidido con 9 muestras interiores.

    Sustituye la evaluación en el punto medio, que fallaba con singularidades evitables:
    sin(x)/x en [-1, 1] vale nan en x = 0, la comparación ``nan >= 0`` es False y las curvas
    se invertían (volumen −5,638 en lugar de +5,638).
    """
    ts = np.linspace(t0, t1, 11)[1:-1]
    hi_vals = _sample_profile(hi_expr, var_sym, ts)
    lo_vals = _sample_profile(lo_expr, var_sym, ts)
    if hi_vals is not None and lo_vals is not None:
        diff = hi_vals - lo_vals
        diff = diff[np.isfinite(diff)]
        if diff.size:
            return float(np.median(diff)) >= 0.0
    try:
        mid = (t0 + t1) / 2.0
        return float(hi_expr.subs(var_sym, mid).evalf()) >= float(lo_expr.subs(var_sym, mid).evalf())
    except Exception:  # noqa: BLE001
        return True


_SIGN_SAMPLES = 201


def _signed_distance(
    diff_expr: sympy.Expr,
    var_sym: sympy.Symbol,
    t0: float,
    t1: float,
) -> sympy.Expr:
    """Distancia |diff_expr| escrita sin valor absoluto cuando el signo es constante en (t0, t1).

    El eje nunca atraviesa la región (lo garantiza ``axis_crossing_error``), así que en la
    mayoría de los ejercicios ``f − k`` y ``x − h`` conservan su signo: se devuelve ``diff_expr``
    o ``−diff_expr``. Solo si el signo cambia dentro del tramo (p. ej. x³ en [−1, 1] sobre el
    eje X) se conserva ``Abs``, porque entonces el valor absoluto forma parte del radio real.
    """
    if diff_expr == 0:
        return sympy.Integer(0)
    ts = np.linspace(t0, t1, _SIGN_SAMPLES)[1:-1]
    vals = _sample_profile(diff_expr, var_sym, ts)
    if vals is not None:
        vals = vals[np.isfinite(vals)]
        if vals.size:
            scale = max(1.0, float(np.max(np.abs(vals))))
            tol = 1e-12 * scale
            if np.all(vals >= -tol):
                return diff_expr
            if np.all(vals <= tol):
                return -diff_expr  # SymPy reparte el −1: −(x − 2) se escribe 2 − x
    return sympy.Abs(diff_expr)


def _first_non_real(expr: sympy.Expr, var_sym: sympy.Symbol, num_a: float, num_b: float) -> float | None:
    """Abscisa interior donde ``expr`` deja de ser real en un tramo (≥ 3 muestras seguidas).

    Un punto aislado (singularidad evitable como sin(x)/x en 0) o un extremo (log x en 0) no
    cuentan; sqrt(x) en [-1, 1] o asin(x) en [0, 2] sí. Devuelve None si no hay problema.
    """
    ts = np.linspace(num_a, num_b, _SCAN_SAMPLES)
    vals = _sample_profile(expr, var_sym, ts)
    if vals is None:
        return None
    bad = np.isnan(vals[1:-1])
    run = 0
    for i, flag in enumerate(bad, start=1):
        run = run + 1 if flag else 0
        if run >= 3:
            return float(ts[i - 1])
    return None


def domain_error(region: Region2D) -> str | None:
    """Mensaje si f o g no son reales en parte de [a, b]; None si la región es válida."""
    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)
    except Exception:  # noqa: BLE001 - el error de límites lo informa otro paso
        return None
    var_sym = sympy.Symbol(region.variable)
    for name, parsed in (("f", f_parsed), ("g", g_parsed)):
        where = _first_non_real(parsed.sympy_expr, var_sym, num_a, num_b)
        if where is not None:
            return (
                f"{name}({region.variable}) = {parsed.plain_text} no está definida o no es real en parte "
                f"del intervalo [{num_a:.4g}, {num_b:.4g}] (por ejemplo, en {region.variable} ≈ {where:.4g}). "
                "Ajuste los límites al dominio de la función."
            )
    return None


def _numeric_value(expr: object) -> float | None:
    """Valor real de un resultado de SymPy; las integrales sin resolver se calculan por cuadratura.

    ``float(Integral(...).evalf())`` fallaba con integrales no elementales (x**x: «No
    disponible») y con funciones escalón (floor: error interno de SymPy). Se usa mpmath en 16
    subintervalos. Devuelve None si el resultado es complejo o no numérico.
    """
    import mpmath

    def quad(integral: sympy.Integral) -> sympy.Expr:
        if len(integral.limits) != 1 or len(integral.limits[0]) != 3:
            return integral
        var, lo, hi = integral.limits[0]
        fn = sympy.lambdify(var, integral.function, modules="mpmath")
        return sympy.Float(mpmath.quad(fn, mpmath.linspace(float(lo), float(hi), 17)))

    try:
        if isinstance(expr, sympy.Basic) and expr.has(sympy.Integral):
            expr = expr.replace(lambda e: isinstance(e, sympy.Integral), quad)
        value = complex(sympy.sympify(expr).evalf())
    except Exception:  # noqa: BLE001
        return None
    if abs(value.imag) > 1e-9 * max(1.0, abs(value.real)):
        return None
    return value.real


def _solve_interior_roots(
    expr: sympy.Expr,
    var_sym: sympy.Symbol,
    num_a: float,
    num_b: float,
    pieces: tuple[object, ...],
) -> list[float]:
    """Raíces reales interiores de ``expr = 0`` evitando ``sympy.solve`` cuando sobra.

    - Si el barrido numérico prueba que no hay raíces interiores, devuelve ``[]`` sin resolver.
    - Si las curvas contienen ``Piecewise`` (spline), usa las raíces numéricas: ``sympy.solve``
      sobre un ``Piecewise`` puede no terminar.
    - En cualquier otro caso usa ``sympy.solve`` exactamente como antes.
    """
    status, approx = _scan_interior_roots(expr, var_sym, num_a, num_b)
    if status == "none":
        return []
    if _has_piecewise(*pieces):
        return approx
    try:
        roots = _interior_real_roots(sympy.solve(sympy.Eq(expr, 0), var_sym), num_a, num_b)
    except Exception:  # noqa: BLE001 - p. ej. NotImplementedError con Max/Min
        return approx
    return roots or approx


def find_curve_crossings(
    f_sym: sympy.Expr,
    g_sym: sympy.Expr,
    var_sym: sympy.Symbol,
    axis_val: float,
    num_a: float,
    num_b: float,
    method: SolidMethod = SolidMethod.WASHERS,
) -> list[tuple[float, sympy.Expr]]:
    """Encuentra las intersecciones reales estrictamente interiores en (num_a, num_b)."""
    candidates = []
    numeric_fallback: list[float] = []

    def _collect(expr: sympy.Expr) -> None:
        """Agrega las raíces de ``expr = 0``; el barrido numérico evita resolver si no hay cruce."""
        status, approx = _scan_interior_roots(expr, var_sym, num_a, num_b)
        if status == "none":
            return  # sin raíces interiores: el resultado es idéntico al de sympy.solve
        if _has_piecewise(f_sym, g_sym):
            candidates.extend(sympy.Float(r) for r in approx)
            return
        numeric_fallback.extend(approx)
        sols = sympy.solve(sympy.Eq(expr, 0), var_sym)  # puede lanzar (Max, Min, Abs…)
        if isinstance(sols, (list, tuple, set)):
            for s in sols:
                candidates.append(sympy.sympify(s))
        elif sols is not None:
            candidates.append(sympy.sympify(sols))

    # 1. f(t) = g(t)
    try:
        _collect(f_sym - g_sym)
    except Exception:
        pass

    # 2. f(t) + g(t) = 2*axis (arandelas con eje != 0)
    if method == SolidMethod.WASHERS and axis_val != 0:
        axis_sym = sympy.nsimplify(axis_val)
        try:
            _collect(f_sym + g_sym - 2 * axis_sym)
        except Exception:
            pass

    eps = 1e-6
    crossings: list[tuple[float, sympy.Expr]] = []
    for c in candidates:
        try:
            c_val = complex(c.evalf())
            if abs(c_val.imag) < 1e-9:
                val = float(c_val.real)
                if num_a + eps < val < num_b - eps:
                    if not any(abs(val - existing[0]) < 1e-5 for existing in crossings):
                        c_simp = sympy.nsimplify(val) if abs(val - round(val)) < 1e-6 else c
                        crossings.append((val, c_simp))
        except Exception:
            pass

    if not crossings and numeric_fallback:
        # sympy.solve no pudo (NotImplementedError con Max/Min) pero el barrido sí vio cruces:
        # sin esto se integraba con una sola orientación y el volumen salía negativo.
        for val in sorted(numeric_fallback):
            if num_a + eps < val < num_b - eps and not any(abs(val - c[0]) < 1e-5 for c in crossings):
                crossings.append((val, sympy.Float(val)))

    crossings.sort(key=lambda item: item[0])
    return crossings


# ─────────────────────────────────────────────────────────────────────────────
# Tramos del volumen: radios con signo resuelto, sin Abs ni ramas complejas
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _VolumePiece:
    """Un tramo ``∫_{t0}^{t1} core d(var)`` (sin el factor π o 2π) y cómo se explica."""

    t0_num: float
    t1_num: float
    t0: sympy.Expr
    t1: sympy.Expr
    core: sympy.Expr
    radii: tuple[RadiusInfo, ...]
    setup: str            # integrando en LaTeX con marcadores @nombre@ para cada radio
    label: str = ""
    is_disk: bool = False


def _fill_setup(setup: str, radii: Sequence[RadiusInfo]) -> str:
    """Reemplaza los marcadores @nombre@ por el LaTeX de cada radio."""
    for info in radii:
        setup = setup.replace(f"@{info.name}@", step_latex(info.expr))
    return setup


def _merge_cuts(*groups: list[tuple[float, sympy.Expr, str]]) -> list[tuple[float, sympy.Expr, str]]:
    merged: list[tuple[float, sympy.Expr, str]] = []
    for item in sorted((c for g in groups for c in g), key=lambda c: c[0]):
        if merged and abs(item[0] - merged[-1][0]) < 1e-7:
            continue
        merged.append(item)
    return merged


def _bounds(
    num_a: float, num_b: float, sym_a: sympy.Expr, sym_b: sympy.Expr,
    cuts: list[tuple[float, sympy.Expr, str]],
) -> list[tuple[tuple[float, sympy.Expr], tuple[float, sympy.Expr]]]:
    points = [(num_a, sym_a), *((c[0], c[1]) for c in cuts), (num_b, sym_b)]
    return list(zip(points, points[1:]))


def _same_piece(p: _VolumePiece, q: _VolumePiece) -> bool:
    return p.radii == q.radii and p.setup == q.setup and abs(p.t1_num - q.t0_num) < 1e-12


def _join_pieces(pieces: list[_VolumePiece]) -> list[_VolumePiece]:
    """Une tramos contiguos con los mismos radios (un corte que al final no cambió nada)."""
    out: list[_VolumePiece] = []
    for piece in pieces:
        if out and _same_piece(out[-1], piece):
            prev = out[-1]
            out[-1] = _VolumePiece(prev.t0_num, piece.t1_num, prev.t0, piece.t1, prev.core, prev.radii,
                                   prev.setup, prev.label, prev.is_disk)
        else:
            out.append(piece)
    return out


def _washer_pieces(
    f: sympy.Expr, g: sympy.Expr, var_sym: sympy.Symbol, axis: RevolutionAxis,
    num_a: float, num_b: float, sym_a: sympy.Expr, sym_b: sympy.Expr,
) -> tuple[list[_VolumePiece], list[tuple[float, sympy.Expr, str]]]:
    """Tramos de Discos/Arandelas con eje horizontal y = k (cortes en x) o vertical x = h (en y)."""
    k = sympy.nsimplify(axis.position)
    v = var_sym.name
    crossings = [(n, s, "las curvas f y g se cruzan") for n, s in
                 find_curve_crossings(f, g, var_sym, axis.position, num_a, num_b, method=SolidMethod.SHELLS)]
    equal = [(n, s, "f y g quedan a la misma distancia del eje") for n, s in
             find_curve_crossings(f, g, var_sym, axis.position, num_a, num_b, method=SolidMethod.WASHERS)
             if not any(abs(n - c[0]) < 1e-7 for c in crossings)]
    signs = [(n, s, "una distancia al eje, un valor absoluto o una raíz impar cambia de signo") for n, s in
             sign_cut_points((f, g), var_sym, num_a, num_b, extra=(f - k, g - k))]
    cuts = _merge_cuts(crossings, equal, signs)
    pieces: list[_VolumePiece] = []
    for (t0n, t0), (t1n, t1) in _bounds(num_a, num_b, sym_a, sym_b, cuts):
        fp, gp = real_branch(f, var_sym, t0n, t1n), real_branch(g, var_sym, t0n, t1n)
        df = _signed_distance(fp - k, var_sym, t0n, t1n)
        dg = _signed_distance(gp - k, var_sym, t0n, t1n)
        f_out = _dominates(df, dg, var_sym, t0n, t1n)
        R, r = (df, dg) if f_out else (dg, df)
        outer, inner = ("f", "g") if f_out else ("g", "f")
        R_info = RadiusInfo(
            f"R({v})", sympy.simplify(R) if R.count_ops() < 30 else R,
            f"Radio exterior: distancia de la curva {outer} al eje {axis.label}. Se escribe "
            f"{'curva − eje' if _sign_of(fp - k if f_out else gp - k, var_sym, t0n, t1n) >= 0 else 'eje − curva'} "
            "para que sea positiva en todo el tramo.",
        )
        if r == 0:
            pieces.append(_VolumePiece(t0n, t1n, t0, t1, R**2, (R_info,), rf"\left[@R({v})@\right]^2",
                                       is_disk=True))
            continue
        r_info = RadiusInfo(
            f"r({v})", sympy.simplify(r) if r.count_ops() < 30 else r,
            f"Radio interior: distancia de la curva {inner} al eje {axis.label} (la más cercana).",
        )
        pieces.append(_VolumePiece(t0n, t1n, t0, t1, R**2 - r**2, (R_info, r_info),
                                   rf"\left(\left[@R({v})@\right]^2 - \left[@r({v})@\right]^2\right)"))
    return _join_pieces(pieces), cuts


def _sign_of(expr: sympy.Expr, var_sym: sympy.Symbol, t0: float, t1: float) -> int:
    s = sign_on(expr, var_sym, t0, t1)
    return 1 if s is None else s


def _shell_pieces(
    f: sympy.Expr, g: sympy.Expr, var_sym: sympy.Symbol, axis: RevolutionAxis,
    num_a: float, num_b: float, sym_a: sympy.Expr, sym_b: sympy.Expr,
) -> tuple[list[_VolumePiece], list[tuple[float, sympy.Expr, str]]]:
    """Tramos de Casquillos: radio p = ±(t − h) y altura h = curva de arriba − curva de abajo."""
    h_sym = sympy.nsimplify(axis.position)
    v = var_sym.name
    crossings = [(n, s, "las curvas f y g se cruzan") for n, s in
                 find_curve_crossings(f, g, var_sym, axis.position, num_a, num_b, method=SolidMethod.SHELLS)]
    signs = [(n, s, "un valor absoluto o una raíz impar cambia de signo") for n, s in
             sign_cut_points((f, g), var_sym, num_a, num_b)]
    cuts = _merge_cuts(crossings, signs)
    pieces: list[_VolumePiece] = []
    for (t0n, t0), (t1n, t1) in _bounds(num_a, num_b, sym_a, sym_b, cuts):
        fp, gp = real_branch(f, var_sym, t0n, t1n), real_branch(g, var_sym, t0n, t1n)
        side = 1 if 0.5 * (t0n + t1n) >= axis.position else -1
        radius = side * (var_sym - h_sym)
        f_top = _dominates(fp, gp, var_sym, t0n, t1n)
        height = (fp - gp) if f_top else (gp - fp)
        p_info = RadiusInfo(
            f"p({v})", radius,
            f"Radio del casquillo: distancia de {v} al eje {axis.label}, "
            f"{'variable − eje' if side > 0 else 'eje − variable'} porque la región está "
            f"{'después' if side > 0 else 'antes'} del eje.",
        )
        h_info = RadiusInfo(
            f"h({v})", height,
            f"Altura del casquillo: curva {'f' if f_top else 'g'} (la de {'arriba' if v == 'x' else 'la derecha'}) "
            f"menos curva {'g' if f_top else 'f'}.",
        )
        pieces.append(_VolumePiece(t0n, t1n, t0, t1, radius * height, (p_info, h_info),
                                   rf"\left(@p({v})@\right)\left(@h({v})@\right)"))
    return _join_pieces(pieces), cuts


# ─────────────────────────────────────────────────────────────────────────────
# Desarrollo paso a paso (lista imprimible) y árbol interactivo
# ─────────────────────────────────────────────────────────────────────────────

_METHOD_TEXT = {
    SolidMethod.DISKS: (
        "Identificación del radio del disco",
        "Cada corte perpendicular al eje {axis} es un disco macizo. Su radio R({v}) es la distancia de la "
        "curva al eje; se escribe con el signo que la hace positiva en todo el intervalo.",
        "El área de un disco es π·R², y cada disco tiene espesor d{v}: dV = π·[R({v})]²·d{v}. "
        "Sumando (integrando) todos los discos entre {a} y {b} se obtiene el volumen.",
        "Se eleva el radio al cuadrado y se desarrolla hasta tener una suma de términos sencillos.",
    ),
    SolidMethod.WASHERS: (
        "Identificación de los radios exterior e interior",
        "La región no toca el eje {axis}, así que cada corte perpendicular es una arandela: un disco de "
        "radio exterior R({v}) (curva más lejana) con un hueco de radio interior r({v}) (curva más cercana).",
        "El área de una arandela es π·(R² − r²): el disco grande menos el hueco. Con espesor d{v}, "
        "dV = π·([R({v})]² − [r({v})]²)·d{v}, y se integra entre {a} y {b}.",
        "Se elevan los dos radios al cuadrado, se restan y se desarrolla el resultado.",
    ),
    SolidMethod.SHELLS: (
        "Radio y altura del casquillo cilíndrico",
        "Cada franja paralela al eje {axis} genera al girar un casquillo (un cilindro hueco de pared delgada). "
        "Su radio p({v}) es la distancia de la franja al eje y su altura h({v}) es la longitud de la franja.",
        "Si se desenrolla el casquillo se obtiene una lámina de largo 2π·p, alto h y grosor d{v}: "
        "dV = 2π·p({v})·h({v})·d{v}, y se integra entre {a} y {b}.",
        "Se multiplica el radio por la altura y se desarrolla el producto.",
    ),
}


def _single_piece_steps(
    method: SolidMethod,
    axis: RevolutionAxis,
    var_sym: sympy.Symbol,
    piece: _VolumePiece,
    factor: sympy.Expr,
    value: sympy.Expr,
    vol_sym: sympy.Expr,
    num_val: float | None,
) -> list[SolutionStep]:
    """Los 7 pasos del desarrollo clásico para un volumen de un solo tramo."""
    v = var_sym.name
    shown = SolidMethod.DISKS if piece.is_disk and method != SolidMethod.SHELLS else method
    title1, expl1, expl2, expl3 = _METHOD_TEXT[shown]
    fmt = {"axis": axis.label, "v": v, "a": sympy.sstr(piece.t0), "b": sympy.sstr(piece.t1)}
    a_l, b_l, f_l = step_latex(piece.t0), step_latex(piece.t1), step_latex(factor)
    expanded = sympy.expand(piece.core)
    F = antiderivative(expanded, var_sym)  # la misma F que el desglose interactivo
    if F.has(sympy.Integral):
        raise ValueError("La primitiva no tiene forma cerrada")
    F_b = sympy.simplify(F.subs(var_sym, piece.t1))
    F_a = sympy.simplify(F.subs(var_sym, piece.t0))
    tech_title, tech_expl, tech_latex = describe_technique(expanded, var_sym)
    technique = tech_title.removeprefix("Técnica de integración: ")
    radii_plain = ",  ".join(f"{r.name} = {sympy.sstr(r.expr)}" for r in piece.radii)
    radii_latex = r", \quad ".join(f"{r.name} = {step_latex(r.expr)}" for r in piece.radii)
    setup_l = _fill_setup(piece.setup, piece.radii)
    approx_text = f" ≈ {num_val:.5f} u³" if num_val is not None else ""
    approx_latex = rf" \approx {num_val:.5f}" if num_val is not None else ""
    return [
        SolutionStep(1, f"1. {title1}", expl1.format(**fmt) + " " + " ".join(r.meaning for r in piece.radii),
                     radii_plain, radii_latex),
        SolutionStep(2, "2. Planteamiento de la integral del volumen", expl2.format(**fmt),
                     f"V = {sympy.sstr(factor)} * int_({fmt['a']})^({fmt['b']}) {sympy.sstr(piece.core)} d{v}",
                     rf"V = {f_l} \int_{{{a_l}}}^{{{b_l}}} {setup_l} \, d{v}"),
        SolutionStep(3, "3. Expansión algebraica del integrando", expl3.format(**fmt),
                     f"{sympy.sstr(piece.core)} = {sympy.sstr(expanded)}",
                     rf"{step_latex(piece.core)} = {step_latex(expanded)}"),
        SolutionStep(4, f"4. {tech_title}", tech_expl, tech_title, tech_latex),
        SolutionStep(
            5, "5. Obtención de la antiderivada (primitiva F)",
            f"Se aplica {technique[0].lower() + technique[1:]} término a término. Comprobación: al derivar F "
            f"se recupera el integrando, F'({v}) = {sympy.sstr(expanded)}.",
            f"F({v}) = ∫({sympy.sstr(expanded)}) d{v} = {sympy.sstr(F)}",
            rf"F({v}) = \int \left({step_latex(expanded)}\right) d{v} = {step_latex(F)}",
        ),
        SolutionStep(
            6, "6. Evaluación en los límites (Teorema Fundamental del Cálculo)",
            f"La integral definida es F({fmt['b']}) − F({fmt['a']}): la primitiva en el límite superior menos "
            "la primitiva en el inferior.",
            f"F({fmt['b']}) = {sympy.sstr(F_b)}\nF({fmt['a']}) = {sympy.sstr(F_a)}\n"
            f"F({fmt['b']}) - F({fmt['a']}) = {sympy.sstr(value)}",
            rf"\int_{{{a_l}}}^{{{b_l}}} \left({step_latex(expanded)}\right) d{v} = F({b_l}) - F({a_l})"
            rf" = {step_latex(F_b)} - \left({step_latex(F_a)}\right) = {step_latex(value)}",
        ),
        SolutionStep(
            7, "7. Volumen final",
            f"Se multiplica el valor de la integral por el factor {sympy.sstr(factor)} de la fórmula del método.",
            f"V = {sympy.sstr(factor)} · ({sympy.sstr(value)}) = {sympy.sstr(vol_sym)}{approx_text}",
            rf"V = {f_l} \cdot \left({step_latex(value)}\right) = {step_latex(vol_sym)}{approx_latex}",
        ),
    ]


def _multi_piece_steps(
    method: SolidMethod,
    var_sym: sympy.Symbol,
    pieces: list[_VolumePiece],
    cuts: list[tuple[float, sympy.Expr, str]],
    factor: sympy.Expr,
    partials: list[sympy.Expr],
    vol_sym: sympy.Expr,
    num_val: float | None,
) -> list[SolutionStep]:
    """Desarrollo por tramos: cortes, radios de cada tramo, planteamiento, cada integral y suma."""
    v = var_sym.name
    f_l = step_latex(factor)
    used = [c for c in cuts if any(abs(c[0] - p.t0_num) < 1e-9 for p in pieces[1:])]
    cut_text = "; ".join(f"{v} = {sympy.sstr(c[1])} ({c[2]})" for c in used)
    cut_latex = r",\quad ".join(f"{v} = {step_latex(c[1])}" for c in used)
    radii_text, radii_latex, setup_latex = [], [], []
    for k, p in enumerate(pieces, start=1):
        radii_text.append(f"Tramo {k} [{sympy.sstr(p.t0)}, {sympy.sstr(p.t1)}]: "
                          + ", ".join(f"{r.name} = {sympy.sstr(r.expr)}" for r in p.radii))
        radii_latex.append(rf"I_{{{k}}} = \left[{step_latex(p.t0)}, {step_latex(p.t1)}\right]:\;"
                           + r",\; ".join(f"{r.name} = {step_latex(r.expr)}" for r in p.radii))
        setup_latex.append(rf"{f_l} \int_{{{step_latex(p.t0)}}}^{{{step_latex(p.t1)}}} "
                           rf"{_fill_setup(p.setup, p.radii)} \, d{v}")
    vk = [sympy.simplify(factor * pv) for pv in partials]
    approx_text = f" ≈ {num_val:.5f} u³" if num_val is not None else ""
    approx_latex = rf" \approx {num_val:.5f}" if num_val is not None else ""
    what = "la altura del casquillo" if method == SolidMethod.SHELLS else "qué curva es la exterior"
    return [
        SolutionStep(1, "1. Detección de intersecciones y división por tramos",
                     f"El intervalo se divide en {cut_text}. En cada tramo {what} y el signo de cada distancia "
                     f"no cambian, así que el integrando se escribe sin valores absolutos.",
                     f"Intersección en: {cut_text}", cut_latex),
        SolutionStep(2, "2. Radios en cada tramo",
                     " ".join(" ".join(r.meaning for r in p.radii[:1]) for p in pieces[:1]) + " " + " ".join(radii_text),
                     "; ".join(radii_text), r" \quad ".join(radii_latex)),
        SolutionStep(3, "3. Planteamiento de la integral de volumen por tramos",
                     "El volumen total es la suma de los volúmenes de cada tramo: V = V₁ + V₂ + …",
                     " + ".join(f"V_{k}" for k in range(1, len(pieces) + 1)),
                     "V = " + " + ".join(setup_latex)),
        SolutionStep(4, "4. Cálculo de cada integral definida",
                     "Cada integral se resuelve con su primitiva y el Teorema Fundamental del Cálculo "
                     "(el detalle está en el desglose interactivo).",
                     "; ".join(f"V_{k} = {sympy.sstr(x)}" for k, x in enumerate(vk, start=1)),
                     r" \quad ".join(rf"V_{{{k}}} = {step_latex(x)}" for k, x in enumerate(vk, start=1))),
        SolutionStep(5, "5. Volumen total (suma de tramos)",
                     "Se suman los volúmenes de los tramos.",
                     f"V = {' + '.join(sympy.sstr(x) for x in vk)} = {sympy.sstr(vol_sym)}{approx_text}",
                     rf"V = {' + '.join(step_latex(x) for x in vk)} = {step_latex(vol_sym)}{approx_latex}"),
    ]


def _step_tree(
    method_label: str,
    var_sym: sympy.Symbol,
    factor: sympy.Expr,
    pieces: list[_VolumePiece],
    vol_sym: sympy.Expr,
    num_val: float | None,
    preface: Sequence[StepNode] = (),
    ids: IdGenerator | None = None,
) -> StepNode | None:
    """Árbol del desglose interactivo; ``None`` si no se pudo construir (el resultado no se pierde)."""
    try:
        return build_volume_tree(
            method_label=method_label,
            var=var_sym,
            factor=factor,
            pieces=[
                StepPiece(p.t0, p.t1, p.core, p.radii, p.setup,
                          f"{var_sym.name} ∈ [{sympy.sstr(p.t0)}, {sympy.sstr(p.t1)}]" if len(pieces) > 1 else p.label)
                for p in pieces
            ],
            volume=vol_sym,
            numeric_value=num_val,
            preface=preface,
            ids=ids,
        )
    except Exception:  # noqa: BLE001 - el desglose es complementario al resultado
        logger.debug("No se pudo construir el árbol de pasos", exc_info=True)
        return None


def _volume_from_pieces(
    method: SolidMethod,
    axis: RevolutionAxis,
    var_sym: sympy.Symbol,
    pieces: list[_VolumePiece],
    cuts: list[tuple[float, sympy.Expr, str]],
    *,
    preface_steps: Sequence[SolutionStep] = (),
    preface_nodes: Sequence[StepNode] = (),
    ids: IdGenerator | None = None,
    extra_warnings: Sequence[str] = (),
) -> VolumeResult:
    """Integra cada tramo, arma el desarrollo (lista y árbol) y devuelve el ``VolumeResult``."""
    factor = 2 * sympy.pi if method == SolidMethod.SHELLS else sympy.pi
    partials = [sympy.simplify(sympy.integrate(p.core, (var_sym, p.t0, p.t1))) for p in pieces]
    vol_sym = sympy.simplify(factor * sympy.Add(*partials))
    num_val = _numeric_value(vol_sym)
    if num_val is None or not math.isfinite(num_val):
        return VolumeResult(
            method=method,
            is_success=False,
            error_message=(
                "La integral del volumen no converge o no es real. Verifique que las funciones estén "
                "definidas y sean reales en todo el intervalo."
            ),
        )
    if method == SolidMethod.DISKS and not all(p.is_disk for p in pieces):
        method = SolidMethod.WASHERS  # la región no toca el eje: hay hueco
    v = var_sym.name
    steps: list[SolutionStep]
    try:
        if len(pieces) == 1:
            steps = _single_piece_steps(method, axis, var_sym, pieces[0], factor, partials[0], vol_sym, num_val)
        else:
            steps = _multi_piece_steps(method, var_sym, pieces, cuts, factor, partials, vol_sym, num_val)
    except Exception:  # noqa: BLE001 - p. ej. primitiva sin forma cerrada: se informa el resultado
        logger.debug("No se pudo armar el desarrollo", exc_info=True)
        steps = []
    if preface_steps:
        steps = [
            SolutionStep(i, f"{i}. {re.sub(r'^[0-9]+[.] *', '', s.title)}", s.explanation,
                         s.expression_plain_text, s.expression_latex)
            for i, s in enumerate([*preface_steps, *steps], start=1)
        ]
    tree = _step_tree(f"Método de {method.value}", var_sym, factor, pieces, vol_sym, num_val,
                      preface_nodes, ids)
    setup = " + ".join(
        rf"{step_latex(factor)} \int_{{{step_latex(p.t0)}}}^{{{step_latex(p.t1)}}} {_fill_setup(p.setup, p.radii)} \, d{v}"
        for p in pieces
    )
    warnings = list(extra_warnings)
    crossing_cuts = [c for c in cuts if "cruzan" in c[2] and any(abs(c[0] - p.t0_num) < 1e-9 for p in pieces[1:])]
    if crossing_cuts:
        where = ", ".join(f"{v} = {sympy.sstr(c[1])}" for c in crossing_cuts)
        warnings.append(
            f"Las curvas se cruzan en {where}. La región se dividió en {len(pieces)} tramos y en cada uno "
            "se usa la curva que corresponde (exterior o de arriba)."
        )
    integrand = factor * (pieces[0].core if len(pieces) == 1 else sympy.Add(*(p.core for p in pieces)))
    return VolumeResult(
        method=method,
        exact_plain_text=str(vol_sym),
        exact_latex=step_latex(vol_sym),
        numeric_value=num_val,
        integrand_plain_text=str(integrand) if len(pieces) == 1 else " + ".join(str(factor * p.core) for p in pieces),
        integrand_latex=step_latex(integrand) if len(pieces) == 1 else setup,
        integral_setup_latex=setup,
        is_success=True,
        steps=steps,
        warnings=warnings,
        step_tree=tree,
    )


def calculate_disk_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
) -> VolumeResult:
    """Volumen por Discos: V = π ∫_a^b [R(t)]² dt.

    Si la región no toca el eje (hay hueco), el resultado se calcula por Arandelas, partiendo en
    los cruces (antes se integraba R² − r² sin partir y daba volúmenes negativos: hallazgo M4).
    """
    return _perpendicular_volume(region, axis or RevolutionAxis.x_axis(), SolidMethod.DISKS)


def calculate_washer_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
) -> VolumeResult:
    """Volumen por Arandelas: V = π ∫_a^b ([R(t)]² − [r(t)]²) dt, por tramos si hace falta."""
    return _perpendicular_volume(region, axis or RevolutionAxis.x_axis(), SolidMethod.WASHERS)


def _perpendicular_volume(region: Region2D, axis: RevolutionAxis, method: SolidMethod) -> VolumeResult:
    if not _SYMPY_AVAILABLE:
        return VolumeResult(method=method, is_success=False, error_message="SymPy no está disponible.")
    try:
        if not is_method_compatible(method, axis, region.variable):
            word = "discos" if method == SolidMethod.DISKS else "arandelas"
            return VolumeResult(
                method=method,
                is_success=False,
                error_message=(
                    f"El método de {word} requiere cortes perpendiculares al eje {axis.label}. "
                    f"Para integrar en '{region.variable}', considere el método de Casquillos."
                ),
            )
        f = _ensure_parsed(region.f_expr).sympy_expr
        g = _ensure_parsed(region.g_expr, default_zero=True).sympy_expr
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)
        pieces, cuts = _washer_pieces(f, g, var_sym, axis, num_a, num_b, sym_a, sym_b)
        return _volume_from_pieces(method, axis, var_sym, pieces, cuts)
    except Exception as exc:  # noqa: BLE001
        return VolumeResult(method=method, is_success=False, error_message=str(exc))


def calculate_shell_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
) -> VolumeResult:
    """Volumen por Casquillos: V = 2π ∫_a^b p(t)·h(t) dt, con p = ±(t − h) sin valor absoluto."""
    axis = axis or RevolutionAxis.y_axis()
    if not _SYMPY_AVAILABLE:
        return VolumeResult(method=SolidMethod.SHELLS, is_success=False, error_message="SymPy no está disponible.")
    try:
        if not is_method_compatible(SolidMethod.SHELLS, axis, region.variable):
            return VolumeResult(
                method=SolidMethod.SHELLS,
                is_success=False,
                error_message=(
                    f"El método de casquillos requiere que los cortes sean paralelos al eje {axis.label}. "
                    f"Para integrar en '{region.variable}', considere Discos o Arandelas."
                ),
            )
        f = _ensure_parsed(region.f_expr).sympy_expr
        g = _ensure_parsed(region.g_expr, default_zero=True).sympy_expr
        var_sym = sympy.Symbol(region.variable)
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)
        pieces, cuts = _shell_pieces(f, g, var_sym, axis, num_a, num_b, sym_a, sym_b)
        return _volume_from_pieces(SolidMethod.SHELLS, axis, var_sym, pieces, cuts)
    except Exception as exc:  # noqa: BLE001
        return VolumeResult(method=SolidMethod.SHELLS, is_success=False, error_message=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Inversión a la otra variable por franjas horizontales (hallazgo A1)
# ─────────────────────────────────────────────────────────────────────────────

def _strip_pieces(
    strips: list[Strip],
    method: SolidMethod,
    axis: RevolutionAxis,
    t_sym: sympy.Symbol,
    x_name: str,
) -> list[_VolumePiece]:
    """Tramos en la nueva variable a partir de las franjas: arandelas (eje ⟂) o casquillos (eje ∥)."""
    pos = sympy.nsimplify(axis.position)
    t = t_sym.name
    pieces: list[_VolumePiece] = []
    for strip in strips:
        label = f"{t} ∈ [{sympy.sstr(strip.y0)}, {sympy.sstr(strip.y1)}]: " + "; ".join(
            f"de {left.describe(x_name)} a {right.describe(x_name)}" for left, right in strip.intervals
        )
        mid_t = 0.5 * (strip.y0_num + strip.y1_num)
        if method == SolidMethod.SHELLS:
            side = 1 if mid_t >= axis.position else -1
            radius = side * (t_sym - pos)
            height = sympy.Add(*(right.expr - left.expr for left, right in strip.intervals))
            height = real_branch(height, t_sym, strip.y0_num, strip.y1_num)
            pieces.append(_VolumePiece(
                strip.y0_num, strip.y1_num, strip.y0, strip.y1, radius * height,
                (RadiusInfo(f"p({t})", radius, f"Radio: distancia de {t} al eje {axis.label}."),
                 RadiusInfo(f"h({t})", height, "Largo de la franja horizontal: borde derecho menos borde izquierdo.")),
                rf"\left(@p({t})@\right)\left(@h({t})@\right)", label,
            ))
            continue
        core = sympy.Integer(0)
        radii: list[RadiusInfo] = []
        setup_parts: list[str] = []
        disk = True
        for k, (left, right) in enumerate(strip.intervals, start=1):
            mid_x = 0.5 * (float(sympy.N(left.expr.subs(t_sym, mid_t))) + float(sympy.N(right.expr.subs(t_sym, mid_t))))
            if mid_x >= axis.position:
                R, r = right.expr - pos, left.expr - pos
            else:
                R, r = pos - left.expr, pos - right.expr
            R = real_branch(sympy.simplify(R), t_sym, strip.y0_num, strip.y1_num)
            r = real_branch(sympy.simplify(r), t_sym, strip.y0_num, strip.y1_num)
            suffix = f"_{k}" if len(strip.intervals) > 1 else ""
            radii.append(RadiusInfo(f"R{suffix}({t})", R, f"Radio exterior: borde de la franja más lejano del eje {axis.label}."))
            if r == 0:
                core += R**2
                setup_parts.append(rf"\left[@R{suffix}({t})@\right]^2")
            else:
                disk = False
                radii.append(RadiusInfo(f"r{suffix}({t})", r, f"Radio interior: borde de la franja más cercano al eje {axis.label}."))
                core += R**2 - r**2
                setup_parts.append(rf"\left[@R{suffix}({t})@\right]^2 - \left[@r{suffix}({t})@\right]^2")
        setup = " + ".join(f"\\left({s}\\right)" if (len(setup_parts) > 1 or " - " in s) else s for s in setup_parts)
        pieces.append(_VolumePiece(strip.y0_num, strip.y1_num, strip.y0, strip.y1, core, tuple(radii),
                                   setup, label, is_disk=disk))
    return _join_pieces(pieces)


def _inversion_preface(
    region: Region2D, strips: list[Strip], t_name: str, method: SolidMethod, axis: RevolutionAxis,
    ids: IdGenerator,
) -> tuple[SolutionStep, StepNode]:
    x = region.variable
    lines = []
    latex_lines = []
    for s in strips:
        parts = "; ".join(f"de {lft.describe(x)} a {rgt.describe(x)}" for lft, rgt in s.intervals)
        lines.append(f"Para {t_name} entre {sympy.sstr(s.y0)} y {sympy.sstr(s.y1)}: {parts}.")
        latex_lines.append(
            rf"{step_latex(s.y0)} \le {t_name} \le {step_latex(s.y1)}:\; "
            + r";\; ".join(rf"{step_latex(lft.expr)} \le {x} \le {step_latex(rgt.expr)}" for lft, rgt in s.intervals)
        )
    expl = (
        f"Con el eje {axis.label}, el método de {method.value} necesita cortes en d{t_name}. Se describe la "
        f"región con franjas horizontales: para cada {t_name} se despeja {x} en cada curva y se toma la "
        "sección real de la región (las rectas de los límites también pueden ser bordes). "
        + " ".join(lines)
    )
    step = SolutionStep(1, f"Despeje e inversión: franjas en d{t_name}", expl, "\n".join(lines),
                        r" \qquad ".join(latex_lines))
    children = tuple(
        StepNode(ids.next(), "Strip", f"Franja {k}: {t_name} ∈ [{sympy.sstr(s.y0)}, {sympy.sstr(s.y1)}]",
                 "; ".join(f"Borde izquierdo: {lft.describe(x)}. Borde derecho: {rgt.describe(x)}."
                           for lft, rgt in s.intervals),
                 latex_lines[k - 1])
        for k, s in enumerate(strips, start=1)
    )
    node = StepNode(ids.next(), "Inversion", f"Despejar {x} en función de {t_name}", expl,
                    r" \qquad ".join(latex_lines), children)
    return step, node


def _inverted_volume(region: Region2D, axis: RevolutionAxis, method: SolidMethod) -> VolumeResult:
    """Volumen con el método pedido integrando en la otra variable (franjas horizontales)."""
    try:
        if region.variable != "x":
            raise InversionFailed("La inversión solo está disponible para regiones dadas en x.")
        f = _ensure_parsed(region.f_expr).sympy_expr
        g = _ensure_parsed(region.g_expr, default_zero=True).sympy_expr
        x_sym, y_sym = sympy.Symbol("x"), sympy.Symbol("y")
        num_a, num_b, sym_a, sym_b = _evaluate_bounds(region.a, region.b)
        crossings = find_curve_crossings(f, g, x_sym, 0.0, num_a, num_b, method=SolidMethod.SHELLS)
        strips = horizontal_strips(f, g, x_sym, y_sym, num_a, num_b, sym_a, sym_b, crossings)
        pieces = _strip_pieces(strips, method, axis, y_sym, "x")
        ids = IdGenerator()
        step, node = _inversion_preface(region, strips, "y", method, axis, ids)
        cuts = [(p.t0_num, p.t0, "cambia la forma de la franja horizontal") for p in pieces[1:]]
        return _volume_from_pieces(method, axis, y_sym, pieces, cuts, preface_steps=[step],
                                   preface_nodes=[node], ids=ids)
    except InversionFailed as exc:
        return VolumeResult(method=method, is_success=False,
                            error_message=f"{exc} Use el método directo para este eje.")
    except Exception as exc:  # noqa: BLE001
        return VolumeResult(method=method, is_success=False, error_message=str(exc))


def _reject_negative(res: VolumeResult) -> VolumeResult:
    """Red de seguridad: un volumen negativo es siempre un error de planteamiento, nunca un éxito."""
    value = res.numeric_value
    if res.is_success and value is not None and value < -1e-9 * max(1.0, abs(value)):
        return VolumeResult(
            method=res.method,
            is_success=False,
            error_message=(
                f"El volumen calculado es negativo ({value:.6g}): no se pudo determinar qué curva es "
                "exterior en todo el intervalo. Revise la región o divida el intervalo en tramos."
            ),
        )
    return res


def numeric_volume(region: Region2D, axis: RevolutionAxis) -> float | None:
    """V por cuadratura (mpmath), partiendo en los cruces. Válido porque el eje no atraviesa
    la región (axis_crossing_error ya lo garantiza)."""
    import mpmath

    f = real_root_form(_ensure_parsed(region.f_expr).sympy_expr)  # ∛x real, como en la gráfica
    g = real_root_form(_ensure_parsed(region.g_expr, default_zero=True).sympy_expr)
    var = sympy.Symbol(region.variable)
    a, b, _sa, _sb = _evaluate_bounds(region.a, region.b)
    k = sympy.nsimplify(axis.position)
    # El método natural depende de la variable, no solo del eje: con una región en y y el eje
    # vertical, los cortes dy son perpendiculares (arandelas). Antes se usaba siempre la fórmula de
    # casquillos para un eje vertical y la referencia salía mal para regiones en y.
    if is_method_compatible(SolidMethod.SHELLS, axis, region.variable):
        core = 2 * sympy.pi * sympy.Abs(var - k) * sympy.Abs(f - g)
        method = SolidMethod.SHELLS
    else:
        core = sympy.pi * sympy.Abs((f - k) ** 2 - (g - k) ** 2)
        method = SolidMethod.WASHERS
    cuts = [float(t) for t, _ in find_curve_crossings(f, g, var, axis.position, a, b, method=method)]
    # Las esquinas de |u| y los cambios de signo de una distancia también son nodos: la cuadratura
    # pierde ~1e-7 si una esquina cae dentro de un subintervalo.
    kinks = [c for c, _ in sign_cut_points((f, g), var, a, b, extra=(f - k, g - k))]
    nodes = sorted({a, b, *cuts, *kinks, *np.linspace(a, b, 17).tolist()})
    val = mpmath.quad(sympy.lambdify(var, core, "mpmath"), nodes)
    return float(val) if mpmath.isfinite(val) else None


def _cross_check(
    res: VolumeResult,
    region: Region2D,
    axis: RevolutionAxis,
    *,
    inverted: bool = True,
) -> VolumeResult:
    """Rechaza un volumen simbólico que no coincide con la cuadratura independiente.

    Para la inversión a dy la tolerancia es estricta (1e-5): es el planteamiento con más riesgo.
    Para los métodos directos solo se rechaza una diferencia grosera (1e-3), que delata un error
    de planteamiento y no de cuadratura; las regiones con splines (``Piecewise``) no se comprueban.
    """
    if not res.is_success or res.numeric_value is None:
        return res
    if not inverted and _has_piecewise(_ensure_parsed(region.f_expr).sympy_expr,
                                       _ensure_parsed(region.g_expr, default_zero=True).sympy_expr):
        return res
    try:
        ref = numeric_volume(region, axis)
    except Exception:  # noqa: BLE001 - la cuadratura es solo una red de seguridad
        return res
    tol = 1e-5 if inverted else 1e-3
    if ref is None or math.isclose(res.numeric_value, ref, rel_tol=tol, abs_tol=1e-7):
        return res
    origin = "El planteamiento invertido" if inverted else "El desarrollo simbólico"
    return VolumeResult(
        method=res.method,
        is_success=False,
        error_message=(
            f"{origin} da {res.numeric_value:.6g}, pero la cuadratura da {ref:.6g}. "
            "Use el método directo para este eje." if inverted else
            f"{origin} da {res.numeric_value:.6g}, pero la cuadratura da {ref:.6g}. "
            "Revise la región: el resultado simbólico no es confiable."
        ),
    )


def calculate_revolution_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    method: SolidMethod | None = None,
    allow_inversion: bool = True,
    *,
    _check_axis: bool = True,
) -> VolumeResult:
    """Calcula el volumen con el método pedido o con el recomendado.

    Si el método exige cortes en la otra variable (Discos/Arandelas con eje vertical o Casquillos
    con eje horizontal) y ``allow_inversion`` es True, la región se describe por franjas
    horizontales y se integra en ``dy`` (``integrallab.core.volume.inversion``). El resultado
    invertido se contrasta siempre con la cuadratura independiente ``numeric_volume``.

    Si el eje de giro atraviesa el interior de la región, devuelve ``is_success=False``: los dos
    lados se solapan al girar y las fórmulas por método dejarían un volumen incorrecto.
    """
    axis = axis or RevolutionAxis.x_axis()

    if _check_axis and method is not None:
        axis_msg = _axis_crossing_error(region, axis)
        if axis_msg:
            return VolumeResult(
                method=method,
                is_success=False,
                error_message=(
                    f"{axis_msg} Elija un eje que no atraviese la región (por ejemplo, uno "
                    "que pase por su borde o fuera de ella)."
                ),
            )

    if method is None:
        rec = recommend_method(region, axis)
        if not rec.is_decidable or rec.recommended_method is None:
            return VolumeResult(
                method=SolidMethod.DISKS,
                is_success=False,
                error_message=f"No se pudo determinar un método viable: {'; '.join(rec.limitations_or_warnings)}",
            )
        method = rec.recommended_method

    if not is_method_compatible(method, axis, region.variable):
        if not allow_inversion:
            return VolumeResult(
                method=method,
                is_success=False,
                error_message=(
                    f"El método {method.value} no es compatible directamente con el eje {axis.label} "
                    f"para la variable '{region.variable}'."
                ),
            )
        return _cross_check(_reject_negative(_inverted_volume(region, axis, method)), region, axis)

    if method == SolidMethod.DISKS:
        res = calculate_disk_volume(region, axis)
    elif method == SolidMethod.WASHERS:
        res = calculate_washer_volume(region, axis)
    elif method == SolidMethod.SHELLS:
        res = calculate_shell_volume(region, axis)
    else:
        return VolumeResult(method=SolidMethod.DISKS, is_success=False, error_message=f"Método desconocido: {method}")
    return _cross_check(_reject_negative(res), region, axis, inverted=False)


def is_method_compatible(
    method: SolidMethod,
    axis: RevolutionAxis,
    variable: str = "x",
) -> bool:
    """Indica si un método es aplicable sin invertir funciones para la variable dada.

    Regla geométrica (el espesor diferencial ``d<variable>`` determina el método):
    - Discos y Arandelas: cortes perpendiculares al eje, es decir, ``dx`` con un
      eje horizontal (y = k) o ``dy`` con un eje vertical (x = h).
    - Casquillos: cortes paralelos al eje, es decir, ``dx`` con un eje vertical
      (x = h) o ``dy`` con un eje horizontal (y = k).

    Es la misma regla que aplican ``calculate_disk_volume``, ``calculate_washer_volume``
    y ``calculate_shell_volume``; la UI la usa para no ofrecer combinaciones imposibles.
    """
    is_perpendicular = (
        (variable == "x" and axis.orientation == AxisOrientation.HORIZONTAL)
        or (variable == "y" and axis.orientation == AxisOrientation.VERTICAL)
    )
    if method in (SolidMethod.DISKS, SolidMethod.WASHERS):
        return is_perpendicular
    if method == SolidMethod.SHELLS:
        return not is_perpendicular
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Motor de Recomendación Explicable
# ─────────────────────────────────────────────────────────────────────────────

_AXIS_SAMPLES = 2001
_AXIS_TOL = 1e-9


def _sample_profile(expr: sympy.Expr, var_sym: sympy.Symbol, ts: np.ndarray) -> np.ndarray | None:
    """Evalúa ``expr`` en ``ts`` de forma vectorizada; ``None`` si no se puede (nan fuera del dominio)."""
    try:
        real_expr = prepare_expr_for_real_eval(expr)
        fn = sympy.lambdify(var_sym, real_expr, modules=REAL_EVAL_MODULES)
        with np.errstate(all="ignore"):
            values = np.asarray(fn(ts))
        if np.iscomplexobj(values):
            values = np.where(np.abs(values.imag) < 1e-9 * np.maximum(1.0, np.abs(values.real)), values.real, np.nan)
        values = values.astype(float)
        if values.ndim == 0:
            values = np.full(ts.shape, float(values))
        return values
    except Exception:
        return None


def _check_axis_intersects_region(
    region: Region2D,
    axis: RevolutionAxis,
    num_a: float,
    num_b: float,
    f_sym: sympy.Expr,
    g_sym: sympy.Expr,
    var_sym: sympy.Symbol,
) -> str | None:
    """Verifica si el eje de rotación atraviesa el interior de la región plana.

    Si el eje pasa por dentro de la región, al girar los dos lados se solapan y las fórmulas de
    discos, arandelas y casquillos (que suman los lados) dejan de dar el volumen del sólido.

    Con corte paralelo al eje (p. ej. región en x y eje vertical) basta comparar la posición del
    eje con el intervalo. En el otro caso se muestrea densamente la banda [min(f, g), max(f, g)]
    (2001 puntos) en lugar de 7, para no perder cruces entre muestras.
    """
    k = axis.position
    tol = _AXIS_TOL * max(1.0, abs(k))

    is_parallel_cut = (
        (region.variable == "x" and axis.orientation == AxisOrientation.VERTICAL)
        or (region.variable == "y" and axis.orientation == AxisOrientation.HORIZONTAL)
    )
    if is_parallel_cut:
        if num_a + tol < k < num_b - tol:
            return (
                f"El eje {axis.label} atraviesa el interior del intervalo de integración "
                f"{region.variable} ∈ [{num_a:.4g}, {num_b:.4g}]."
            )
        return None

    ts = np.linspace(num_a, num_b, _AXIS_SAMPLES)
    f_vals = _sample_profile(f_sym, var_sym, ts)
    g_vals = _sample_profile(g_sym, var_sym, ts)
    if f_vals is None or g_vals is None:
        # Respaldo: evaluación puntual en 7 abscisas, como antes.
        f_vals = np.full(7, np.nan)
        g_vals = np.full(7, np.nan)
        ts = np.array([num_a + (num_b - num_a) * t for t in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)])
        for i, p in enumerate(ts):
            try:
                f_vals[i] = float(f_sym.subs(var_sym, p).evalf())
                g_vals[i] = float(g_sym.subs(var_sym, p).evalf())
            except Exception:
                continue

    lo = np.minimum(f_vals, g_vals)
    hi = np.maximum(f_vals, g_vals)
    inside = np.isfinite(lo) & np.isfinite(hi) & (lo + tol < k) & (k < hi - tol)
    if inside.any():
        idx = int(np.argmax(inside))
        coord = "y" if region.variable == "x" else "x"
        return (
            f"El eje {axis.label} atraviesa el interior de la región entre "
            f"{coord}={lo[idx]:.2f} y {coord}={hi[idx]:.2f} (en {region.variable}≈{ts[idx]:.3g}), "
            "lo cual provocaría autointersecciones."
        )
    return None


def _axis_crossing_error(region: Region2D, axis: RevolutionAxis) -> str | None:
    """Devuelve el mensaje de error si el eje atraviesa la región; ``None`` si es válido.

    Si la región o los límites no son válidos devuelve ``None``: ese error lo reporta el método
    de cálculo con su propio mensaje.
    """
    try:
        f_parsed = _ensure_parsed(region.f_expr)
        g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
        num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)
    except Exception:
        return None
    return _check_axis_intersects_region(
        region,
        axis,
        num_a,
        num_b,
        f_parsed.sympy_expr,
        g_parsed.sympy_expr,
        sympy.Symbol(region.variable),
    )


def axis_crossing_error(region: Region2D, axis: RevolutionAxis) -> str | None:
    """Mensaje de error si el eje de giro atraviesa el interior de la región; ``None`` si es válido.

    Es la misma verificación que aplica ``calculate_revolution_volume`` (muestreo NumPy, sin
    SymPy pesado), expuesta para que la interfaz pueda validar el eje antes de lanzar cálculos
    simbólicos largos o de mostrar un sólido que luego se rechazaría.
    """
    return _axis_crossing_error(region, axis)


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
    axis_err = _check_axis_intersects_region(
        region, axis, num_a, num_b, f_parsed.sympy_expr, g_parsed.sympy_expr, var_sym
    )
    if axis_err:
        return MethodRecommendation(
            recommended_method=None,
            justification="No se puede recomendar un método con el eje dentro de la región.",
            is_decidable=False,
            limitations_or_warnings=[axis_err],
        )

    # 2. Determinar método natural según paralelismo/perpendicularidad
    # Cortes diferenciales perpendiculares al eje -> Discos o Arandelas
    is_perpendicular = (
        (region.variable == "x" and axis.orientation == AxisOrientation.HORIZONTAL)
        or (region.variable == "y" and axis.orientation == AxisOrientation.VERTICAL)
    )

    if is_perpendicular:
        # Hay hueco salvo que una de las curvas sea el propio eje (radio interior idénticamente 0).
        k = sympy.nsimplify(axis.position)
        has_void = not any(
            sympy.simplify(c - k) == 0 for c in (f_parsed.sympy_expr, g_parsed.sympy_expr)
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

@dataclass(frozen=True)
class SolidProfile:
    """Perfil numérico de la región (nodos axiales y valores de f y g), calculado una vez.

    Girarlo a otro ángulo es solo NumPy (``revolve_profile``): los deslizadores ya no vuelven a
    llamar a ``lambdify`` ni evalúan las curvas punto a punto en cada cuadro (hallazgo A8).
    """

    t: np.ndarray
    f: np.ndarray
    g: np.ndarray
    axis: RevolutionAxis


def solid_profile(region: Region2D, axis: RevolutionAxis | None = None, num_axial: int = 40) -> SolidProfile:
    """Muestrea f y g en ``num_axial`` nodos de [a, b] repartidos según la longitud de arco."""
    axis = axis or RevolutionAxis.x_axis()
    f_parsed = _ensure_parsed(region.f_expr)
    g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
    var_sym = sympy.Symbol(region.variable)
    num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)
    f_lamb = sympy.lambdify(var_sym, prepare_expr_for_real_eval(f_parsed.sympy_expr), modules=REAL_EVAL_MODULES)
    g_lamb = sympy.lambdify(var_sym, prepare_expr_for_real_eval(g_parsed.sympy_expr), modules=REAL_EVAL_MODULES)
    # Nodos axiales: el giro angular es exacto, así que solo se densifica a lo largo del perfil,
    # siguiendo la longitud de arco de f y g. La cantidad de filas es exactamente num_axial.
    t_dense = np.linspace(num_a, num_b, max(400, 8 * num_axial))
    with np.errstate(all="ignore"):
        f_dense = _evaluate_profile(f_lamb, t_dense)
        g_dense = _evaluate_profile(g_lamb, t_dense)
        t_vals = equidistributed_nodes(t_dense, [f_dense, g_dense], num_axial)
        f_vals = _evaluate_profile(f_lamb, t_vals)
        g_vals = _evaluate_profile(g_lamb, t_vals)
    return SolidProfile(np.asarray(t_vals, dtype=float), f_vals, g_vals, axis)


def revolve_profile(profile: SolidProfile, num_radial: int = 36, theta_max: float = 2 * math.pi) -> SolidMesh3D:
    """Gira un perfil ya muestreado hasta ``theta_max`` (radianes). Solo NumPy: ~0,1 ms."""
    axis = profile.axis
    t_vals, f_vals, g_vals = profile.t, profile.f, profile.g
    theta_bound = max(1e-4, min(2 * np.pi, float(theta_max)))
    theta_vals = np.linspace(0, theta_bound, num_radial)
    cos_t, sin_t = np.cos(theta_vals), np.sin(theta_vals)
    X_in = Y_in = Z_in = None
    with np.errstate(invalid="ignore"):
        if axis.orientation == AxisOrientation.HORIZONTAL:
            dist_f = np.abs(f_vals - axis.position)
            dist_g = np.abs(g_vals - axis.position)
            r_outer = np.maximum(dist_f, dist_g)
            r_inner = np.minimum(dist_f, dist_g)
            X_out = np.repeat(t_vals[:, np.newaxis], num_radial, axis=1)
            Y_out = axis.position + np.multiply.outer(r_outer, cos_t)
            Z_out = np.multiply.outer(r_outer, sin_t)
            if bool(np.any(r_inner > 1e-6)):
                X_in = X_out.copy()
                Y_in = axis.position + np.multiply.outer(r_inner, cos_t)
                Z_in = np.multiply.outer(r_inner, sin_t)
        else:
            r_axial = np.abs(t_vals - axis.position)
            y_top = np.maximum(f_vals, g_vals)
            y_bot = np.minimum(f_vals, g_vals)
            X_out = axis.position + np.multiply.outer(r_axial, cos_t)
            Z_out = np.multiply.outer(r_axial, sin_t)
            Y_out = np.repeat(y_top[:, np.newaxis], num_radial, axis=1)
            if bool(np.any(np.abs(y_top - y_bot) > 1e-6)):
                X_in, Z_in = X_out.copy(), Z_out.copy()
                Y_in = np.repeat(y_bot[:, np.newaxis], num_radial, axis=1)
    return SolidMesh3D(
        x_outer=X_out, y_outer=Y_out, z_outer=Z_out,
        x_inner=X_in, y_inner=Y_in, z_inner=Z_in,
        axis=axis, is_valid=True,
    )


def generate_solid_mesh(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    num_radial: int = 36,
    num_axial: int = 40,
    theta_max: float = 2 * math.pi,
) -> SolidMesh3D:
    """Genera matrices numéricas (X, Y, Z) en NumPy para renderizar el sólido en 3D.

    Parametriza la superficie de revolución de manera exacta:
    - Rotación en eje horizontal (y = k):  X = t,  Y = k + R(t)·cos θ,  Z = R(t)·sin θ
    - Rotación en eje vertical (x = h):    X = h + |t − h|·cos θ,  Y = y(t),  Z = |t − h|·sin θ

    Equivale a ``revolve_profile(solid_profile(region, axis, num_axial), num_radial, theta_max)``.
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
        return revolve_profile(solid_profile(region, axis, num_axial), num_radial, theta_max)
    except Exception as exc:  # noqa: BLE001
        return SolidMesh3D(
            x_outer=np.empty((0, 0)),
            y_outer=np.empty((0, 0)),
            z_outer=np.empty((0, 0)),
            axis=axis,
            is_valid=False,
            error_message=str(exc),
        )


def generate_representative_slice(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    position: float | None = None,
    thickness_factor: float = 0.04,
    num_radial: int = 36,
    theta_max: float = 2 * math.pi,
) -> SolidMesh3D:
    """Genera la malla de una rebanada o arandela representativa de espesor dx o dy.

    Args:
        region: Región plana que define el sólido.
        axis: Eje de giro.
        position: Coordenada axial donde situar la rebanada (por defecto, punto medio de [a, b]).
        thickness_factor: Fracción del ancho del intervalo que ocupa el espesor de la rebanada.
        num_radial: Resolución angular.
        theta_max: Ángulo máximo de revolución en radianes.

    Returns:
        SolidMesh3D con la arandela o disco representativo en la posición seleccionada.
    """
    num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)
    span = max(1e-5, num_b - num_a)
    if position is None:
        pos = num_a + 0.5 * span
    else:
        pos = max(num_a, min(num_b, float(position)))

    dx = max(0.001, thickness_factor * span)
    t0 = max(num_a, pos - 0.5 * dx)
    t1 = min(num_b, pos + 0.5 * dx)
    if t1 <= t0:
        t1 = t0 + 0.01

    sub_reg = Region2D(region.f_expr, region.g_expr, a=t0, b=t1, variable=region.variable)
    return generate_solid_mesh(sub_reg, axis=axis, num_radial=num_radial, num_axial=2, theta_max=theta_max)


def generate_riemann_mesh(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    num_disks: int = 10,
    num_radial: int = 36,
    theta_max: float = 2 * math.pi,
) -> SolidMesh3D:
    """Genera la aproximación escalonada por discos/arandelas cilíndricos de Riemann.

    Args:
        region: Región plana que define el sólido.
        axis: Eje de giro.
        num_disks: Cantidad de cilindros de Riemann en [a, b].
        num_radial: Resolución angular.
        theta_max: Ángulo de revolución en radianes.

    Returns:
        SolidMesh3D con la geometría escalonada discreta de Riemann.
    """
    axis = axis or RevolutionAxis.x_axis()
    num_disks = max(2, min(50, int(num_disks)))
    num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)
    edges = np.linspace(num_a, num_b, num_disks + 1)

    f_parsed = _ensure_parsed(region.f_expr)
    g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
    var_sym = sympy.Symbol(region.variable)
    f_real = prepare_expr_for_real_eval(f_parsed.sympy_expr)
    g_real = prepare_expr_for_real_eval(g_parsed.sympy_expr)
    f_lamb = sympy.lambdify(var_sym, f_real, modules=REAL_EVAL_MODULES)
    g_lamb = sympy.lambdify(var_sym, g_real, modules=REAL_EVAL_MODULES)

    t_stepped: list[float] = []
    f_stepped: list[float] = []
    g_stepped: list[float] = []
    for i in range(num_disks):
        t_left, t_right = edges[i], edges[i + 1]
        t_mid = 0.5 * (t_left + t_right)
        try:
            fv = float(np.real(f_lamb(t_mid))) if np.isreal(f_lamb(t_mid)) else np.nan
        except Exception:
            fv = np.nan
        try:
            gv = float(np.real(g_lamb(t_mid))) if np.isreal(g_lamb(t_mid)) else np.nan
        except Exception:
            gv = np.nan
        t_stepped.extend([t_left, t_right])
        f_stepped.extend([fv, fv])
        g_stepped.extend([gv, gv])

    t_vals = np.array(t_stepped)
    f_vals = np.array(f_stepped)
    g_vals = np.array(g_stepped)

    theta_bound = max(1e-4, min(2 * np.pi, float(theta_max)))
    theta_vals = np.linspace(0, theta_bound, num_radial)
    T_grid, Theta_grid = np.meshgrid(t_vals, theta_vals, indexing="ij")

    if axis.orientation == AxisOrientation.HORIZONTAL:
        dist_f = np.abs(f_vals - axis.position)
        dist_g = np.abs(g_vals - axis.position)
        r_outer_1d = np.maximum(dist_f, dist_g)
        r_inner_1d = np.minimum(dist_f, dist_g)
        R_outer = np.repeat(r_outer_1d[:, np.newaxis], num_radial, axis=1)
        R_inner = np.repeat(r_inner_1d[:, np.newaxis], num_radial, axis=1)
        X_out = T_grid
        Y_out = axis.position + R_outer * np.cos(Theta_grid)
        Z_out = R_outer * np.sin(Theta_grid)
        has_inner = bool(np.any(r_inner_1d > 1e-6))
        if has_inner:
            X_in = T_grid
            Y_in = axis.position + R_inner * np.cos(Theta_grid)
            Z_in = R_inner * np.sin(Theta_grid)
        else:
            X_in = Y_in = Z_in = None
    else:
        r_axial = np.abs(t_vals - axis.position)
        R_grid = np.repeat(r_axial[:, np.newaxis], num_radial, axis=1)
        y_top_1d = np.maximum(f_vals, g_vals)
        y_bot_1d = np.minimum(f_vals, g_vals)
        Y_out = np.repeat(y_top_1d[:, np.newaxis], num_radial, axis=1)
        X_out = axis.position + R_grid * np.cos(Theta_grid)
        Z_out = R_grid * np.sin(Theta_grid)
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

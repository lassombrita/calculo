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
        steps: Lista ordenada de pasos analíticos de resolución.
        warnings: Advertencias sobre cruces de curvas que pueden afectar el resultado.
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


def invert_region_to_variable(
    region: Region2D,
    target_var: str = "y",
) -> tuple[Region2D, str, str]:
    """Transforma una región plana acotada invirtiendo la variable independiente (ej. x -> y).

    Returns:
        tuple[Region2D, str, str]: (nueva_region, explicacion_texto, explicacion_latex)
    """
    if region.variable == target_var:
        return region, "", ""

    f_parsed = _ensure_parsed(region.f_expr)
    g_parsed = _ensure_parsed(region.g_expr, default_zero=True)
    num_a, num_b, _, _ = _evaluate_bounds(region.a, region.b)

    from_sym = sympy.Symbol(region.variable)
    to_sym = sympy.Symbol(target_var)

    f_inv = invert_symbolic_expression(f_parsed.sympy_expr, from_sym, to_sym, num_a, num_b)

    f_a = float(f_parsed.sympy_expr.subs(from_sym, num_a).evalf())
    f_b = float(f_parsed.sympy_expr.subs(from_sym, num_b).evalf())

    c_num = min(f_a, f_b)
    d_num = max(f_a, f_b)

    has_g = region.g_expr is not None and g_parsed.sympy_expr != 0
    if has_g:
        g_inv = invert_symbolic_expression(g_parsed.sympy_expr, from_sym, to_sym, num_a, num_b)
        g_a = float(g_parsed.sympy_expr.subs(from_sym, num_a).evalf())
        g_b = float(g_parsed.sympy_expr.subs(from_sym, num_b).evalf())
        c_num = min(c_num, g_a, g_b)
        d_num = max(d_num, g_a, g_b)
        new_f_expr = str(f_inv)
        new_g_expr = str(g_inv)
        expl_text = (
            f"Despeje analítico: {region.variable} en función de {target_var}.\n"
            f"Curva 1: {target_var} = {f_parsed.plain_text}  ==>  {region.variable} = {f_inv}\n"
            f"Curva 2: {target_var} = {g_parsed.plain_text}  ==>  {region.variable} = {g_inv}\n"
            f"Límites en {target_var}: [{c_num:.4g}, {d_num:.4g}]."
        )
        expl_latex = (
            f"\\text{{Despeje: }} {sympy.latex(from_sym)} = {sympy.latex(f_inv)}"
            f" \\quad \\text{{y}} \\quad {sympy.latex(from_sym)} = {sympy.latex(g_inv)}"
        )
    else:
        # Rama sin curva g: la región bajo f(x) en [a,b].
        # Al integrar en dy la región queda entre x=0 (eje) y x=f_inv(y).
        # Verificar monotonía para dar un mensaje claro si falla.
        try:
            f_deriv = sympy.diff(f_parsed.sympy_expr, from_sym)
            test_pts = [num_a + (num_b - num_a) * t for t in (0.1, 0.3, 0.5, 0.7, 0.9)]
            signs = []
            for tp in test_pts:
                try:
                    dv = float(f_deriv.subs(from_sym, tp).evalf())
                    signs.append(dv)
                except Exception:
                    pass
            if signs and not (all(v >= 0 for v in signs) or all(v <= 0 for v in signs)):
                raise InversionError(
                    f"La función {f_parsed.plain_text} no es monótona en [{num_a:.4g}, {num_b:.4g}]. "
                    "La inversión a dy no es posible de forma directa. "
                    "Usa el método de Casquillos (shells) en su lugar."
                )
        except InversionError:
            raise
        except Exception:
            pass  # No bloquear si la derivada falla; continuar con la inversión

        new_f_expr = str(f_inv)
        new_g_expr = "0"
        expl_text = (
            f"Despeje analítico: {region.variable} en función de {target_var}.\n"
            f"Curva: {target_var} = {f_parsed.plain_text}  ==>  {region.variable} = {f_inv}\n"
            f"La región queda entre {region.variable} = 0 (eje) y {region.variable} = {f_inv}.\n"
            f"Límites en {target_var}: [{c_num:.4g}, {d_num:.4g}]."
        )
        expl_latex = (
            f"\\text{{Despeje: }} {sympy.latex(from_sym)} = {sympy.latex(f_inv)}"
            f", \\quad \\text{{región: }} 0 \\le {sympy.latex(from_sym)} \\le {sympy.latex(f_inv)}"
        )

    def _to_exact(v: float) -> sympy.Expr:
        """Convierte un float a Rational exacto cuando sea posible, sin el hack :.6f."""
        try:
            # nsimplify busca la fracción exacta más cercana al float
            exact = sympy.nsimplify(v, rational=True, tolerance=1e-9)
            return exact
        except Exception:
            return sympy.Float(v)

    a_sym = _to_exact(c_num)
    b_sym = _to_exact(d_num)

    new_region = Region2D(
        f_expr=new_f_expr,
        g_expr=new_g_expr,
        a=a_sym,
        b=b_sym,
        variable=target_var,
    )
    return new_region, expl_text, expl_latex


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
    """Indica si un método incompatible directamente puede aplicarse mediante inversión analítica."""
    if is_method_compatible(method, axis, region.variable):
        return True
    try:
        target_var = "y" if region.variable == "x" else "x"
        invert_region_to_variable(region, target_var=target_var)
        return True
    except Exception:
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


def _order_curves_by_distance(
    f_sym: sympy.Expr,
    g_sym: sympy.Expr,
    var_sym: sympy.Symbol,
    axis_val: float,
    num_a: float,
    num_b: float,
) -> tuple[sympy.Expr, sympy.Expr, bool, list[str]]:
    """Ordena dos curvas en R_outer y R_inner según su distancia al eje de rotación.

    Returns:
        (r_outer_expr, r_inner_expr, has_inner_void, warnings)
        donde warnings contiene mensajes de advertencia sobre cruces de curvas.
    """
    # Expresiones de distancia exacta respecto al eje
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)

    warnings: list[str] = []

    # Función para evaluar distancia en un punto dado
    def evaluate_distance(dist_expr, x_val):
        try:
            return float(dist_expr.subs(var_sym, x_val).evalf())
        except Exception:
            return None

    # Probar si las distancias son iguales en el punto medio (curvas coincidentes)
    mid_val = sympy.Rational(num_a + num_b, 2)
    try:
        val_f_mid = float(dist_f.subs(var_sym, mid_val).evalf())
        val_g_mid = float(dist_g.subs(var_sym, mid_val).evalf())
        
        if abs(val_f_mid - val_g_mid) < 1e-9:
            warnings.append(
                f"Las curvas f({var_sym}) y g({var_sym}) se cruzan o coinciden en el punto medio "
                f"x = {mid_val.evalf():.3f}. El volumen calculado es una aproximación; "
                f"verifique la región geométrica."
            )
    except Exception:
        pass

    # Buscar cruces resolviendo dist_f(x) = dist_g(x)
    # Esto equivale a |f - axis| = |g - axis|, que tiene dos posibles soluciones:
    # 1. f - axis = g - axis => f = g (cruce de las curvas originales)
    # 2. f - axis = -(g - axis) => f + g = 2*axis (cruce donde distancias son iguales)
    
    # Caso 1: f(x) = g(x). Solo cruces reales ESTRICTAMENTE interiores a (a, b):
    # un cruce en un extremo del intervalo no divide la región (p. ej. y=x con g=0 en [0, 1]).
    # El barrido numérico previo evita sympy.solve cuando no hay cruce (p. ej. sin²x·cos³x + 2
    # tardaba ~36 s en recommend_method) y cuando f o g son un spline (Piecewise).
    try:
        for x_float in _solve_interior_roots(f_sym - g_sym, var_sym, num_a, num_b, (f_sym, g_sym)):
            warnings.append(
                f"¡ADVERTENCIA! Las curvas se cruzan en x = {x_float:.3f} dentro del "
                f"intervalo [{num_a}, {num_b}]. La determinación de la curva exterior "
                f"basada solo en el punto medio puede ser incorrecta. El volumen calculado "
                f"asume que una curva es siempre exterior."
            )
    except Exception:
        pass

    # Caso 2: |f - axis| = |g - axis| donde distancias coinciden pero curvas no son iguales
    if axis_val == 0:  # Eje estándar, simplificación
        eq2 = sympy.Eq(f_sym - g_sym, 0)  # Ya cubierto en caso 1
    else:
        # Para distancias iguales: (f - axis)^2 = (g - axis)^2
        try:
            dist_equal_expr = sympy.expand((f_sym - axis_sym)**2) - sympy.expand((g_sym - axis_sym)**2)
            crosses_dist_equal = _solve_interior_roots(
                dist_equal_expr, var_sym, num_a, num_b, (f_sym, g_sym)
            )

            for x_float in crosses_dist_equal:
                # Descartar las raíces que ya corresponden al caso f = g
                dist_f_at_x = evaluate_distance(dist_f, x_float)
                dist_g_at_x = evaluate_distance(dist_g, x_float)
                if (
                    dist_f_at_x is not None
                    and dist_g_at_x is not None
                    and abs(dist_f_at_x - dist_g_at_x) < 1e-9
                    and abs(
                        (evaluate_distance(f_sym, x_float) or 0.0)
                        - (evaluate_distance(g_sym, x_float) or 0.0)
                    ) < 1e-9
                ):
                    continue
                warnings.append(
                    f"¡ADVERTENCIA! Las curvas tienen igual distancia al eje en "
                    f"x = {x_float:.3f} dentro del intervalo [{num_a}, {num_b}]. "
                    f"La región podría estar autointerseccionada."
                )
        except Exception:
            pass

    # Curva exterior: la que está más lejos del eje en la mayoría de las muestras interiores
    # (no solo en el punto medio, que puede ser una singularidad evitable).
    if _dominates(dist_f, dist_g, var_sym, num_a, num_b):
        r_outer_dist = dist_f
        r_inner_dist = dist_g
    else:
        r_outer_dist = dist_g
        r_inner_dist = dist_f

    # Comprobar si el radio interior es idénticamente cero
    is_inner_zero = r_inner_dist.is_zero or r_inner_dist == 0
    
    return r_outer_dist, r_inner_dist, not is_inner_zero, warnings


def _detect_integration_technique(
    integrand: sympy.Expr,
    var_sym: sympy.Symbol,
) -> tuple[str, str, str]:
    """Detecta y clasifica la técnica de integración más adecuada para el integrando dado.

    Evalúa la estructura algebraica del integrando usando átomos y tipos de SymPy para
    identificar si se requiere: regla de la potencia, sustitución simple, integración
    por partes o sustitución trigonométrica.

    Solo identifica radicales genuinos (sqrt de expresiones NO numéricas y NO simplificables
    a entero) para evitar falsos positivos en polinomios con Abs() residuales.

    Args:
        integrand: Expresión del integrando (expandida o en forma canónica).
        var_sym: Símbolo de la variable de integración.

    Returns:
        Tupla (título_del_paso, explicación_pedagógica, expresión_latex_del_método).
    """
    # Pre-proceso: expandir y limpiar Abs residuales para análisis limpio
    try:
        integrand_clean = sympy.expand(integrand)
    except Exception:
        integrand_clean = integrand

    # 1. Detectar radicales cuadráticos GENUINOS (Pow con exp=1/2, base no numérica)
    #    Filtra Abs(expr)^(1/2) que SymPy puede generar internamente como artefacto.
    sqrt_atoms = []
    for a in integrand_clean.atoms(sympy.Pow):
        if a.exp != sympy.Rational(1, 2):
            continue
        if not a.base.has(var_sym):
            continue
        if a.base.is_number:  # sqrt de constante → no cuenta
            continue
        # Excluir si la base es Abs(expr) — artefacto de _order_curves_by_distance
        if isinstance(a.base, sympy.Abs):
            continue
        # Verificar que no simplifique a racional (ej. sqrt(4) = 2)
        try:
            simplified = sympy.sqrt(a.base)
            if simplified.is_rational:
                continue
        except Exception:
            pass
        sqrt_atoms.append(a)

    if sqrt_atoms:
        title = "Técnica de integración: Sustitución trigonométrica"
        explanation = (
            "El integrando contiene un radical (raíz cuadrada) de una expresión en la variable. "
            "Se analiza la forma del radicando para elegir el cambio de variable trigonométrico "
            "que elimina el radical y convierte la integral en una resoluble directamente:"
        )
        latex = (
            r"\sqrt{a^2 - u^2} \;\Rightarrow\; u = a\sin\theta"
            r"\qquad"
            r"\sqrt{a^2 + u^2} \;\Rightarrow\; u = a\tan\theta"
            r"\qquad"
            r"\sqrt{u^2 - a^2} \;\Rightarrow\; u = a\sec\theta"
        )
        return title, explanation, latex

    # 2. Detectar funciones trigonométricas, exponenciales y logaritmos
    trig_classes = (sympy.sin, sympy.cos, sympy.tan, sympy.cot, sympy.sec, sympy.csc)
    trig_atoms = integrand_clean.atoms(*trig_classes)
    exp_atoms = integrand_clean.atoms(sympy.exp)
    log_atoms = integrand_clean.atoms(sympy.log)
    is_product = isinstance(integrand_clean, sympy.Mul)

    if trig_atoms or exp_atoms or log_atoms:
        if is_product:
            title = "Técnica de integración: Integración por partes"
            explanation = (
                "El integrando es un producto de una función polinomial y una función trascendente "
                "(trigonométrica, exponencial o logarítmica). "
                "Se aplica integración por partes siguiendo la regla mnemotécnica LIATE para elegir u y dv:"
            )
            latex = r"\int u \, dv = uv - \int v \, du"
            return title, explanation, latex
        else:
            title = "Técnica de integración: Sustitución simple"
            explanation = (
                "El integrando contiene una función compuesta (trigonométrica o exponencial). "
                "Se aplica el método de sustitución con el cambio de variable u = g(x):"
            )
            latex = (
                r"\int f(g(x)) \cdot g'(x) \, dx = \int f(u) \, du"
                r"\qquad \text{donde } u = g(x),\; du = g'(x)\,dx"
            )
            return title, explanation, latex

    # 3. Potencias con base compuesta (cadena inversa → sustitución algebraica)
    pow_compound = [
        a for a in integrand_clean.atoms(sympy.Pow)
        if a.exp not in (sympy.S.One, sympy.Rational(1, 2))
        and not a.exp.is_negative
        and a.base.has(var_sym)
        and a.base != var_sym
        and not a.base.is_number
        and not isinstance(a.base, sympy.Abs)
    ]
    if pow_compound:
        base_expr = pow_compound[0].base
        deriv_base = sympy.diff(base_expr, var_sym)
        title = "Técnica de integración: Sustitución simple"
        explanation = (
            "El integrando contiene una expresión compuesta elevada a una potencia (regla de la cadena inversa). "
            f"Se aplica el cambio de variable u = {sympy.latex(base_expr)} para convertir la integral:"
        )
        latex = (
            r"\int f(g(x)) \cdot g'(x) \, dx = \int f(u) \, du"
            rf"\qquad \text{{donde }} u = {sympy.latex(base_expr)},\; du = {sympy.latex(deriv_base)}\,dx"
        )
        return title, explanation, latex

    # 4. Caso general: polinomio / regla de la potencia
    title = "Técnica de integración: Regla de la potencia"
    explanation = (
        "El integrando es un polinomio o una suma de monomios con potencias enteras de la variable. "
        "Se aplica la regla de la potencia a cada término por separado:"
    )
    latex = r"\int x^n \, dx = \frac{x^{n+1}}{n+1} + C \qquad (n \neq -1)"
    return title, explanation, latex


def _clean_latex(s: object) -> str:
    """Convierte una expresion SymPy o cadena LaTeX a string LaTeX limpio.

    Acepta tanto str como objetos SymPy. Cuando recibe un objeto
    SymPy lo convierte con sympy.latex() antes de aplicar las
    transformaciones de presentacion.

    Args:
        s: Cadena LaTeX o expresion SymPy.

    Returns:
        Cadena LaTeX lista para presentacion pedagogica.
    """
    import re as _re
    import sympy as _sp
    if not isinstance(s, str):
        try:
            s_str: str = _sp.latex(s)
        except Exception:
            s_str = str(s)
    else:
        s_str = s
    s_str = s_str.replace(r'\left|', r'\left(').replace(r'\right|', r'\right)')
    s_str = _re.sub(r'\\operatorname\{Abs\}\\left\(', r'\\left(', s_str)
    s_str = _re.sub(r'\\text\{Abs\}\(', r'(', s_str)
    return s_str


def _build_volume_steps(
    method: SolidMethod,
    region: Region2D,
    axis: RevolutionAxis,
    var_sym: sympy.Symbol,
    sym_a: sympy.Expr,
    sym_b: sympy.Expr,
    integrand_core: sympy.Expr,
    vol_sym: sympy.Expr,
    num_val: float | None,
    r_outer: sympy.Expr | None = None,
    r_inner: sympy.Expr | None = None,
    shell_radius: sympy.Expr | None = None,
    shell_height: sympy.Expr | None = None,
) -> list[SolutionStep]:
    """Construye la lista pedagógica de pasos analíticos intermedios con explicaciones didácticas."""
    try:
        var = region.variable
        integrand_core_expanded = sympy.expand(integrand_core)
        antiderivative = sympy.integrate(integrand_core_expanded, var_sym)

        eval_b = sympy.simplify(antiderivative.subs(var_sym, sym_b))
        eval_a = sympy.simplify(antiderivative.subs(var_sym, sym_a))
        diff_eval = sympy.simplify(eval_b - eval_a)

        # Helper: limpia LaTeX generado por SymPy de valores absolutos residuales
        def cl(expr: sympy.Expr) -> str:
            return _clean_latex(sympy.latex(expr))

        steps: list[SolutionStep] = []

        if method == SolidMethod.DISKS:
            r = r_outer if r_outer is not None else sympy.Symbol("R")
            steps.append(
                SolutionStep(
                    step_number=1,
                    title="1. Identificación del radio del disco",
                    explanation=(
                        f"¡Listo parce! Lo primero es identificar de qué tamaño son los discazos que vamos a ir apilando. "
                        f"Cuando giramos la región alrededor del eje {axis.label}, cada corte perpendicular a ese eje "
                        f"nos genera un disco sólido. El radio R({var}) de ese disco es la distancia entre la curva y el eje de giro. "
                        f"Ojo: ese radio siempre debe ser positivo, así que nos aseguramos de tomar la distancia correcta."
                    ),
                    expression_plain_text=f"R({var}) = {r}",
                    expression_latex=_clean_latex(f"R({var}) = {cl(r)}"),
                )
            )
            steps.append(
                SolutionStep(
                    step_number=2,
                    title="2. Planteamiento de la integral del volumen",
                    explanation=(
                        f"De una. El área de cada disco es A = π·R², y su espesor es d{var}. "
                        f"Entonces el volumen diferencial es dV = π·[R({var})]²·d{var}. "
                        f"Solo queda sumar (integrar) todos esos discazos a lo largo del intervalo [{sym_a}, {sym_b}]. "
                        f"Eso nos da la integral que vamos a resolver paso a paso, parcero."
                    ),
                    expression_plain_text=f"V = pi * int_({sym_a})^({sym_b}) [R({var})]^2 d{var}",
                    expression_latex=_clean_latex(
                        f"V = \\pi \\int_{{{cl(sym_a)}}}^{{{cl(sym_b)}}}"
                        f" \\left[{cl(r)}\\right]^2 \\, d{var}"
                    ),
                )
            )
            steps.append(
                SolutionStep(
                    step_number=3,
                    title="3. Expansión y simplificación del integrando",
                    explanation=(
                        "Antes de integrar hay que simplificar ese chicharrón algebraico. "
                        "Elevamos al cuadrado el radio y usamos álgebra para romper los paréntesis "
                        "y obtener una suma de monomios ordenados. "
                        "Así la integral se vuelve supermanejable, término a término. ¡Sin estrés!"
                    ),
                    expression_plain_text=f"[R({var})]^2 = {integrand_core_expanded}",
                    expression_latex=_clean_latex(
                        f"\\left[{cl(r)}\\right]^2 = {cl(integrand_core_expanded)}"
                    ),
                )
            )

        elif method == SolidMethod.WASHERS:
            r_out = r_outer if r_outer is not None else sympy.Symbol("R_ext")
            r_in = r_inner if r_inner is not None else sympy.Symbol("R_int")
            steps.append(
                SolutionStep(
                    step_number=1,
                    title="1. Identificación de radios exterior e interior",
                    explanation=(
                        f"¡Ojo acá, parcero! Como la región tiene dos curvas que la delimitan, "
                        f"al girar alrededor del eje {axis.label} los cortes no son discos sólidos sino "
                        f"arandelas (como una rosca o un aro). Necesitamos dos radios: "
                        f"el externo R_ext({var}) (el más alejado del eje) y el interno R_int({var}) (el más cercano). "
                        f"No los cruce, we, o el volumen le sale negativo."
                    ),
                    expression_plain_text=f"R_ext({var}) = {r_out},  R_int({var}) = {r_in}",
                    expression_latex=_clean_latex(
                        f"R_{{\\text{{ext}}}}({var}) = {cl(r_out)}, \\quad R_{{\\text{{int}}}}({var}) = {cl(r_in)}"
                    ),
                )
            )
            steps.append(
                SolutionStep(
                    step_number=2,
                    title="2. Planteamiento de la integral del volumen",
                    explanation=(
                        f"Acuérdese de la clase: el área de una arandela es π(R_ext² − R_int²). "
                        f"Esto viene de restar el área del disco chiquito al del grande. "
                        f"Multiplicamos por d{var} para tener el volumen diferencial y luego integramos "
                        f"en [{sym_a}, {sym_b}]. ¡De una vez coronamos el planteamiento!"
                    ),
                    expression_plain_text=f"V = pi * int_({sym_a})^({sym_b}) ([R_ext]^2 - [R_int]^2) d{var}",
                    expression_latex=_clean_latex(
                        f"V = \\pi \\int_{{{cl(sym_a)}}}^{{{cl(sym_b)}}}"
                        f" \\left( \\left[{cl(r_out)}\\right]^2"
                        f" - \\left[{cl(r_in)}\\right]^2 \\right) d{var}"
                    ),
                )
            )
            steps.append(
                SolutionStep(
                    step_number=3,
                    title="3. Expansión y resta de los radios al cuadrado",
                    explanation=(
                        "Le metemos álgebra al asunto: elevamos al cuadrado cada radio y restamos. "
                        "El objetivo es dejar el integrando como un polinomio o función reconocible "
                        "para poder aplicar las técnicas de integración que ya conocemos. "
                        "¡Sin miedo, parcero, esto es solo carpintería algebraica!"
                    ),
                    expression_plain_text=f"R_ext^2 - R_int^2 = {integrand_core_expanded}",
                    expression_latex=_clean_latex(
                        f"R_{{\\text{{ext}}}}^2 - R_{{\\text{{int}}}}^2 = {cl(integrand_core_expanded)}"
                    ),
                )
            )

        elif method == SolidMethod.SHELLS:
            p = shell_radius if shell_radius is not None else sympy.Symbol("p")
            h = shell_height if shell_height is not None else sympy.Symbol("h")
            steps.append(
                SolutionStep(
                    step_number=1,
                    title="1. Planteamiento geométrico del casquillo cilíndrico",
                    explanation=(
                        f"En este caso usamos casquillos cilíndricos: imagínese que en vez de cortar el sólido en "
                        f"discos, lo pelamos como una cebolla en capas concéntricas. "
                        f"Cada capa tiene radio medio p({var}) (su distancia al eje {axis.label}) "
                        f"y altura h({var}) (qué tan alto es ese cilindrito). ¡Así de sencillo!"
                    ),
                    expression_plain_text=f"p({var}) = {p},  h({var}) = {h}",
                    expression_latex=_clean_latex(
                        f"p({var}) = {cl(p)}, \\quad h({var}) = {cl(h)}"
                    ),
                )
            )
            steps.append(
                SolutionStep(
                    step_number=2,
                    title="2. Planteamiento de la integral del volumen",
                    explanation=(
                        f"Si 'desplegamos' el casquillo como una lámina, obtenemos un rectángulo de área "
                        f"2π·p·h. Multiplicamos por d{var} y tenemos el volumen diferencial dV = 2π·p({var})·h({var})·d{var}. "
                        f"Integramos en [{sym_a}, {sym_b}] y listo el pollo, we."
                    ),
                    expression_plain_text=f"V = 2*pi * int_({sym_a})^({sym_b}) p({var}) * h({var}) d{var}",
                    expression_latex=_clean_latex(
                        f"V = 2\\pi \\int_{{{cl(sym_a)}}}^{{{cl(sym_b)}}}"
                        f" \\left({cl(p)}\\right) \\left({cl(h)}\\right) d{var}"
                    ),
                )
            )
            steps.append(
                SolutionStep(
                    step_number=3,
                    title="3. Expansión algebraica del producto radio-altura",
                    explanation=(
                        "Expandimos el producto radio por altura para simplificar el integrando. "
                        "Así nos queda una función más manejable pa' integrar. "
                        "¡Dele con confianza, esto es álgebra básica!"
                    ),
                    expression_plain_text=f"p({var}) * h({var}) = {integrand_core_expanded}",
                    expression_latex=_clean_latex(
                        f"p({var}) \\cdot h({var}) = {cl(integrand_core_expanded)}"
                    ),
                )
            )

        # ── Paso 4: Identificación de la técnica de integración ─────────────────
        tech_title, tech_explanation, tech_latex = _detect_integration_technique(
            integrand_core_expanded, var_sym
        )
        steps.append(
            SolutionStep(
                step_number=4,
                title=f"4. {tech_title}",
                explanation=tech_explanation,
                expression_plain_text=tech_title,
                expression_latex=tech_latex,
            )
        )

        # ── Pasos comunes: Antiderivada, TFC y Resultado ────────────────────────
        factor_str = "2·π" if method == SolidMethod.SHELLS else "π"
        factor_latex = "2\\pi" if method == SolidMethod.SHELLS else "\\pi"

        steps.append(
            SolutionStep(
                step_number=5,
                title="5. Obtención de la antiderivada (Primitiva F)",
                explanation=(
                    f"¡Breve! Aplicamos la técnica identificada en el paso anterior para encontrar "
                    f"la primitiva F({var}). Recuerde: la primitiva es la función cuya derivada es nuestro integrando. "
                    f"Por la regla de la potencia: ∫xⁿ dx = xⁿ⁺¹/(n+1) + C. Resolvemos término a término, parcero."
                ),
                expression_plain_text=f"F({var}) = ∫({integrand_core_expanded}) d{var} = {antiderivative}",
                expression_latex=_clean_latex(
                    f"F({var}) = \\int \\left({cl(integrand_core_expanded)}\\right) d{var}"
                    f" = {cl(antiderivative)}"
                ),
            )
        )

        steps.append(
            SolutionStep(
                step_number=6,
                title="6. Evaluación en los límites — Teorema Fundamental del Cálculo",
                explanation=(
                    f"Ahora aplicamos el Teorema Fundamental del Cálculo (el más importante del semestre, parcero). "
                    f"Evaluamos la primitiva en el límite superior {sym_b} y le restamos la evaluación "
                    f"en el límite inferior {sym_a}. Es pura carpintería: enchufar los números y restar. "
                    f"¡Sin errores de signo, que ese es el error más común en parciales!"
                ),
                expression_plain_text=(
                    f"F({sym_b}) = {eval_b}\n"
                    f"F({sym_a}) = {eval_a}\n"
                    f"F({sym_b}) - F({sym_a}) = {diff_eval}"
                ),
                expression_latex=_clean_latex(
                    f"\\int_{{{cl(sym_a)}}}^{{{cl(sym_b)}}} f({var})\\,d{var}"
                    f" = F({cl(sym_b)}) - F({cl(sym_a)})"
                    f" = {cl(eval_b)} - {cl(eval_a)}"
                    f" = {cl(diff_eval)}"
                ),
            )
        )

        approx_text = f" ≈ {num_val:.5f} u³" if num_val is not None else ""
        steps.append(
            SolutionStep(
                step_number=7,
                title="7. Volumen final — multiplicación por la constante de revolución",
                explanation=(
                    f"Por último, multiplicamos la diferencia obtenida por el factor {factor_str} "
                    f"(que proviene de la fórmula del método, viene de rotar 2π radianes alrededor del eje). "
                    f"¡Eso es todo, we! Ahí está el resultado exacto y su aproximación decimal. "
                    f"Ya puede escribirlo en el parcial con toda la seguridad."
                ),
                expression_plain_text=f"V = {factor_str} · ({diff_eval}) = {vol_sym}{approx_text}",
                expression_latex=_clean_latex(
                    f"V = {factor_latex} \\cdot \\left({cl(diff_eval)}\\right) = {cl(vol_sym)}"
                ),
            )
        )

        return steps
    except Exception:
        return []




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

        r_outer, r_inner, has_void, warnings_from_curves = _order_curves_by_distance(
            f_parsed.sympy_expr,
            g_parsed.sympy_expr,
            var_sym,
            axis.position,
            num_a,
            num_b,
        )

        # Construir mensaje de advertencia si hay cruces de curvas
        cross_warnings = ""
        if warnings_from_curves:
            cross_warnings = (
                f"\n⚠️  **ADVERTENCIA DE CÁLCULO**\n"
                f"Las curvas se cruzan dentro del intervalo [{num_a}, {num_b}]. El volumen calculado "
                f"asume que una curva es siempre exterior (basado en el punto medio). "
                f"Esto puede dar un valor incorrecto si el cruce ocurre cerca de los límites."
            )

        def _sq(e: sympy.Expr) -> sympy.Expr:
            if isinstance(e, sympy.Abs):
                return e.args[0]**2
            return e**2

        if has_void:
            integrand_core = _sq(r_outer) - _sq(r_inner)
            chosen_method = SolidMethod.WASHERS
        else:
            integrand_core = _sq(r_outer)
            chosen_method = SolidMethod.DISKS

        integrand = sympy.pi * integrand_core
        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        num_val = _numeric_value(vol_sym)
        if num_val is None:
            num_val = numeric_volume(region, axis)

        # Detectar resultado no finito (integral divergente o dominio imaginario)
        import math as _math
        if num_val is not None and not _math.isfinite(num_val):
            return VolumeResult(
                method=chosen_method,
                is_success=False,
                error_message=(
                    "La integral del volumen no converge (resultado no finito). "
                    "Verifique que la función esté definida y sea real en todo el intervalo."
                ),
            )

        steps = _build_volume_steps(
            method=chosen_method,
            region=region,
            axis=axis,
            var_sym=var_sym,
            sym_a=sym_a,
            sym_b=sym_b,
            integrand_core=integrand_core,
            vol_sym=vol_sym,
            num_val=num_val,
            r_outer=r_outer,
            r_inner=r_inner if has_void else None,
        )

        return VolumeResult(
            method=chosen_method,
            exact_plain_text=str(vol_sym),
            exact_latex=_clean_latex(sympy.latex(vol_sym)),
            numeric_value=num_val,
            integrand_plain_text=str(integrand),
            integrand_latex=_clean_latex(sympy.latex(integrand)),
            integral_setup_latex=_clean_latex(
                f"\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}}"
                + (
                    f" \\left({sympy.latex(r_outer**2)} - {sympy.latex(r_inner**2)}\\right) d{region.variable}"
                    if has_void
                    else f" \\left({sympy.latex(r_outer**2)}\\right) d{region.variable}"
                )
            ),
            is_success=True,
            steps=steps,
            warnings=warnings_from_curves if warnings_from_curves else [],
        )
    except Exception as exc:
        return VolumeResult(
            method=SolidMethod.DISKS,
            is_success=False,
            error_message=str(exc),
        )



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


def partition_washer_intervals(
    f_sym: sympy.Expr,
    g_sym: sympy.Expr,
    var_sym: sympy.Symbol,
    axis_val: float,
    num_a: float,
    num_b: float,
    sym_a: sympy.Expr,
    sym_b: sympy.Expr,
) -> list[dict[str, Any]]:
    """Subdivide el intervalo [a, b] en subintervalos con orden R_ext >= R_int uniforme."""
    crossings = find_curve_crossings(
        f_sym, g_sym, var_sym, axis_val, num_a, num_b, method=SolidMethod.WASHERS
    )
    bounds = [(num_a, sym_a)] + crossings + [(num_b, sym_b)]
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)

    intervals = []
    for i in range(len(bounds) - 1):
        t0_num, t0_sym = bounds[i]
        t1_num, t1_sym = bounds[i + 1]
        if _dominates(dist_f, dist_g, var_sym, t0_num, t1_num):
            r_out = dist_f
            r_in = dist_g
            core = (f_sym - axis_sym)**2 - (g_sym - axis_sym)**2
            f_is_outer = True
        else:
            r_out = dist_g
            r_in = dist_f
            core = (g_sym - axis_sym)**2 - (f_sym - axis_sym)**2
            f_is_outer = False

        intervals.append({
            "t0_num": t0_num,
            "t1_num": t1_num,
            "t0_sym": t0_sym,
            "t1_sym": t1_sym,
            "r_outer": r_out,
            "r_inner": r_in,
            "core": core,
            "f_is_outer": f_is_outer,
        })
    return intervals


def _build_piecewise_washer_steps(
    region: Region2D,
    axis: RevolutionAxis,
    var_sym: sympy.Symbol,
    intervals: list[dict[str, Any]],
    vol_partials: list[sympy.Expr],
    vol_sym: sympy.Expr,
    num_val: float | None,
) -> list[SolutionStep]:
    """Genera el desarrollo pedagógico por tramos cuando las curvas se cruzan."""
    var = region.variable
    cl = _clean_latex
    steps: list[SolutionStep] = []

    # Paso 1: Puntos de intersección
    cross_points = [it["t1_sym"] for it in intervals[:-1]]
    cross_str = ", ".join(f"{var} = {p}" for p in cross_points)
    steps.append(
        SolutionStep(
            step_number=1,
            title="1. Detección de intersecciones y división por tramos",
            explanation=(
                f"Las curvas frontera se intersecan en {cross_str} dentro del intervalo "
                f"[{region.a}, {region.b}]. Para calcular el volumen geométrico sin que "
                f"las regiones se resten incorrectamente, dividimos el dominio en "
                f"{len(intervals)} subintervalos."
            ),
            expression_plain_text=f"Intersección en: {cross_str}",
            expression_latex=cl(rf"\text{{Intersección en: }}\; {cross_str}"),
        )
    )

    # Paso 2: Radios por tramo
    explanations = []
    latex_parts = []
    for idx, it in enumerate(intervals):
        r_out_name = f"f({var})" if it.get("f_is_outer", True) else f"g({var})"
        r_in_name = f"g({var})" if it.get("f_is_outer", True) else f"f({var})"
        explanations.append(
            f"En [{it['t0_sym']}, {it['t1_sym']}]: {r_out_name} queda en el exterior y {r_in_name} en el interior."
        )
        latex_parts.append(
            rf"I_{{{idx+1}}} = [{cl(it['t0_sym'])}, {cl(it['t1_sym'])}]: "
            rf"R_{{ext}} = {cl(it['r_outer'])},\; r_{{int}} = {cl(it['r_inner'])}"
        )

    steps.append(
        SolutionStep(
            step_number=2,
            title="2. Radios exterior e interior en cada subintervalo",
            explanation=" ".join(explanations),
            expression_plain_text="; ".join(explanations),
            expression_latex=cl(r" \quad ".join(latex_parts)),
        )
    )

    # Paso 3: Planteamiento por tramos
    setup_latex_list = [
        rf"\pi \int_{{{cl(it['t0_sym'])}}}^{{{cl(it['t1_sym'])}}} \left( {cl(it['core'])} \right) d{var}"
        for it in intervals
    ]
    steps.append(
        SolutionStep(
            step_number=3,
            title="3. Planteamiento de la integral de volumen por tramos",
            explanation=(
                "El volumen total es la suma de los volúmenes de revolución de cada subintervalo: "
                "V = V₁ + V₂ + ..."
            ),
            expression_plain_text=" + ".join(f"V_{i+1}" for i in range(len(intervals))),
            expression_latex=cl(r"V = " + " + ".join(setup_latex_list)),
        )
    )

    # Paso 4: Evaluación de cada tramo
    eval_texts = []
    eval_latex = []
    for idx, (it, vp) in enumerate(zip(intervals, vol_partials)):
        eval_texts.append(f"V_{idx+1} = {vp}")
        eval_latex.append(rf"V_{{{idx+1}}} = {cl(vp)}")

    steps.append(
        SolutionStep(
            step_number=4,
            title="4. Cálculo de cada integral definida",
            explanation="Integramos y evaluamos en los límites correspondientes de cada subintervalo.",
            expression_plain_text="; ".join(eval_texts),
            expression_latex=cl(r" \quad ".join(eval_latex)),
        )
    )

    # Paso 5: Suma y resultado final
    approx_text = f" ≈ {num_val:.5f} u³" if num_val is not None else ""
    steps.append(
        SolutionStep(
            step_number=5,
            title="5. Volumen total final (suma de tramos)",
            explanation="Sumamos el volumen aportado por cada tramo para obtener el volumen geométrico total exacto.",
            expression_plain_text=f"V = {' + '.join(str(vp) for vp in vol_partials)} = {vol_sym}{approx_text}",
            expression_latex=cl(rf"V = {' + '.join(sympy.latex(vp) for vp in vol_partials)} = {sympy.latex(vol_sym)}"),
        )
    )

    return steps


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

        intervals = partition_washer_intervals(
            f_parsed.sympy_expr,
            g_parsed.sympy_expr,
            var_sym,
            axis.position,
            num_a,
            num_b,
            sym_a,
            sym_b,
        )
        has_crossings = len(intervals) > 1

        if not has_crossings:
            t_info = intervals[0]
            r_outer = t_info["r_outer"]
            r_inner = t_info["r_inner"]
            integrand_core = t_info["core"]
            integrand = sympy.pi * integrand_core
            vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))
            num_val = _numeric_value(vol_sym)
            if num_val is None:
                num_val = numeric_volume(region, axis)

            steps = _build_volume_steps(
                method=SolidMethod.WASHERS,
                region=region,
                axis=axis,
                var_sym=var_sym,
                sym_a=sym_a,
                sym_b=sym_b,
                integrand_core=integrand_core,
                vol_sym=vol_sym,
                num_val=num_val,
                r_outer=r_outer,
                r_inner=r_inner,
            )

            return VolumeResult(
                method=SolidMethod.WASHERS,
                exact_plain_text=str(vol_sym),
                exact_latex=_clean_latex(sympy.latex(vol_sym)),
                numeric_value=num_val,
                integrand_plain_text=str(integrand),
                integrand_latex=_clean_latex(sympy.latex(integrand)),
                integral_setup_latex=_clean_latex(
                    rf"\pi \int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} "
                    rf"\left[ {sympy.latex(r_outer)}^2 - {sympy.latex(r_inner)}^2 \right] d{region.variable}"
                ),
                is_success=True,
                steps=steps,
                warnings=[],
            )
        else:
            vol_partials = []
            setup_parts = []
            for item in intervals:
                sub_a_sym = item["t0_sym"]
                sub_b_sym = item["t1_sym"]
                core_j = item["core"]
                v_j = sympy.integrate(sympy.pi * core_j, (var_sym, sub_a_sym, sub_b_sym))
                vol_partials.append(v_j)
                setup_parts.append(
                    rf"\pi \int_{{{sympy.latex(sub_a_sym)}}}^{{{sympy.latex(sub_b_sym)}}} "
                    rf"\left[ {sympy.latex(item['r_outer'])}^2 - {sympy.latex(item['r_inner'])}^2 \right] d{region.variable}"
                )

            vol_sym = sympy.simplify(sum(vol_partials))
            num_val = _numeric_value(vol_sym)
            if num_val is None:
                num_val = numeric_volume(region, axis)

            setup_latex = _clean_latex(" + ".join(setup_parts))
            steps = _build_piecewise_washer_steps(
                region=region,
                axis=axis,
                var_sym=var_sym,
                intervals=intervals,
                vol_partials=vol_partials,
                vol_sym=vol_sym,
                num_val=num_val,
            )

            cross_warn = [
                f"Las curvas se cruzan dentro del intervalo [{num_a}, {num_b}]. La región se dividió "
                f"en {len(intervals)} subintervalos para calcular el volumen geométrico exacto por tramos."
            ]

            return VolumeResult(
                method=SolidMethod.WASHERS,
                exact_plain_text=str(vol_sym),
                exact_latex=_clean_latex(sympy.latex(vol_sym)),
                numeric_value=num_val,
                integrand_plain_text=" + ".join(str(sympy.pi * it["core"]) for it in intervals),
                integrand_latex=setup_latex,
                integral_setup_latex=setup_latex,
                is_success=True,
                steps=steps,
                warnings=cross_warn,
            )
    except Exception as exc:
        return VolumeResult(
            method=SolidMethod.WASHERS,
            is_success=False,
            error_message=str(exc),
        )


def _build_piecewise_shell_steps(
    region: Region2D,
    radius_expr: sympy.Expr,
    pieces: list[tuple[sympy.Expr, sympy.Expr, sympy.Expr]],
    top_is_f: list[bool],
    vol_partials: list[sympy.Expr],
    vol_sym: sympy.Expr,
    num_val: float | None,
) -> list[SolutionStep]:
    """Desarrollo pedagógico de casquillos cuando las curvas se cruzan (un tramo por orientación)."""
    var = region.variable
    cl = _clean_latex

    def height_latex(h: sympy.Expr, f_on_top: bool) -> str:
        if h.has(sympy.Piecewise):  # repetir un spline completo en cada tramo lo haría ilegible
            return "f(x) - g(x)" if f_on_top else "g(x) - f(x)"
        return sympy.latex(h)

    cuts = [t1 for _t0, t1, _h in pieces[:-1]]
    cuts_text = ", ".join(f"{var} = {c}" for c in cuts)
    setup = [
        rf"2\pi \int_{{{sympy.latex(t0)}}}^{{{sympy.latex(t1)}}} {sympy.latex(radius_expr)}\left({height_latex(h, top)}\right) d{var}"
        for (t0, t1, h), top in zip(pieces, top_is_f)
    ]
    approx_text = f" ≈ {num_val:.5f} u³" if num_val is not None else ""
    return [
        SolutionStep(
            step_number=1,
            title="1. Detección de intersecciones y división por tramos",
            explanation=(
                f"Las curvas se cruzan en {cuts_text} dentro de [{region.a}, {region.b}]. La altura del "
                f"casquillo es |f − g|, así que se integra en {len(pieces)} tramos, cada uno con la curva "
                "de arriba menos la de abajo."
            ),
            expression_plain_text=f"Intersección en: {cuts_text}",
            expression_latex=cl(rf"\text{{Intersección en: }}\; {cuts_text}"),
        ),
        SolutionStep(
            step_number=2,
            title="2. Planteamiento de la integral de volumen por tramos",
            explanation="El volumen total es la suma de los volúmenes de cada tramo: V = V₁ + V₂ + ...",
            expression_plain_text=" + ".join(f"V_{i + 1}" for i in range(len(pieces))),
            expression_latex=cl("V = " + " + ".join(setup)),
        ),
        SolutionStep(
            step_number=3,
            title="3. Cálculo de cada integral definida",
            explanation="Integramos y evaluamos en los límites de cada tramo.",
            expression_plain_text="; ".join(f"V_{i + 1} = {vp}" for i, vp in enumerate(vol_partials)),
            expression_latex=cl(r" \quad ".join(rf"V_{{{i + 1}}} = {sympy.latex(vp)}" for i, vp in enumerate(vol_partials))),
        ),
        SolutionStep(
            step_number=4,
            title="4. Volumen total final (suma de tramos)",
            explanation="Sumamos el volumen de cada tramo para obtener el volumen total.",
            expression_plain_text=f"V = {vol_sym}{approx_text}",
            expression_latex=cl(rf"V = {sympy.latex(vol_sym)}"),
        ),
    ]


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

        # Altura del casquillo: |f − g|. Si las curvas se cruzan dentro de (a, b), se integra por
        # tramos con la orientación correcta en cada uno. Antes se usaba (f − g) o (g − f) según el
        # punto medio para TODO el intervalo: con f = x, g = x² en [0, 2] y eje Y daba −8π/3 en
        # lugar de 3π, marcado como éxito.
        f_expr, g_expr = f_parsed.sympy_expr, g_parsed.sympy_expr
        warnings_from_curves: list[str] = []
        crossings = find_curve_crossings(
            f_expr, g_expr, var_sym, axis.position, num_a, num_b, method=SolidMethod.SHELLS
        )
        bounds = [(num_a, sym_a)] + crossings + [(num_b, sym_b)]
        pieces: list[tuple[sympy.Expr, sympy.Expr, sympy.Expr]] = []
        orientation: list[bool] = []
        for (t0_num, t0_sym), (t1_num, t1_sym) in zip(bounds, bounds[1:]):
            top_is_f = _dominates(f_expr, g_expr, var_sym, t0_num, t1_num)
            orientation.append(top_is_f)
            pieces.append((t0_sym, t1_sym, (f_expr - g_expr) if top_is_f else (g_expr - f_expr)))

        vol_partials = [
            sympy.integrate(2 * sympy.pi * radius_expr * h, (var_sym, t0, t1)) for t0, t1, h in pieces
        ]
        vol_sym = sympy.Add(*vol_partials)
        num_val = _numeric_value(vol_sym)
        if num_val is None:
            num_val = numeric_volume(region, axis)

        if len(pieces) == 1:
            height_expr = pieces[0][2]
            integrand_core = radius_expr * height_expr
            steps = _build_volume_steps(
                method=SolidMethod.SHELLS,
                region=region,
                axis=axis,
                var_sym=var_sym,
                sym_a=sym_a,
                sym_b=sym_b,
                integrand_core=integrand_core,
                vol_sym=vol_sym,
                num_val=num_val,
                shell_radius=radius_expr,
                shell_height=height_expr,
            )
        else:
            height_expr = sympy.Abs(f_expr - g_expr)
            integrand_core = radius_expr * height_expr
            warnings_from_curves.append(
                f"Las curvas se cruzan dentro del intervalo [{num_a}, {num_b}]. La altura del casquillo es "
                f"|f − g| y la integral se dividió en {len(pieces)} tramos."
            )
            # Desarrollo por tramos: el desarrollo genérico re-integraba x·|f − g| con SymPy, y con
            # un spline (Piecewise) tardaba ~135 s de los ~139 s del cálculo.
            steps = _build_piecewise_shell_steps(
                region, radius_expr, pieces, orientation, vol_partials, vol_sym, num_val
            )
        integrand = 2 * sympy.pi * integrand_core

        return VolumeResult(
            method=SolidMethod.SHELLS,
            exact_plain_text=str(vol_sym),
            exact_latex=_clean_latex(sympy.latex(vol_sym)),
            numeric_value=num_val,
            integrand_plain_text=str(integrand),
            integrand_latex=_clean_latex(sympy.latex(integrand)),
            integral_setup_latex=(
                steps[1].expression_latex.removeprefix("V = ")  # suma por tramos: _clean_latex quitaría |f − g|
                if len(pieces) > 1
                else _clean_latex(
                    f"2\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} "
                    f"\\left({sympy.latex(radius_expr)}\\right) \\left({sympy.latex(height_expr)}\\right) d{region.variable}"
                )
            ),
            is_success=True,
            steps=steps,
            warnings=warnings_from_curves if warnings_from_curves else [],
        )
    except Exception as exc:
        return VolumeResult(
            method=SolidMethod.SHELLS,
            is_success=False,
            error_message=str(exc),
        )


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

    f = _ensure_parsed(region.f_expr).sympy_expr
    g = _ensure_parsed(region.g_expr, default_zero=True).sympy_expr
    var = sympy.Symbol(region.variable)
    a, b, _sa, _sb = _evaluate_bounds(region.a, region.b)
    k = sympy.nsimplify(axis.position)
    if axis.orientation is AxisOrientation.VERTICAL:  # cortes en x: casquillos
        core = 2 * sympy.pi * sympy.Abs(var - k) * sympy.Abs(f - g)
        method = SolidMethod.SHELLS
    else:  # eje horizontal: arandelas
        core = sympy.pi * sympy.Abs((f - k) ** 2 - (g - k) ** 2)
        method = SolidMethod.WASHERS
    cuts = [float(t) for t, _ in find_curve_crossings(f, g, var, axis.position, a, b, method=method)]
    nodes = sorted({a, b, *cuts, *np.linspace(a, b, 17).tolist()})
    val = mpmath.quad(sympy.lambdify(var, core, "mpmath"), nodes)
    return float(val) if mpmath.isfinite(val) else None


def _cross_check(res: VolumeResult, region: Region2D, axis: RevolutionAxis) -> VolumeResult:
    """Rechaza un volumen simbólico proveniente de inversión que no coincide con la cuadratura independiente."""
    if not res.is_success or res.numeric_value is None:
        return res
    ref = numeric_volume(region, axis)
    if ref is None or math.isclose(res.numeric_value, ref, rel_tol=1e-5, abs_tol=1e-7):
        return res
    return VolumeResult(
        method=res.method,
        is_success=False,
        error_message=(
            f"El planteamiento invertido da {res.numeric_value:.6g}, pero la cuadratura da "
            f"{ref:.6g}. Use el método directo para este eje."
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
    """Función de alto nivel para calcular el volumen según el método seleccionado o recomendado.

    Si el método solicitado requiere cortes en la otra variable (por ejemplo, Discos/Arandelas
    en eje vertical o Casquillos en eje horizontal) y allow_inversion es True, invierte analíticamente
    la región mediante SymPy para resolver la integral en dy.

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

    # Si no es compatible directamente con la variable actual
    if not is_method_compatible(method, axis, region.variable):
        if allow_inversion:
            target_var = "y" if region.variable == "x" else "x"
            try:
                inv_region, expl_text, expl_latex = invert_region_to_variable(region, target_var=target_var)
                sub_method = method
                res = calculate_revolution_volume(
                    inv_region, axis, method=sub_method, allow_inversion=False, _check_axis=False
                )
                if res.is_success:
                    inversion_step = SolutionStep(
                        step_number=1,
                        title=f"Despeje e inversión analítica de variables (integración en d{target_var})",
                        explanation=(
                            f"Para aplicar el método de {method.value} respecto al eje {axis.label}, "
                            f"los cortes analíticos deben formularse respecto a la variable '{target_var}'. "
                            f"Despejamos analíticamente con SymPy:\n{expl_text}"
                        ),
                        expression_plain_text=expl_text,
                        expression_latex=expl_latex,
                    )
                    new_steps = [inversion_step]
                    for s in res.steps:
                        new_steps.append(
                            SolutionStep(
                                step_number=len(new_steps) + 1,
                                title=s.title,
                                explanation=s.explanation,
                                expression_plain_text=s.expression_plain_text,
                                expression_latex=s.expression_latex,
                            )
                        )
                    return _cross_check(_reject_negative(VolumeResult(
                        method=method,
                        exact_plain_text=res.exact_plain_text,
                        exact_latex=res.exact_latex,
                        numeric_value=res.numeric_value,
                        integrand_plain_text=res.integrand_plain_text,
                        integrand_latex=res.integrand_latex,
                        integral_setup_latex=res.integral_setup_latex,
                        is_success=True,
                        steps=new_steps,
                        warnings=res.warnings,
                    )), region, axis)
                return res
            except InversionError as err:
                return VolumeResult(
                    method=method,
                    is_success=False,
                    error_message=str(err),
                )
        else:
            return VolumeResult(
                method=method,
                is_success=False,
                error_message=(
                    f"El método {method.value} no es compatible directamente con el eje {axis.label} "
                    f"para la variable '{region.variable}'."
                ),
            )

    if method == SolidMethod.DISKS:
        return _reject_negative(calculate_disk_volume(region, axis))
    elif method == SolidMethod.WASHERS:
        return _reject_negative(calculate_washer_volume(region, axis))
    elif method == SolidMethod.SHELLS:
        return _reject_negative(calculate_shell_volume(region, axis))
    else:
        return VolumeResult(
            method=SolidMethod.DISKS,
            is_success=False,
            error_message=f"Método desconocido: {method}",
        )


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
        # Comprobar si hay vacío interior
        _, _, has_void, warnings_from_curves = _order_curves_by_distance(
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
    theta_max: float = 2 * math.pi,
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

        # Lambdificar funciones a NumPy/math para evaluación vectorial rápida
        f_real = prepare_expr_for_real_eval(f_parsed.sympy_expr)
        g_real = prepare_expr_for_real_eval(g_parsed.sympy_expr)
        f_lamb = sympy.lambdify(var_sym, f_real, modules=REAL_EVAL_MODULES)
        g_lamb = sympy.lambdify(var_sym, g_real, modules=REAL_EVAL_MODULES)

        # Nodos axiales en [a, b]: el giro angular es exacto, así que solo se densifica
        # a lo largo del perfil, siguiendo la longitud de arco de f y g. La cantidad de
        # filas sigue siendo exactamente num_axial.
        t_dense = np.linspace(num_a, num_b, max(400, 8 * num_axial))
        with np.errstate(all="ignore"):
            f_dense = _evaluate_profile(f_lamb, t_dense)
            g_dense = _evaluate_profile(g_lamb, t_dense)
        t_vals = equidistributed_nodes(t_dense, [f_dense, g_dense], num_axial)

        # Muestrear el ángulo angular en [0, theta_max] (permite apertura/barrido interactivo)
        theta_bound = max(1e-4, min(2 * np.pi, float(theta_max)))
        theta_vals = np.linspace(0, theta_bound, num_radial)
        T_grid, Theta_grid = np.meshgrid(t_vals, theta_vals, indexing="ij")

        # Evaluar valores de las funciones sobre el eje t
        f_vals = np.array([float(np.real(f_lamb(t))) if np.isreal(f_lamb(t)) else np.nan for t in t_vals])
        g_vals = np.array([float(np.real(g_lamb(t))) if np.isreal(g_lamb(t)) else np.nan for t in t_vals])

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

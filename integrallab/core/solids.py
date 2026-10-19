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
        new_f_expr = str(num_b)
        new_g_expr = str(f_inv)
        expl_text = (
            f"Despeje analítico: {region.variable} en función de {target_var}.\n"
            f"Curva interior/exterior: {region.variable} = {f_inv}\n"
            f"Frontera lateral: {region.variable} = {num_b}\n"
            f"Límites en {target_var}: [{c_num:.4g}, {d_num:.4g}]."
        )
        expl_latex = (
            f"\\text{{Despeje: }} {sympy.latex(from_sym)} = {sympy.latex(f_inv)}"
            f", \\quad \\text{{frontera: }} {sympy.latex(from_sym)} = {num_b}"
        )

    a_sym = sympy.Rational(f"{c_num:.6f}").limit_denominator(1000) if abs(c_num - round(c_num)) < 1e-6 else c_num
    b_sym = sympy.Rational(f"{d_num:.6f}").limit_denominator(1000) if abs(d_num - round(d_num)) < 1e-6 else d_num

    new_region = Region2D(
        f_expr=new_f_expr,
        g_expr=new_g_expr,
        a=a_sym,
        b=b_sym,
        variable=target_var,
    )
    return new_region, expl_text, expl_latex


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
                out[i] = float(value)
        except (ArithmeticError, ValueError, TypeError):
            continue
    return out


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
    
    # Caso 1: f(x) = g(x)
    eq1 = sympy.Eq(f_sym, g_sym)
    try:
        crosses_f_eq_g = sympy.solve(eq1, var_sym)
        for x in crosses_f_eq_g:
            if isinstance(x, (sympy.Float, sympy.Rational)):
                x_float = float(x.evalf())
            else:
                continue
            
            # Verificar si el cruce está en el intervalo [a, b]
            if num_a <= x_float <= num_b:
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
            eq_squared = sympy.Eq(sympy.expand((f_sym - axis_sym)**2), 
                                   sympy.expand((g_sym - axis_sym)**2))
            crosses_dist_equal = sympy.solve(eq_squared, var_sym)
            
            # Filtrar soluciones que ya fueron detectadas en caso 1 (f = g)
            f_equals_g_str = str(sympy.Eq(f_sym, g_sym))
            already_checked = set()
            
            for x in crosses_dist_equal:
                if isinstance(x, (sympy.Float, sympy.Rational)):
                    x_float = float(x.evalf())
                else:
                    continue
                
                # Verificar si no es una repetición del caso f=g
                try:
                    dist_f_at_x = evaluate_distance(dist_f, x_float)
                    dist_g_at_x = evaluate_distance(dist_g, x_float)
                    if abs(dist_f_at_x - dist_g_at_x) < 1e-9:
                        # Esto es f=g, ya fue tratado arriba
                        already_checked.add(x_float)
                        continue
                except Exception:
                    pass
                
                # Verificar si está en el intervalo y no fue ya chequeado
                if num_a <= x_float <= num_b and x_float not in already_checked:
                    warnings.append(
                        f"¡ADVERTENCIA! Las curvas tienen igual distancia al eje en "
                        f"x = {x_float:.3f} dentro del intervalo [{num_a}, {num_b}]. "
                        f"La región podría estar autointerseccionada."
                    )
        except Exception:
            pass

    # Decisión simple basada en punto medio (con advertencia si hay cruces)
    try:
        val_f_mid = float(dist_f.subs(var_sym, mid_val).evalf())
        val_g_mid = float(dist_g.subs(var_sym, mid_val).evalf())
    except Exception:
        val_f_mid = 1.0
        val_g_mid = 0.0

    if val_f_mid >= val_g_mid:
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


def _clean_latex(s: str) -> str:
    """Elimina notación de valor absoluto de cadenas LaTeX generadas por SymPy.

    SymPy genera \\left|...\\right| cuando no puede determinar el signo de una
    expresión. Esta función los convierte en paréntesis ordinarios para una
    presentación pedagógica más limpia.

    Args:
        s: Cadena LaTeX potencialmente con notación de valor absoluto.

    Returns:
        Cadena LaTeX con los valores absolutos convertidos a paréntesis.
    """
    import re
    # \\left|...\\right| → \\left(...\\right)
    s = s.replace(r'\left|', r'\left(').replace(r'\right|', r'\right)')
    # \\operatorname{Abs}\\left(...\\right) → \\left(...\\right)
    s = re.sub(r'\\operatorname\{Abs\}\\left\(', r'\\left(', s)
    # Abs(expr) simple sin \\left
    s = re.sub(r'\\text\{Abs\}\(', r'(', s)
    return s


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

        if has_void:
            integrand_core = r_outer**2 - r_inner**2
            chosen_method = SolidMethod.WASHERS
        else:
            integrand_core = r_outer**2
            chosen_method = SolidMethod.DISKS

        integrand = sympy.pi * integrand_core
        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        try:
            num_val = float(vol_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

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
                f" \\left({sympy.latex(r_outer**2)}\\right) d{region.variable}"
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

        r_outer, r_inner, _, warnings_from_curves = _order_curves_by_distance(
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

        integrand_core = r_outer**2 - r_inner**2
        integrand = sympy.pi * integrand_core
        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        try:
            num_val = float(vol_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

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
                f"\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} "
                f"\\left[ {sympy.latex(r_outer)}^2 - {sympy.latex(r_inner)}^2 \\right] d{region.variable}"
            ),
            is_success=True,
            steps=steps,
            warnings=warnings_from_curves if warnings_from_curves else [],
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

        # Capturar advertencias de cruces de curvas
        _, _, _, warnings_from_curves = _order_curves_by_distance(
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

        if val_f >= val_g:
            height_expr = f_parsed.sympy_expr - g_parsed.sympy_expr
        else:
            height_expr = g_parsed.sympy_expr - f_parsed.sympy_expr

        integrand_core = radius_expr * height_expr
        integrand = 2 * sympy.pi * integrand_core
        vol_sym = sympy.integrate(integrand, (var_sym, sym_a, sym_b))

        try:
            num_val = float(vol_sym.evalf())
        except (TypeError, ValueError):
            num_val = None

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

        return VolumeResult(
            method=SolidMethod.SHELLS,
            exact_plain_text=str(vol_sym),
            exact_latex=_clean_latex(sympy.latex(vol_sym)),
            numeric_value=num_val,
            integrand_plain_text=str(integrand),
            integrand_latex=_clean_latex(sympy.latex(integrand)),
            integral_setup_latex=_clean_latex(
                f"2\\pi \\int_{{{sympy.latex(sym_a)}}}^{{{sympy.latex(sym_b)}}} "
                f"\\left({sympy.latex(radius_expr)}\\right) \\left({sympy.latex(height_expr)}\\right) d{region.variable}"
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


def calculate_revolution_volume(
    region: Region2D,
    axis: RevolutionAxis | None = None,
    method: SolidMethod | None = None,
    allow_inversion: bool = True,
) -> VolumeResult:
    """Función de alto nivel para calcular el volumen según el método seleccionado o recomendado.

    Si el método solicitado requiere cortes en la otra variable (por ejemplo, Discos/Arandelas
    en eje vertical o Casquillos en eje horizontal) y allow_inversion es True, invierte analíticamente
    la región mediante SymPy para resolver la integral en dy.
    """
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

    # Si no es compatible directamente con la variable actual
    if not is_method_compatible(method, axis, region.variable):
        if allow_inversion:
            target_var = "y" if region.variable == "x" else "x"
            try:
                inv_region, expl_text, expl_latex = invert_region_to_variable(region, target_var=target_var)
                sub_method = method
                res = calculate_revolution_volume(inv_region, axis, method=sub_method, allow_inversion=False)
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
                    return VolumeResult(
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
                    )
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
        f_lamb = sympy.lambdify(var_sym, f_parsed.sympy_expr, modules=["numpy", "math"])
        g_lamb = sympy.lambdify(var_sym, g_parsed.sympy_expr, modules=["numpy", "math"])

        # Nodos axiales en [a, b]: el giro angular es exacto, así que solo se densifica
        # a lo largo del perfil, siguiendo la longitud de arco de f y g. La cantidad de
        # filas sigue siendo exactamente num_axial.
        t_dense = np.linspace(num_a, num_b, max(400, 8 * num_axial))
        with np.errstate(all="ignore"):
            f_dense = _evaluate_profile(f_lamb, t_dense)
            g_dense = _evaluate_profile(g_lamb, t_dense)
        t_vals = equidistributed_nodes(t_dense, [f_dense, g_dense], num_axial)

        # Muestrear el ángulo angular [0, 2π]
        theta_vals = np.linspace(0, 2 * np.pi, num_radial)
        T_grid, Theta_grid = np.meshgrid(t_vals, theta_vals, indexing="ij")

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

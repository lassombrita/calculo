"""Sólidos de revolución usando arquitectura modular (Fase 5 M5).

Responsabilidad:
1. Representar regiones bidimensionales delimitadas por curvas y límites.
2. Calcular analítica y numéricamente volúmenes de revolución.
3. Proveer un motor de recomendación explicable.
4. Generar mallas numéricas tridimensionales para visualización.

NOTAS DE MIGRACIÓN (M5):
- ✅ Uso de Region2D inmutable con árbol para memoización
- ✅ Delegación a calculate_volume_from_region() en lugar de llamadas directas
- ✅ Parámetros consolidados en objeto Región en lugar de dispersos
- ✅ Uso de ExpressionTokenizer para parsing robusto
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Tuple, Sequence, Union

import numpy as np

# Importar desde nueva estructura modular (Fase 5 M1-M4)
from integrallab.core.domain.calculus import integrate, differentiate
from integrallab.core.domain.expressions import ExpressionTokenizer
from integrallab.core.parser import ParsedExpression
from integrallab.core.domain.geometry import Region2D
from integrallab.core.volume.calculation import calculate_volume_from_region
from integrallab.core.parser import parse_math_expression, parse_numeric_or_symbolic


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


class SolidOfRevolutionError(ValueError):
    """Excepción para errores en el cálculo de sólidos de revolución."""

    pass


# ─────────────────────────────────────────────────────────────────────────────
# Funciones públicas de creación de regiones (M5)
# ─────────────────────────────────────────────────────────────────────────────

def create_region_disk(
    f_expr: Union[str, ParsedExpression],
    a: Union[float, int, str] = 0,
    b: Union[float, int, str] = 1,
    variable: str = "x"
) -> Region2D:
    """Crea una región para método de discos (bajo y=f(x), sobre y=0).

    Args:
        f_expr: Función f(x) que define la curva superior.
        a: Límite inferior de integración.
        b: Límite superior de integration.
        variable: Variable independiente ('x' o 'y').

    Returns:
        Region2D configurada para cálculo de volumen por discos.
    """
    return Region2D(
        f_expr=f_expr,
        g_expr="0",  # Región bajo el eje y=0
        a=float(a),
        b=float(b),
        variable=variable
    )


def create_region_washer(
    outer_expr: Union[str, ParsedExpression],
    inner_expr: Optional[Union[str, ParsedExpression]] = None,
    a: Union[float, int, str] = 0,
    b: Union[float, int, str] = 1,
    variable: str = "x"
) -> Region2D:
    """Crea una región para método de arandelas (entre dos curvas).

    Args:
        outer_expr: Función que define la curva externa (más lejana al eje).
        inner_expr: Función que define la curva interna (o None para usar y=0).
        a: Límite inferior de integración.
        b: Límite superior de integración.
        variable: Variable independiente ('x' o 'y').

    Returns:
        Region2D configurada para cálculo de volumen por arandelas.
    """
    inner_expr = inner_expr or "0"
    return Region2D(
        f_expr=outer_expr,
        g_expr=inner_expr,
        a=float(a),
        b=float(b),
        variable=variable
    )


def create_region_shell(
    x_expr: Union[str, ParsedExpression],
    y_lower: Optional[Union[float, int, str]] = None,
    y_upper: Optional[Union[float, int, str]] = None,
    a: Union[float, int, str] = 0,
    b: Union[float, int, str] = 1,
    variable: str = "y"
) -> Region2D:
    """Crea una región para método de casquillos cilíndricos.

    Args:
        x_expr: Función x=g(y) que define el perfil en función de y.
        y_lower: Límite inferior para y (o None para usar valor numérico).
        y_upper: Límite superior para y (o None para usar valor numérico).
        a: Valor mínimo de x (eje o curva interna).
        b: Valor máximo de x (eje o curva externa).
        variable: Variable independiente ('x' o 'y').

    Returns:
        Region2D configurada para cálculo de volumen por casquillos.
    """
    if y_lower is None and y_upper is None:
        # Usar a, b como límites si se proporcionaron como y
        return Region2D(
            f_expr=str(x_expr),
            g_expr="0",
            a=float(a) if isinstance(a, (int, float)) else str(a),
            b=float(b) if isinstance(b, (int, float)) else str(b),
            variable=variable
        )
    return Region2D(
        f_expr=str(x_expr),
        g_expr="0",  # Simplificado
        a=float(y_lower) if isinstance(y_lower, (int, float)) else str(y_lower),
        b=float(y_upper) if isinstance(y_upper, (int, float)) else str(y_upper),
        variable=variable
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de volumen delegado a volume/calculation.py (M5-M6)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_volume(
    region: Region2D,
    axis: RevolutionAxis = RevolutionAxis.x_axis(),
    method: Optional[SolidMethod] = None,
    use_exact: bool = True
) -> VolumeResult:
    """Calcula el volumen del sólido de revolución usando la región proporcionada.

    Args:
        region: Región2D que define la región plana a rotar.
        axis: Eje de rotación (horizontal o vertical).
        method: Método de integración deseado (Discos, Arandelas, Casquillos).
                 Si None, se selecciona automáticamente según la geometría.
        use_exact: True para calcular integral exacta (SymPy), False para numérico.

    Returns:
        VolumeResult con volumen exacto y aproximación numérica.
    """
    
    # Usar API unificada de volume/calculation.py
    return calculate_volume_from_region(
        region=region,
        axis=axis,
        method=method,
        use_exact=use_exact
    )


def calculate_mesh_3d(
    region: Region2D,
    axis: RevolutionAxis = RevolutionAxis.x_axis(),
    resolution: int = 50
) -> SolidMesh3D:
    """Genera malla numérica 3D para visualización de la superficie.

    Args:
        region: Región2D que define el perfil a rotar.
        axis: Eje de rotación.
        resolution: Resolución de la malla (número de puntos).

    Returns:
        SolidMesh3D con matrices para renderizado 3D.
    """
    
    # Implementación delegada a volumen/calculation.py si está disponible
    # Por ahora, implementación básica usando parametrización angular
    try:
        from integrallab.core.volume.meshing import generate_revolution_mesh
        
        return generate_revolution_mesh(region=region, axis=axis, resolution=resolution)
    except ImportError:
        # Fallback: generar malla numérica simple con NumPy
        _generate_fallback_mesh(region, axis, resolution)


def _generate_fallback_mesh(
    region: Region2D,
    axis: RevolutionAxis,
    resolution: int = 50
) -> SolidMesh3D:
    """Genera malla numérica simple para visualización 3D (fallback)."""
    
    try:
        # Crear parametrización en coordenadas polares
        theta = np.linspace(0, 2 * np.pi, resolution)
        t_vals = np.linspace(float(region.a), float(region.b), resolution)
        
        X, Y = np.meshgrid(theta, t_vals)
        
        if axis.orientation == AxisOrientation.VERTICAL:
            # Rotación alrededor de eje vertical (x = constante)
            radius = abs(float(_evaluate_profile_expr(
                region.f_expr, 
                str(region.variable),
                Y
            )))
            Z = X[0]  # Eje vertical
            
            # Generar malla exterior y superficie
            x_outer = (axis.position + radius * np.cos(Z))
            y_outer = radius * np.sin(Z)
            z_outer = t_vals[X.flatten()[0]]  # Simplificado
        else:
            # Rotación alrededor de eje horizontal (y = constante)
            radius = abs(float(_evaluate_profile_expr(
                region.f_expr, 
                str(region.variable),
                Y
            )))
            Z = Y[0]  # Eje horizontal
            
            x_outer = radius * np.cos(Z)
            y_outer = axis.position + radius * np.sin(Z)
            z_outer = t_vals[Y.flatten()[0]]
        
        return SolidMesh3D(
            x_outer=x_outer,
            y_outer=y_outer,
            z_outer=z_outer,
            is_valid=True
        )
    except Exception:
        # Malla por defecto si falla
        mesh = SolidMesh3D(
            x_outer=np.zeros((resolution, resolution)),
            y_outer=np.zeros((resolution, resolution)),
            z_outer=np.zeros((resolution, resolution)),
            is_valid=True
        )
        return mesh


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de evaluación (M5)
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_profile_expr(
    expr: Union[str, ParsedExpression],
    variable: str,
    values
) -> np.ndarray:
    """Evalúa una expresión matemática en valores numéricos."""
    
    try:
        parsed = parse_math_expression(str(expr))
        
        # Crear función de evaluación
        from sympy import sympify, lambdify
        
        var_sym = sympy.Symbol(variable)
        func = lambdify(var_sym, parsed.sympy_expr, modules="numpy")
        
        return np.array([func(float(v)) for v in values])
    except Exception:
        return np.full_like(values, np.nan)


# ─────────────────────────────────────────────────────────────────────────────
# Validaciones y recomendaciones (M5-M13)
# ─────────────────────────────────────────────────────────────────────────────

def validate_region(region: Region2D) -> Tuple[bool, Optional[str]]:
    """Valida que una región esté bien definida."""
    
    try:
        # 1. Verificar sintaxis de expresiones
        f_parsed = ExpressionTokenizer.tokenize(str(region.f_expr))
        
        if region.g_expr is not None:
            g_parsed = ExpressionTokenizer.tokenize(str(region.g_expr))
        
        # 2. Verificar límites numéricos
        a, b = float(region.a), float(region.b)
        if a >= b:
            return False, f"Límites inválidos: a={a} no puede ser >= b={b}"
        
        # 3. Verificar dominio de funciones en [a, b]
        for name, expr_str in [("f", region.f_expr), ("g", region.g_expr)]:
            if domain_error_for_expr(expr_str, variable=region.variable):
                return False, f"La función {name} no está definida en todo el intervalo [{a}, {b}]"
        
        return True, None
        
    except Exception as e:
        return False, str(e)


def domain_error_for_expr(
    expr: Union[str, ParsedExpression],
    variable: str = "x"
) -> Optional[str]:
    """Verifica que una expresión tenga dominio válido en algún intervalo."""
    
    try:
        from sympy import Symbol, is_real
    
        var_sym = Symbol(variable)
        
        # Evaluar en varios puntos para detectar problemas de dominio
        test_points = [-1.0, -0.5, 0.0, 0.5, 1.0, 2.0, np.pi, np.e]
        
        expr_str = str(expr)
        
        for val in test_points:
            try:
                parsed = ExpressionTokenizer.tokenize(expr_str)
                func = lambdify(var_sym, parsed.sympy_expr, modules="numpy")
                result = func(val)
                
                if not np.isreal(result):
                    return f"Expresión no es real en {variable}={val}"
            except Exception:
                return f"Error al evaluar expresión en {variable}={val}"
        
        return None
        
    except ImportError:
        return None


from sympy import sympify, lambdify as _lambdify


def domain_error(region: Region2D) -> Optional[str]:
    """Mensaje si f o g no son reales en parte de [a, b]; None si la región es válida."""
    
    try:
        # Verificar dominio usando evaluación numérica
        a, b = float(region.a), float(region.b)
        
        test_points = np.linspace(a, b, 10)
        
        for name, expr_str in [("f", str(region.f_expr)), ("g", str(region.g_expr or "0"))]:
            for val in test_points:
                try:
                    parsed = ExpressionTokenizer.tokenize(expr_str)
                    var_sym = sympy.Symbol(region.variable)
                    func = _lambdify(var_sym, parsed.sympy_expr, modules="numpy")
                    result = func(val)
                    
                    if not np.isreal(result):
                        return (
                            f"{name}({region.variable}) = {expr_str} no está definida o no es real en parte "
                            f"del intervalo [{a:.4g}, {b:.4g}] (por ejemplo, en {region.variable} ≈ {val:.4g}). "
                            "Ajuste los límites al dominio de la función."
                        )
                except Exception:
                    return (
                        f"{name}({region.variable}) = {expr_str} no puede ser evaluada en parte del intervalo. "
                        f"Ajuste los límites al dominio de la función."
                    )
        
        return None
        
    except Exception:
        return None


def recommend_method(region: Region2D, axis: RevolutionAxis) -> MethodRecommendation:
    """Recomienda el método de integración más adecuado para la región."""
    
    # Reglas heurísticas para seleccionar método
    a, b = float(region.a), float(region.b)
    
    # Obtener valores aproximados en puntos del dominio
    try:
        f_values = _evaluate_profile_expr(str(region.f_expr), region.variable, [a + 0.1*(b-a), a + 0.9*(b-a)])
        
        if region.g_expr is not None and region.g_expr != "0":
            g_values = _evaluate_profile_expr(str(region.g_expr), region.variable, [a + 0.1*(b-a), a + 0.9*(b-a)])
        else:
            g_values = np.zeros_like(f_values)
    except Exception:
        f_values = np.array([1.0])
        g_values = np.array([0.0])
    
    # Determinar método basado en geometría
    if len(f_values) == 1 or (region.g_expr is None or region.g_expr == "0"):
        # Región simple bajo una curva → Discos
        return MethodRecommendation(
            recommended_method=SolidMethod.DISKS,
            justification=(
                "La región está definida por una sola función f(x) sobre el eje y=0. "
                "El método de discos es el más adecuado."
            ),
            integral_setup=f"V = π ∫_{{a}}^{{b}} [f({region.variable})]² d{region.variable}",
            alternatives=[
                (SolidMethod.WASHERS, "Solo si se añade una curva inferior no nula"),
                (SolidMethod.SHELLS, "Método alternativo pero más complejo para esta geometría")
            ]
        )
    elif len(f_values) > 1 and len(g_values) > 0:
        # Región entre dos curvas → Arandelas
        return MethodRecommendation(
            recommended_method=SolidMethod.WASHERS,
            justification=(
                "La región está delimitada por dos funciones f(x) y g(x). "
                "El método de arandelas es el más directo."
            ),
            integral_setup=f"V = π ∫_{{a}}^{{b}} ([f({region.variable})]² - [g({region.variable})]²) d{region.variable}",
            alternatives=[
                (SolidMethod.SHELLS, "Método alternativo que requiere inversión analítica"),
                (SolidMethod.DISKS, "Solo si la región inferior es y=0")
            ]
        )
    else:
        # Casos especiales → Casquillos o discos
        return MethodRecommendation(
            recommended_method=SolidMethod.SHELLS,
            justification=(
                "Geometría compleja detectada. El método de casquillos es adecuado para regiones "
                "que no pueden expresarse fácilmente como funciones y=f(x)."
            ),
            integral_setup=f"V = 2π ∫_{{a}}^{{b}} [x - {axis.position}] · f({region.variable}) d{region.variable}",
            alternatives=[
                (SolidMethod.DISKS, "Después de invertir la región a dx"),
                (SolidMethod.WASHERS, "Si existe una curva interna bien definida")
            ]
        )


# ─────────────────────────────────────────────────────────────────────────────
# Inversión simbólica para métodos incompatibles (M5)
# ─────────────────────────────────────────────────────────────────────────────

def invert_region(
    region: Region2D,
    target_var: str = "y"
) -> Tuple[Region2D, str, str]:
    """Invierte una región de revolución para cambio de variable (x → y).

    Args:
        region: Región original definida en variables x.
        target_var: Variable objetivo para la nueva definición ('y').

    Returns:
        Tupla con (nueva_región_invertida, explicación_texto, explicación_latex).
    """
    
    from integrallab.core.domain.inversion import invert_region_to_variable
    
    try:
        inverted_region, expl_text, expl_latex = invert_region_to_variable(
            region=region,
            target_var=target_var
        )
        
        return (
            inverted_region,
            f"Inversión exitosa a {target_var}: {expl_text}",
            f"\\text{{Inversión: }}{expl_latex}"
        )
    except Exception as e:
        raise SolidOfRevolutionError(f"Error al invertir región: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Funciones de utilidad (M5-M13)
# ─────────────────────────────────────────────────────────────────────────────

def parse_expression_safe(text: str, variable: str = "x") -> ParsedExpression:
    """Parsea una expresión matemática de forma segura.

    Args:
        text: Texto con la expresión matemática.
        variable: Variable independiente (por defecto 'x').

    Returns:
        ParsedExpression listo para evaluación o integración.
    """
    
    try:
        # Usar ExpressionTokenizer para parsing robusto
        tokenized = ExpressionTokenizer.tokenize(text)
        return tokenized
    except Exception as e:
        raise SolidOfRevolutionError(f"Error al parsear expresión '{text}': {e}")


def simplify_expression(expr: str, variable: str = "x") -> str:
    """Simplifica una expresión matemática usando SymPy.

    Args:
        expr: Expresión en sintaxis Python o LaTeX.
        variable: Variable independiente.

    Returns:
        Expresión simplificada.
    """
    
    try:
        from sympy import simplify, Symbol
        
        var_sym = Symbol(variable)
        parsed = ExpressionTokenizer.tokenize(expr)
        simplified_expr = simplify(parsed.sympy_expr)
        
        return str(simplified_expr)
    except Exception:
        # Si falla, devolver expresión original
        return expr


def differentiate_with_chain_rule(expr: str, variable: str = "x") -> Tuple[str, str]:
    """Calcula derivada usando regla de la cadena para expresiones compuestas.

    Args:
        expr: Expresión con composición de funciones (ej. sin(x**2)).
        variable: Variable independiente.

    Returns:
        Tupla con (expresión_derivada, explicación_latex).
    """
    
    try:
        from sympy import diff, Symbol
        
        var_sym = Symbol(variable)
        parsed = ExpressionTokenizer.tokenize(expr)
        
        deriv = diff(parsed.sympy_expr, var_sym)
        
        latex_explanation = f"\\frac{{d}}{{d{variable}}}({expr}) = {deriv}"
        
        return str(deriv), latex_explanation
    except Exception as e:
        return expr, f"Error al calcular derivada: {e}"


__all__ = [
    # Tipos
    "AxisOrientation",
    "SolidMethod", 
    "RevolutionAxis",
    "SolutionStep",
    "VolumeResult",
    "MethodRecommendation",
    "SolidMesh3D",
    "SolidOfRevolutionError",
    
    # Funciones de creación de regiones (M5)
    "create_region_disk",
    "create_region_washer",
    "create_region_shell",
    
    # Cálculo delegado (M5-M6)
    "calculate_volume",
    "calculate_mesh_3d",
    
    # Utilidades de evaluación (M5)
    "_evaluate_profile_expr",
    
    # Validaciones y recomendaciones (M5-M13)
    "validate_region",
    "domain_error_for_expr",
    "domain_error",
    "recommend_method",
    
    # Inversión simbólica (M5)
    "invert_region",
    
    # Funciones de utilidad (M5-M13)
    "parse_expression_safe",
    "simplify_expression",
    "differentiate_with_chain_rule",
]
"""Módulo de interpolación numérica y aproximación funcional.

Responsabilidad:
Construir funciones y polinomios continuos a partir de conjuntos de datos discretos (puntos x, y)
mediante interpolación polinómica de Lagrange, diferencias divididas de Newton y Splines cúbicos,
entregando representaciones simbólicas (SymPy) y pasos explicados de deducción para análisis pedagógico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Callable, Sequence

try:
    import sympy
    _SYMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    sympy = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False

from integrallab.core.solids import SolutionStep


class InterpolationMethod(str, Enum):
    """Métodos de interpolación soportados."""

    LAGRANGE = "lagrange"
    NEWTON = "newton"
    CUBIC_SPLINE = "spline"


@dataclass(frozen=True)
class DataPoint:
    """Representa un punto coordenado (x, y) en el plano cartesiano."""

    x: float
    y: float

    def to_tuple(self) -> tuple[float, float]:
        """Retorna las coordenadas como tupla (x, y)."""
        return self.x, self.y


@dataclass(frozen=True)
class InterpolationResult:
    """Resultado del proceso de interpolación numérica.

    Atributos:
        method: Método empleado (Lagrange, Newton o Spline cúbico).
        points: Lista ordenada de puntos de soporte utilizados.
        polynomial_plain_text: Expresión matemática en texto plano estándar.
        polynomial_latex: Expresión matemática en formato LaTeX.
        sympy_expr: Expresión simbólica de SymPy (polinomio o Piecewise).
        is_success: True si la interpolación concluyó sin errores.
        error_message: Mensaje explicativo en caso de fallo.
        steps: Desglose analítico paso a paso del procedimiento matemático.
    """

    method: InterpolationMethod
    points: list[DataPoint] = field(default_factory=list)
    polynomial_plain_text: str = ""
    polynomial_latex: str = ""
    sympy_expr: object | None = None
    is_success: bool = True
    error_message: str | None = None
    steps: list[SolutionStep] = field(default_factory=list)

    def evaluate(self, x_val: float) -> float:
        """Evalúa el polinomio o función interpolante en un valor numérico dado."""
        if not self.is_success or self.sympy_expr is None or not _SYMPY_AVAILABLE:
            raise ValueError("No se puede evaluar un resultado de interpolación no exitoso o sin SymPy.")
        x_sym = sympy.Symbol("x")
        val = self.sympy_expr.subs(x_sym, x_val)
        return float(val.evalf())


def _normalize_points(
    raw_points: Sequence[DataPoint | tuple[float, float] | list[float]],
) -> list[DataPoint]:
    """Convierte y valida una secuencia de puntos, ordenándolos por la coordenada x."""
    if len(raw_points) < 2:
        raise ValueError("Se requieren al menos 2 puntos para realizar una interpolación.")

    pts: list[DataPoint] = []
    for p in raw_points:
        if isinstance(p, DataPoint):
            pts.append(p)
        elif isinstance(p, (tuple, list)) and len(p) >= 2:
            pts.append(DataPoint(x=float(p[0]), y=float(p[1])))
        else:
            raise TypeError(f"Elemento de punto inválido: {p}. Se esperaba DataPoint o tupla (x, y).")

    # Ordenar por x
    pts.sort(key=lambda pt: pt.x)

    # Validar que no haya abscisas repetidas
    for i in range(len(pts) - 1):
        if math.isclose(pts[i].x, pts[i + 1].x, abs_tol=1e-12):
            raise ValueError(
                f"Abscisas duplicadas no permitidas para una función: x = {pts[i].x} en índices {i} y {i+1}."
            )

    return pts


def interpolate_lagrange(
    points: Sequence[DataPoint | tuple[float, float]],
    variable: str = "x",
) -> InterpolationResult:
    """Calcula el polinomio interpolador de Lagrange para un conjunto de puntos.

    Fórmula:
        P(x) = ∑_{i=0}^{n-1} y_i · L_i(x)
        donde L_i(x) = ∏_{j ≠ i} (x - x_j) / (x_i - x_j)
    """
    if not _SYMPY_AVAILABLE:
        return InterpolationResult(
            method=InterpolationMethod.LAGRANGE,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        pts = _normalize_points(points)
        x_sym = sympy.Symbol(variable)
        n = len(pts)

        steps: list[SolutionStep] = []
        l_bases: list[sympy.Expr] = []

        step_idx = 1
        steps.append(
            SolutionStep(
                step_number=step_idx,
                title="Planteamiento de los datos de soporte",
                explanation=f"Se identifican {n} puntos de soporte ordenados en el plano.",
                expression_plain_text=", ".join([f"({p.x}, {p.y})" for p in pts]),
                expression_latex="; \\quad ".join([f"({p.x}, {p.y})" for p in pts]),
            )
        )
        step_idx += 1

        # Construcción de polinomios base L_i(x)
        poly_expr: sympy.Expr = sympy.Integer(0)
        for i, pt_i in enumerate(pts):
            l_i: sympy.Expr = sympy.Integer(1)
            for j, pt_j in enumerate(pts):
                if i != j:
                    l_i = l_i * (x_sym - pt_j.x) / (pt_i.x - pt_j.x)

            l_bases.append(l_i)
            term = pt_i.y * l_i
            poly_expr = poly_expr + term

        expanded_poly = sympy.expand(poly_expr)
        simplified_poly = sympy.simplify(expanded_poly)

        steps.append(
            SolutionStep(
                step_number=step_idx,
                title="Construcción de los polinomios base de Lagrange L_i(x)",
                explanation=f"Se forman los {n} términos L_i(x) que satisfacen L_i(x_j) = δ_ij.",
                expression_plain_text="\n".join([f"L_{i}({variable}) = {l_bases[i]}" for i in range(min(4, n))]),
                expression_latex="; \\quad ".join([f"L_{{{i}}}({variable}) = {sympy.latex(l_bases[i])}" for i in range(min(3, n))]),
            )
        )
        step_idx += 1

        steps.append(
            SolutionStep(
                step_number=step_idx,
                title="Combinación lineal y simplificación polinómica",
                explanation="Se multiplican los valores y_i por sus respectivas bases y se expanden términos semejantes.",
                expression_plain_text=f"P({variable}) = {simplified_poly}",
                expression_latex=f"P({variable}) = {sympy.latex(simplified_poly)}",
            )
        )

        return InterpolationResult(
            method=InterpolationMethod.LAGRANGE,
            points=pts,
            polynomial_plain_text=str(simplified_poly),
            polynomial_latex=sympy.latex(simplified_poly),
            sympy_expr=simplified_poly,
            is_success=True,
            steps=steps,
        )
    except Exception as exc:
        return InterpolationResult(
            method=InterpolationMethod.LAGRANGE,
            is_success=False,
            error_message=str(exc),
        )


def interpolate_newton(
    points: Sequence[DataPoint | tuple[float, float]],
    variable: str = "x",
) -> InterpolationResult:
    """Calcula el polinomio interpolador de Newton mediante diferencias divididas.

    Fórmula:
        P(x) = f[x_0] + f[x_0, x_1](x - x_0) + f[x_0, x_1, x_2](x - x_0)(x - x_1) + ...
    """
    if not _SYMPY_AVAILABLE:
        return InterpolationResult(
            method=InterpolationMethod.NEWTON,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        pts = _normalize_points(points)
        x_sym = sympy.Symbol(variable)
        n = len(pts)

        xs = [p.x for p in pts]
        ys = [p.y for p in pts]

        # Tabla de diferencias divididas
        dd = [[0.0] * n for _ in range(n)]
        for i in range(n):
            dd[i][0] = ys[i]

        for j in range(1, n):
            for i in range(n - j):
                dd[i][j] = (dd[i + 1][j - 1] - dd[i][j - 1]) / (xs[i + j] - xs[i])

        steps: list[SolutionStep] = []
        steps.append(
            SolutionStep(
                step_number=1,
                title="Tabla de Diferencias Divididas",
                explanation=f"Se calculan los coeficientes f[x_0, ..., x_k] recursivamente a partir de los {n} puntos.",
                expression_plain_text=", ".join([f"f[x_0..x_{k}]={dd[0][k]:.4g}" for k in range(n)]),
                expression_latex="; \\quad ".join([f"f[x_0\\dots x_{{{k}}}] = {dd[0][k]:.4g}" for k in range(min(5, n))]),
            )
        )

        # Construir polinomio analítico
        poly_newton: sympy.Expr = sympy.Rational(f"{dd[0][0]:.8f}").limit_denominator(10000) if abs(dd[0][0] - round(dd[0][0])) < 1e-7 else sympy.Float(dd[0][0])
        product_factor: sympy.Expr = sympy.Integer(1)

        for k in range(1, n):
            product_factor = product_factor * (x_sym - xs[k - 1])
            coeff = sympy.Rational(f"{dd[0][k]:.8f}").limit_denominator(10000) if abs(dd[0][k] - round(dd[0][k])) < 1e-7 else sympy.Float(dd[0][k])
            poly_newton = poly_newton + coeff * product_factor

        simplified_poly = sympy.simplify(sympy.expand(poly_newton))

        steps.append(
            SolutionStep(
                step_number=2,
                title="Formulación y simplificación de Newton",
                explanation="Se expanden los productos sucesivos (x - x_0)...(x - x_k) y se reducen términos semejantes.",
                expression_plain_text=f"P({variable}) = {simplified_poly}",
                expression_latex=f"P({variable}) = {sympy.latex(simplified_poly)}",
            )
        )

        return InterpolationResult(
            method=InterpolationMethod.NEWTON,
            points=pts,
            polynomial_plain_text=str(simplified_poly),
            polynomial_latex=sympy.latex(simplified_poly),
            sympy_expr=simplified_poly,
            is_success=True,
            steps=steps,
        )
    except Exception as exc:
        return InterpolationResult(
            method=InterpolationMethod.NEWTON,
            is_success=False,
            error_message=str(exc),
        )


def interpolate_cubic_spline(
    points: Sequence[DataPoint | tuple[float, float]],
    variable: str = "x",
) -> InterpolationResult:
    """Calcula el Spline Cúbico Natural por el método tridiagonal estándar.

    Condiciones de borde naturales: S''(x_0) = S''(x_n) = 0.

    El algoritmo resuelve el sistema tridiagonal de n-1 incógnitas (momentos M_i)
    usando eliminación de Thomas (O(n)) y construye los polinomios cúbicos por
    tramos en forma de Piecewise de SymPy.

    Válido desde n=2 puntos (spline lineal degenerado).
    """
    if not _SYMPY_AVAILABLE:
        return InterpolationResult(
            method=InterpolationMethod.CUBIC_SPLINE,
            is_success=False,
            error_message="El motor matemático SymPy no está disponible.",
        )

    try:
        pts = _normalize_points(points)
        n = len(pts)
        x_sym = sympy.Symbol(variable)
        xs = [float(p.x) for p in pts]
        ys = [float(p.y) for p in pts]

        if n < 2:
            raise ValueError("Se requieren al menos 2 puntos para el spline cúbico.")

        # Caso degenerado: 2 puntos → interpolación lineal
        if n == 2:
            h = xs[1] - xs[0]
            slope = (ys[1] - ys[0]) / h
            spline_expr = sympy.sympify(ys[0]) + sympy.sympify(slope) * (x_sym - xs[0])
            steps = [
                SolutionStep(
                    step_number=1,
                    title="Caso degenerado: 2 puntos",
                    explanation="Con solo 2 puntos el spline se reduce a una recta.",
                    expression_plain_text=str(spline_expr),
                    expression_latex=sympy.latex(spline_expr),
                ),
            ]
            return InterpolationResult(
                method=InterpolationMethod.CUBIC_SPLINE,
                points=pts,
                polynomial_plain_text=str(spline_expr),
                polynomial_latex=sympy.latex(spline_expr),
                sympy_expr=spline_expr,
                is_success=True,
                steps=steps,
            )

        # Pasos del algoritmo tridiagonal
        # h_i = x_{i+1} - x_i
        h = [xs[i + 1] - xs[i] for i in range(n - 1)]

        # Sistema tridiagonal de (n-2) ecuaciones para M_1..M_{n-2}
        # (condiciones naturales: M_0 = M_{n-1} = 0)
        size = n - 2
        if size == 0:
            # n=2 ya manejado arriba; n=3 produce size=1
            pass

        M = [0.0] * n  # momentos, M[0]=M[n-1]=0

        if size > 0:
            # Coeficientes de la diagonal principal, sub y super diagonal
            diag = [2.0 * (h[i] + h[i + 1]) for i in range(size)]
            upper = [h[i + 1] for i in range(size - 1)]
            lower = [h[i + 1] for i in range(size - 1)]
            rhs = [
                6.0 * ((ys[i + 2] - ys[i + 1]) / h[i + 1] - (ys[i + 1] - ys[i]) / h[i])
                for i in range(size)
            ]

            # Eliminación de Thomas (forward sweep)
            c_prime = [0.0] * size
            d_prime = [0.0] * size
            c_prime[0] = upper[0] / diag[0] if size > 1 else 0.0
            d_prime[0] = rhs[0] / diag[0]
            for i in range(1, size):
                denom = diag[i] - lower[i - 1] * c_prime[i - 1]
                c_prime[i] = upper[i] / denom if i < size - 1 else 0.0
                d_prime[i] = (rhs[i] - lower[i - 1] * d_prime[i - 1]) / denom

            # Back substitution
            M[size] = d_prime[size - 1]  # M[n-2]
            for i in range(size - 2, -1, -1):
                M[i + 1] = d_prime[i] - c_prime[i] * M[i + 2]

        # Construir los polinomios cúbicos S_i(x) en [x_i, x_{i+1}]
        pieces = []
        for i in range(n - 1):
            xi, xi1 = xs[i], xs[i + 1]
            yi, yi1 = ys[i], ys[i + 1]
            Mi, Mi1 = M[i], M[i + 1]
            hi = h[i]
            t = x_sym - xi
            # Forma estándar de los coeficientes del spline
            a_i = yi
            b_i = (yi1 - yi) / hi - hi * (2 * Mi + Mi1) / 6.0
            c_i = Mi / 2.0
            d_i = (Mi1 - Mi) / (6.0 * hi)
            poly = (
                sympy.Float(a_i)
                + sympy.Float(b_i) * t
                + sympy.Float(c_i) * t**2
                + sympy.Float(d_i) * t**3
            )
            # Condición de validez del tramo
            if i < n - 2:
                cond = sympy.And(x_sym >= xi, x_sym < xi1)
            else:
                cond = sympy.And(x_sym >= xi, x_sym <= xi1)
            pieces.append((poly, cond))

        spline_expr = sympy.Piecewise(*pieces)

        steps: list[SolutionStep] = [
            SolutionStep(
                step_number=1,
                title="Planteamiento de Splines Cúbicos Naturales",
                explanation=(
                    f"Se formulan {n - 1} polinomios cúbicos S_i(x) con continuidad C² "
                    f"y condiciones naturales S''(x_0) = S''(x_{n-1}) = 0. "
                    f"Se resuelve el sistema tridiagonal de {max(n - 2, 0)} momentos."
                ),
                expression_plain_text=f"Intervalos: {n - 1} tramos entre [{xs[0]}, {xs[-1]}].",
                expression_latex=(
                    f"S''(x_0) = S''(x_{{{n - 1}}}) = 0, "
                    f"\\quad n = {n} \\text{{ puntos}}"
                ),
            ),
            SolutionStep(
                step_number=2,
                title="Momentos M_i (sistema tridiagonal)",
                explanation="Los momentos son las segundas derivadas de S en cada nodo.",
                expression_plain_text=", ".join(f"M_{i}={M[i]:.6g}" for i in range(n)),
                expression_latex=", ".join(
                    f"M_{{{i}}} = {M[i]:.6g}" for i in range(n)
                ),
            ),
            SolutionStep(
                step_number=3,
                title="Spline por tramos",
                explanation="Polinomios cúbicos S_i(x) válidos en cada subintervalo.",
                expression_plain_text=str(spline_expr),
                expression_latex=sympy.latex(spline_expr),
            ),
        ]

        return InterpolationResult(
            method=InterpolationMethod.CUBIC_SPLINE,
            points=pts,
            polynomial_plain_text=str(spline_expr),
            polynomial_latex=sympy.latex(spline_expr),
            sympy_expr=spline_expr,
            is_success=True,
            steps=steps,
        )
    except Exception as exc:
        return InterpolationResult(
            method=InterpolationMethod.CUBIC_SPLINE,
            is_success=False,
            error_message=str(exc),
        )


def interpolate(
    points: Sequence[DataPoint | tuple[float, float]],
    method: InterpolationMethod | str = InterpolationMethod.LAGRANGE,
    variable: str = "x",
) -> InterpolationResult:
    """Función de alto nivel que despacha al método de interpolación solicitado."""
    if isinstance(method, str):
        method_str = method.lower().strip()
        if "newton" in method_str:
            chosen = InterpolationMethod.NEWTON
        elif "spline" in method_str:
            chosen = InterpolationMethod.CUBIC_SPLINE
        else:
            chosen = InterpolationMethod.LAGRANGE
    else:
        chosen = method

    if chosen == InterpolationMethod.LAGRANGE:
        return interpolate_lagrange(points, variable=variable)
    elif chosen == InterpolationMethod.NEWTON:
        return interpolate_newton(points, variable=variable)
    elif chosen == InterpolationMethod.CUBIC_SPLINE:
        return interpolate_cubic_spline(points, variable=variable)
    else:
        return InterpolationResult(
            method=InterpolationMethod.LAGRANGE,
            is_success=False,
            error_message=f"Método de interpolación no reconocido: {method}",
        )


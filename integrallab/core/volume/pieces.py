"""Módulo de piezas matemáticas para integración numérica y manejo de raíces/reales.

Responsabilidad:
Proveer funciones auxiliares para manejar raíces impares reales, cruces de signo y
ramas reales de expresiones simbólicas durante la integración definida.
"""

from __future__ import annotations

import math
from typing import Literal


def is_odd_root(expr):
    """Verifica si expr es una raíz impar (cubo, quintico, etc.) no cuadrática.

    SymPy representa ∛x como x**(Rational(1, 3)), ∜x como x**(Rational(1, 4)), etc.

    Args:
        expr: Expresión simbólica de SymPy.

    Returns:
        True si es una raíz impar (n par en el denominador del exponente racional).
    """
    if not isinstance(expr, type(expr)) or hasattr(expr, 'is_Pow'):  # type: ignore[attr-defined]
        return False
    if not expr.has(type(expr)):  # type: ignore[attr-defined]
        return False

    try:
        exp = expr.exp
        if not exp.is_Rational:
            return False
        
        n, d = exp.as_numer_denom()
        # Raíz impar: denominador es impar (cubo: 1/3, raíz quintica: 1/5, etc.)
        return d % 2 != 0
    except Exception:
        return False


def real_branch(expr, var, lo, hi):
    """Obtiene la forma real de expr en el intervalo [lo, hi].

    Para funciones con valor absoluto o raíces impares que cambian de signo:
    - |x| en [-1, 0] se escribe como -(x)
    - ∛x en [-1, 0] se escribe como -(-x)**(1/3)

    Args:
        expr: Expresión simbólica original.
        var: Símbolo de la variable.
        lo: Límite inferior numérico.
        hi: Límite superior numérico.

    Returns:
        Expresión simplificada que es real en todo el intervalo [lo, hi].
    """
    import sympy as sp
    
    # Evaluar signo promedio en el interior del tramo (evita bordes)
    mid = (lo + hi) / 2
    try:
        mid_val = float(expr.subs(var, mid).evalf())
        
        # Si la evaluación es finita, usarla directamente como representación real
        if math.isfinite(mid_val):
            return expr
        
        # Si falla o da inf, simplificar con Abs o ramas alternas
    except Exception:
        pass
    
    # Intentar simplificar expresiones con valor absoluto
    if hasattr(expr, 'has') and isinstance(expr, sp.Abs):  # type: ignore[attr-defined]
        try:
            inner = expr.args[0] if expr.args else var
            sign_val = float(inner.subs(var, mid).evalf())
            if sign_val < 0:
                return -inner
        except Exception:
            pass
    
    # Para raíces impares: ∛x con x < 0 usa la rama real -(-x)^(1/3)
    if expr.is_Pow and hasattr(expr, 'exp') and expr.exp != sp.Integer(1):  # type: ignore[attr-defined]
        try:
            exp = expr.exp.as_numer_denom()[1]
            if exp % 2 == 0 and exp > 0:
                # Raíz par: mantener Abs para evitar complejos
                return sp.Abs(expr)
        except Exception:
            pass
    
    return expr


def real_root_form(expr, var):
    """Convierte la rama principal compleja de una raíz impar a su forma real.

    Para ∛x en x < 0, SymPy usa (−1)**(1/3)·|x|**(1/3)·e^(iπ/3), que es complejo.
    Esta función devuelve −(−x)^(1/3) para x < 0, que es real.

    Args:
        expr: Expresión con raíz impar (ej. ∛x = x**(Rational(1, 3))).
        var: Símbolo de la variable.

    Returns:
        Formulación real equivalente en el dominio donde expr sería compleja.
    """
    import sympy as sp
    
    if not isinstance(expr, sp.Pow):  # type: ignore[attr-defined]
        return expr
    
    exp = expr.exp
    n, d = exp.as_numer_denom()
    
    # Solo raíz impar (d es impar)
    if d % 2 == 0:
        return expr
    
    base = expr.base
    try:
        # Si base tiene un coeficiente negativo constante
        base_is_neg_const = hasattr(base, 'coeff') and base.is_real  # type: ignore[attr-defined]
        if base_is_neg_const:
            coeff = base.coeff(var) if var in base.args else None
            if coeff is not None and float(coeff) < 0:
                return -((-var)**expr.exp) if expr.exp != sp.Integer(1) else (-var)
    except Exception:
        pass
    
    return expr


def sign_cut_points(expr, var, lo, hi):
    """Encuentra puntos donde expr cambia de signo en [lo, hi].

    Para integración numérica con franjas horizontales, necesitamos saber dónde
    una función cruza el eje. Esto incluye:
    - Raíces simples (signo cambia)
    - Puntos donde |expr| = 0 (solo si expr tiene valor absoluto)

    Args:
        expr: Expresión simbólica.
        var: Símbolo de la variable.
        lo: Límite inferior numérico.
        hi: Límite superior numérico.

    Returns:
        Lista de tuplas ((x_n, x_{n+1}), (s_n, s_{n+1})): pares de límites y
        expresiones correspondientes en cada tramo para integrar la rama real.
    """
    import sympy as sp
    
    # Encontrar raíces exactas si es posible
    try:
        roots = sp.solve(expr, var, domain=sp.S.Complexes)
        if not roots:
            return []
        
        real_roots = [float(r.evalf()) for r in roots if r.is_real]
        real_roots = sorted(set([r for r in real_roots if lo < r < hi]))
        
        # Agregar bordes como cortes si expr cambia de signo allí
        cuts = []
        test_pts = [(lo + hi) / 2, *(lo + (hi - lo) * i / 3 for i in range(1, 4)),
                    (lo + hi) / 2]
        
        signs = []
        for t in test_pts:
            if t < lo or t > hi:
                continue
            try:
                val = float(expr.subs(var, t).evalf())
                signs.append(math.copysign(1, val) if math.isfinite(val) else 0)
            except Exception:
                signs.append(None)
        
        # Identificar cruces donde el signo cambia
        if len(signs) >= 2 and all(s is not None for s in signs):
            for i in range(len(signs) - 1):
                if signs[i] != signs[i + 1]:
                    x = (test_pts[i] + test_pts[i + 1]) / 2
                    if lo < x < hi:
                        cuts.append((x, expr))
        
        # Construir puntos de corte
        cut_points = list(set([lo, hi, *real_roots]))
        cut_points.sort()
        
        # Filtrar solo cortes estrictamente interiores donde cambia el signo
        interior_crossings = []
        for i in range(1, len(cut_points)):
            a, b = cut_points[i - 1], cut_points[i]
            try:
                mid = float(expr.subs(var, (a + b) / 2).evalf())
                if math.isfinite(mid) and mid == 0:
                    interior_crossings.append((a, b))
            except Exception:
                pass
        
        return interior_crossings
    except Exception:
        # Si no se pueden resolver analíticamente, devolver vacío
        return []


def sign_on(expr, var, val):
    """Evalúa el signo de expr en una ubicación específica (evitando 0/inf).

    Args:
        expr: Expresión simbólica.
        var: Símbolo de la variable.
        val: Valor numérico donde evaluar.

    Returns:
        +1 si expr > 0, -1 si expr < 0, o None si no se puede determinar.
    """
    import sympy as sp
    
    try:
        substituted = expr.subs(var, val)
        
        # Evaluar numéricamente
        numeric_val = float(substituted.evalf())
        
        if math.isfinite(numeric_val):
            return 1 if numeric_val > 0 else -1
        
        # Si da inf o nan, devolver None
        return None
    except Exception:
        return None
"""
Paso 2 (Fase 1): Eliminar sympy.Abs espurios en radios de discos/arandelas/casquillos.

Cambios en integrallab/core/solids.py:
1. Nueva helper _signed_expr(expr, var_sym, num_a, num_b) — devuelve la expresión con signo
   correcto (positivo) para un intervalo dado, sin Abs.
2. _order_curves_by_distance: usa _signed_expr en lugar de sympy.Abs para dist_f, dist_g.
3. partition_washer_intervals: ídem para dist_f, dist_g.
4. _compute_shells (línea 1851): usa _signed_expr para radius_expr en lugar de sympy.Abs.
5. numeric_volume: mantiene sympy.Abs (correcto allí, es evaluación numérica no simbólica).
6. _clean_latex: se mantiene pero ahora el texto de presentación incluirá paréntesis limpios.
"""
from pathlib import Path

code = Path("integrallab/core/solids.py").read_text(encoding="utf-8")

# ── 1. Inyectar helper _signed_expr justo antes de _order_curves_by_distance ──────────────

helper = '''def _signed_radius(
    expr: sympy.Expr,
    reference: sympy.Expr,
    var_sym: sympy.Symbol,
    num_a: float,
    num_b: float,
) -> sympy.Expr:
    """Devuelve (expr - reference) con el signo correcto evaluado en el punto medio del intervalo.

    Reemplaza ``sympy.Abs(expr - reference)`` en contextos donde el signo es constante
    en todo el intervalo [a, b].  Esto permite que SymPy calcule la antiderivada exacta
    (``sympy.Abs`` la bloquea devolviendo ``Integral(...)`` sin evaluar).

    Si el radio toma valores cercanos a cero o cambia de signo en el intervalo, el resultado
    es conservador: devuelve la expresión sin cambio de signo. La red de seguridad numérica
    ``_cross_check`` en ``calculate_revolution_volume`` captura el error en ese caso.
    """
    mid = (num_a + num_b) / 2.0
    try:
        val_mid = float((expr - reference).subs(var_sym, mid).evalf())
    except Exception:
        val_mid = 0.0
    if val_mid >= 0:
        return expr - reference
    return reference - expr


def _signed_dist(
    f_sym: sympy.Expr,
    axis_sym: sympy.Expr,
    var_sym: sympy.Symbol,
    num_a: float,
    num_b: float,
) -> sympy.Expr:
    """Distancia orientada de f(x) al eje, con signo positivo en el intervalo dado.

    Equivale a ``|f(x) - axis|`` pero sin el operador ``Abs``, que bloquea la antiderivación
    simbólica de SymPy. El signo se determina evaluando en el punto medio del intervalo.
    """
    return _signed_radius(f_sym, axis_sym, var_sym, num_a, num_b)


'''

target_order = "def _order_curves_by_distance("
assert target_order in code, "target_order not found"
code = code.replace(target_order, helper + target_order, 1)

# ── 2. Patch _order_curves_by_distance: replace Abs with _signed_dist ─────────────────────

old_order_abs = '''    # Expresiones de distancia exacta respecto al eje
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)'''

new_order_abs = '''    # Expresiones de distancia con signo correcto (sin Abs que bloquea antiderivadas en SymPy)
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = _signed_dist(f_sym, axis_sym, var_sym, num_a, num_b)
    dist_g = _signed_dist(g_sym, axis_sym, var_sym, num_a, num_b)'''

assert old_order_abs in code, "old_order_abs not found"
code = code.replace(old_order_abs, new_order_abs, 1)

# ── 3. Patch partition_washer_intervals: replace Abs with _signed_dist ────────────────────

old_pwi = '''    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)'''

new_pwi = '''    axis_sym = sympy.nsimplify(axis_val)
    dist_f = _signed_dist(f_sym, axis_sym, var_sym, num_a, num_b)
    dist_g = _signed_dist(g_sym, axis_sym, var_sym, num_a, num_b)'''

assert old_pwi in code, "old_pwi not found"
code = code.replace(old_pwi, new_pwi, 1)

# ── 4. Patch _compute_shells radius_expr: replace Abs with _signed_radius ─────────────────

old_shell_radius = '''        # Radio del casquillo: distancia desde la variable 't' al eje
        axis_pos_sym = sympy.nsimplify(axis.position)
        radius_expr = sympy.Abs(var_sym - axis_pos_sym)'''

new_shell_radius = '''        # Radio del casquillo: distancia con signo correcto (sin Abs que bloquea antiderivadas)
        axis_pos_sym = sympy.nsimplify(axis.position)
        radius_expr = _signed_radius(var_sym, axis_pos_sym, var_sym, num_a, num_b)'''

assert old_shell_radius in code, "old_shell_radius not found"
code = code.replace(old_shell_radius, new_shell_radius, 1)

# ── 5. Patch _compute_shells height_expr Abs: use unsigned diff (pieces guarantee sign) ──

old_height_abs = '''            height_expr = sympy.Abs(f_expr - g_expr)'''
new_height_abs = '''            # El signo del integrando ya está garantizado por _build_piecewise_shell_steps;
            # usar Abs aquí volvería a bloquear la antiderivada en el paso de desarrollo.
            height_expr = f_expr - g_expr  # puede ser negativo, pero sólo se usa en display'''

assert old_height_abs in code, "old_height_abs not found"
code = code.replace(old_height_abs, new_height_abs, 1)

# ── 6. Cleanup _clean_latex: improve Abs detection patterns ──────────────────────────────

old_clean_latex = '''    s_str = s_str.replace(r\'\\left|\', r\'\\left(\').replace(r\'\\right|\', r\'\\right)\')
    s_str = _re.sub(r\'\\\\operatorname\\{Abs\\}\\\\left\\(\', r\'\\\\left(\', s_str)
    s_str = _re.sub(r\'\\\\text\\{Abs\\}\\(\', r\'(\', s_str)
    return s_str'''

new_clean_latex = '''    # Normalizar Abs(...) residuales que puedan aparecer en representaciones LaTeX de SymPy
    s_str = _re.sub(r\'\\\\left\\|\', r\'\\\\left(\', s_str)
    s_str = _re.sub(r\'\\\\right\\|\', r\'\\\\right)\', s_str)
    s_str = _re.sub(r\'\\\\operatorname\\{Abs\\}\\\\left\\(\', r\'\\\\left(\', s_str)
    s_str = _re.sub(r\'\\\\text\\{Abs\\}\\(\', r\'(\', s_str)
    s_str = _re.sub(r\'\\\\operatorname\\{Abs\\}\\\\left\\((.+?)\\\\right\\)\', r\'\\\\left(\\\\1\\\\right)\', s_str)
    return s_str'''

assert old_clean_latex in code, "old_clean_latex not found"
code = code.replace(old_clean_latex, new_clean_latex, 1)

Path("integrallab/core/solids.py").write_text(code, encoding="utf-8")
print("solids.py Phase 1 patch applied successfully")


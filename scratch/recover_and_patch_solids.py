"""
Recovery script: restore solids.py from the git reference (0c507d3),
then re-apply Phase 0 and Phase 1 patches cleanly.
"""
from pathlib import Path
import subprocess, re, math, textwrap

REPO = Path(".")
REF_COMMIT = "0c507d3"

# Step 1: Get the correct full solids.py from git
result = subprocess.run(
    ["git", "show", f"{REF_COMMIT}:integrallab/core/solids.py"],
    capture_output=True,
    cwd=str(REPO)
)
if result.returncode != 0:
    raise RuntimeError(f"git show failed: {result.stderr.decode()}")

content = result.stdout.decode("utf-8")
assert "def _reject_negative" in content, "_reject_negative not in reference"
assert "def calculate_revolution_volume" in content
assert len(content) > 90_000, f"Content too small: {len(content)}"
print(f"Reference solids.py size: {len(content)} chars")

# Step 2: Apply Phase 0 patches (from apply_phase0.py)
# Fix corrupted accented chars
content = content.replace("V?lido porque el eje no atraviesa", "Válido porque el eje no atraviesa")
content = content.replace("la regi?n (axis_crossing_error ya lo garantiza)", "la región (axis_crossing_error ya lo garantiza)")

# Add _cross_check helper before calculate_revolution_volume
cross_check_def = '''

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

'''

assert "def calculate_revolution_volume(" in content
content = content.replace("def calculate_revolution_volume(", cross_check_def + "def calculate_revolution_volume(", 1)

# Wire _cross_check into the inversion return path
old_ret = """                    return _reject_negative(VolumeResult(
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
                    ))"""

new_ret = """                    return _cross_check(_reject_negative(VolumeResult(
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
                    )), region, axis)"""

assert old_ret in content, "old_ret not found"
content = content.replace(old_ret, new_ret, 1)
print("Phase 0 patches applied")

# Step 3: Apply Phase 1 patches (_signed_radius helpers, remove Abs from radii)

helper = '''

def _signed_radius(
    expr: "sympy.Expr",
    reference: "sympy.Expr",
    var_sym: "sympy.Symbol",
    num_a: float,
    num_b: float,
) -> "sympy.Expr":
    """Devuelve (expr - reference) con el signo correcto evaluado en el punto medio del intervalo.

    Reemplaza ``sympy.Abs(expr - reference)`` en contextos donde el signo es constante
    en todo el intervalo [a, b].  Esto permite que SymPy calcule la antiderivada exacta
    (``sympy.Abs`` la bloquea devolviendo ``Integral(...)`` sin evaluar).
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
    f_sym: "sympy.Expr",
    axis_sym: "sympy.Expr",
    var_sym: "sympy.Symbol",
    num_a: float,
    num_b: float,
) -> "sympy.Expr":
    """Distancia orientada de f(x) al eje, con signo positivo en el intervalo dado.

    Equivale a ``|f(x) - axis|`` pero sin el operador ``Abs``, que bloquea la antiderivación
    simbólica de SymPy. El signo se determina evaluando en el punto medio del intervalo.
    """
    return _signed_radius(f_sym, axis_sym, var_sym, num_a, num_b)

'''

target_order = "def _order_curves_by_distance("
assert target_order in content
content = content.replace(target_order, helper + target_order, 1)

# Fix _order_curves_by_distance
old_order_abs = '''    # Expresiones de distancia exacta respecto al eje
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)'''

new_order_abs = '''    # Expresiones de distancia con signo correcto (sin Abs que bloquea antiderivadas en SymPy)
    axis_sym = sympy.nsimplify(axis_val)
    dist_f = _signed_dist(f_sym, axis_sym, var_sym, num_a, num_b)
    dist_g = _signed_dist(g_sym, axis_sym, var_sym, num_a, num_b)'''

assert old_order_abs in content, "old_order_abs not found"
content = content.replace(old_order_abs, new_order_abs, 1)

# Fix partition_washer_intervals
old_pwi = '''    axis_sym = sympy.nsimplify(axis_val)
    dist_f = sympy.Abs(f_sym - axis_sym)
    dist_g = sympy.Abs(g_sym - axis_sym)'''

new_pwi = '''    axis_sym = sympy.nsimplify(axis_val)
    dist_f = _signed_dist(f_sym, axis_sym, var_sym, num_a, num_b)
    dist_g = _signed_dist(g_sym, axis_sym, var_sym, num_a, num_b)'''

assert old_pwi in content, "old_pwi not found"
content = content.replace(old_pwi, new_pwi, 1)

# Fix shell radius_expr
old_shell_radius = '''        # Radio del casquillo: distancia desde la variable 't' al eje
        axis_pos_sym = sympy.nsimplify(axis.position)
        radius_expr = sympy.Abs(var_sym - axis_pos_sym)'''

new_shell_radius = '''        # Radio del casquillo: distancia con signo correcto (sin Abs que bloquea antiderivadas)
        axis_pos_sym = sympy.nsimplify(axis.position)
        radius_expr = _signed_radius(var_sym, axis_pos_sym, var_sym, num_a, num_b)'''

assert old_shell_radius in content, "old_shell_radius not found"
content = content.replace(old_shell_radius, new_shell_radius, 1)

# Fix piecewise height_expr Abs
old_height_abs = '''            height_expr = sympy.Abs(f_expr - g_expr)'''
new_height_abs = '''            # El signo del integrando ya está garantizado por _build_piecewise_shell_steps;
            # usar Abs aquí volvería a bloquear la antiderivada en el paso de desarrollo.
            height_expr = f_expr - g_expr  # puede ser negativo, pero sólo se usa en display'''

assert old_height_abs in content, "old_height_abs not found"
content = content.replace(old_height_abs, new_height_abs, 1)

# Improve _clean_latex
old_clean = r"""    s_str = s_str.replace(r'\left|', r'\left(').replace(r'\right|', r'\right)')
    s_str = _re.sub(r'\\operatorname\{Abs\}\\left\(', r'\\left(', s_str)
    s_str = _re.sub(r'\\text\{Abs\}\(', r'(', s_str)
    return s_str"""

new_clean = r"""    s_str = _re.sub(r'\\left\|', r'\\left(', s_str)
    s_str = _re.sub(r'\\right\|', r'\\right)', s_str)
    s_str = _re.sub(r'\\operatorname\{Abs\}\\left\(', r'\\left(', s_str)
    s_str = _re.sub(r'\\text\{Abs\}\(', r'(', s_str)
    return s_str"""

assert old_clean in content, "old_clean not found"
content = content.replace(old_clean, new_clean, 1)

# Step 4: Fix also the _sq helper in _compute_disks/washers to remove Abs
# (The _sq function unwraps Abs — keep it as safety net for display LaTeX but ensure
#  the main computation uses _signed_dist above)
# Already handled via _order_curves_by_distance patch above.

# Step 5: Write updated file
Path("integrallab/core/solids.py").write_text(content, encoding="utf-8")
print(f"solids.py written: {len(content)} chars")

# Verify
with open("integrallab/core/solids.py", encoding="utf-8") as f:
    final = f.read()
import re
funcs = re.findall(r'^def \w+', final, re.MULTILINE)
print(f"Total top-level functions: {len(funcs)}")
for fn in ["_reject_negative", "_cross_check", "_signed_radius", "_signed_dist",
           "calculate_revolution_volume", "numeric_volume"]:
    found = f"def {fn}" in final
    print(f"  def {fn}: {'OK' if found else 'MISSING!'}")


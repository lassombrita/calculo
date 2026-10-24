import sys, math
from integrallab.core.solids import (
    Region2D, RevolutionAxis, AxisOrientation, SolidMethod,
    calculate_revolution_volume, numeric_volume
)


def check(desc, region, axis, method=None, expected=None):
    res = calculate_revolution_volume(region, axis, method=method)
    ref = numeric_volume(region, axis)
    if res.is_success and res.numeric_value is not None:
        sym_val = res.numeric_value
        ref_str = f"{ref:.4f}" if ref is not None else "None"
        if expected is None or math.isclose(sym_val, expected, rel_tol=1e-4):
            verdict = "OK"
        else:
            verdict = f"WRONG (want {expected:.4f})"
        blocked = "Integral" in (res.exact_latex or "")
        print(f"  {desc}: sym={sym_val:.4f}  ref={ref_str}  Abs_blocked={blocked}  {verdict}")
    else:
        print(f"  {desc}: FAIL => {res.error_message}")


print("=== Fase 1: Radios con signo correcto (sin Abs espurio) ===")

# 1. Discos x^2 alrededor del eje X en [0,1] => pi/5 ≈ 0.6283
r1 = Region2D("x**2", None, "0", "1")
check("Discos x^2 eje-X [0,1]", r1, RevolutionAxis.x_axis(), SolidMethod.DISKS,
      expected=math.pi/5)

# 2. Arandelas sqrt(x) vs x^2 alrededor del eje X en [0,1] => 3*pi/10 ≈ 0.9425
r2 = Region2D("sqrt(x)", "x**2", "0", "1")
check("Arandelas sqrt(x)-x^2 eje-X [0,1]", r2, RevolutionAxis.x_axis(), SolidMethod.WASHERS,
      expected=3*math.pi/10)

# 3. Casquillos x^2 alrededor del eje Y en [0,1] => pi/2 ≈ 1.5708
r3 = Region2D("x**2", None, "0", "1")
check("Casquillos x^2 eje-Y [0,1]", r3, RevolutionAxis.y_axis(), SolidMethod.SHELLS,
      expected=math.pi/2)

# 4. Discos y=x alrededor del eje X en [0,2] => 8*pi/3 ≈ 8.3776
r4 = Region2D("x", None, "0", "2")
check("Discos x eje-X [0,2]", r4, RevolutionAxis.x_axis(), SolidMethod.DISKS,
      expected=8*math.pi/3)

# 5. Casquillos sqrt(x) alrededor del eje x=2 en [0,1] => 28*pi/15 ≈ 5.8643
r5 = Region2D("sqrt(x)", None, "0", "1")
axis5 = RevolutionAxis(orientation=AxisOrientation.VERTICAL, position=2.0)
check("Casquillos sqrt(x) eje-x=2 [0,1]", r5, axis5, SolidMethod.SHELLS,
      expected=28*math.pi/15)

# 6. Arandelas con eje desplazado y=2: f=x, g=0 en [0,1] => 5*pi/3 ≈ 5.2360
r6 = Region2D("x", None, "0", "1")
axis6 = RevolutionAxis(orientation=AxisOrientation.HORIZONTAL, position=2.0)
check("Arandelas x eje-y=2 [0,1]", r6, axis6, SolidMethod.WASHERS,
      expected=5*math.pi/3)

print("DONE")


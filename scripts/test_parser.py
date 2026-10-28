#!/usr/bin/env python3
"""Script de pruebas para parse_math_expression - Bug fix completado."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # raíz del repositorio

from integrallab.core.parser import parse_math_expression

print("="*60)
print("TEST DE VALIDACIÓN - Parser Math Expressions")
print("="*60)
print()

tests = [
    ("x**2", "Cuadrado de x"),
    ("sqrt(x)**2", "Raíz cuadrada al cuadrado"),
    ("sin(x) + cos(x)", "Suma trigonométrica"),
    ("log(x, 10)", "Logaritmo en base 10"),
    ("abs(x)", "Valor absoluto"),
    ("pi * r**2", "Área del círculo"),
    ("(x + y)**2", "Binomio al cuadrado"),
]

passed = 0
failed = 0

for expr, description in tests:
    print(f"Test: {description}")
    print(f"Expresión: {expr}")
    try:
        result = parse_math_expression(expr)
        print(f"  ✅ Parseado correctamente")
        print(f"     Resultado simbólico: {result.sympy_expr}")
        if "x" in expr or "X" in expr:
            # Evaluar en x=2 para verificar
            from sympy import N
            x_val = result.sympy_expr.subs("x", 2)
            print(f"     Evaluado en x=2: {N(x_val, 10)}")
        passed += 1
    except Exception as e:
        print(f"  ❌ ERROR: {type(e).__name__}: {e}")
        failed += 1
    print()

print("="*60)
print(f"RESULTADOS: {passed}Passed, {failed}Failed")
print("="*60)

if failed == 0:
    print("\n✅ TODOS LOS TESTS PASARON - Bug fix completado!")
else:
    print(f"\n⚠️ {failed} test(s) fallaron. Verifica las correcciones.")
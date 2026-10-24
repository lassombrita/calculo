"""Pruebas unitarias de contención inmediata para la Fase 0 de la auditoría técnica."""
from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
import sympy

from integrallab.core.parser import (
    ExpressionParseError,
    is_points_input,
    parse_math_expression,
)
from integrallab.core.solids import (
    Region2D,
    RevolutionAxis,
    SolidMethod,
    calculate_revolution_volume,
)


def test_cosenh_alias_translates_to_cosh():
    """Verifica que 'cosenh' se normalice a cosh(x) y no a asinh(x)."""
    parsed = parse_math_expression("cosenh(x)")
    assert parsed.sympy_expr == sympy.cosh(sympy.Symbol("x"))
    val = float(parsed.sympy_expr.subs(sympy.Symbol("x"), 0))
    assert val == pytest.approx(1.0)


def test_factorial_large_argument_raises_error():
    """Verifica que factoriales astronómicos sean bloqueados antes de congelar el hilo."""
    # Válido con notación postfix
    res = parse_math_expression("5!")
    assert res.sympy_expr == sympy.Integer(120)

    # Válido con llamada funcional
    res_func = parse_math_expression("factorial(5)")
    assert res_func.sympy_expr == sympy.Integer(120)

    # Fuera de rango con postfix
    with pytest.raises(ExpressionParseError, match="hasta 1000"):
        parse_math_expression("99999999!")

    # Fuera de rango con llamada funcional
    with pytest.raises(ExpressionParseError, match="hasta 1000"):
        parse_math_expression("factorial(10000)")


def test_is_points_input_linear_time_on_large_number():
    """Verifica que una cadena numérica de 20.000 dígitos no cause retroceso exponencial."""
    long_input = "9" * 20_000
    t0 = time.perf_counter()
    result = is_points_input(long_input)
    elapsed = time.perf_counter() - t0

    assert not result
    assert elapsed < 0.05, f"is_points_input tardó {elapsed:.3f} s (límite: 50 ms)"


def test_cross_check_safety_net_catches_divergent_inversion():
    """Verifica que la red de seguridad _cross_check rechace volúmenes invertidos erróneos."""
    # x**3 en [0, 1] alrededor del eje Y con método forzado de Discos
    region = Region2D("x**3", None, "0", "1")
    axis = RevolutionAxis.y_axis()

    res = calculate_revolution_volume(region, axis, method=SolidMethod.DISKS)
    # Debe ser rechazado explicando que el planteamiento invertido no coincide con la cuadratura
    assert not res.is_success
    assert "El planteamiento invertido da" in (res.error_message or "")
    assert "Use el método directo" in (res.error_message or "")


def test_no_corrupted_question_marks_in_codebase():
    """Verifica que no existan tildes o eñes corruptas con '?' entre dos letras en integrallab/."""
    pattern = re.compile(r"[a-zA-ZáéíóúÁÉÍÓÚ]\?[a-zA-ZáéíóúÁÉÍÓÚ]")
    pkg_dir = Path(__file__).resolve().parent.parent / "integrallab"

    corrupted_occurrences = []
    for file_path in pkg_dir.rglob("*.py"):
        text = file_path.read_text(encoding="utf-8")
        for line_num, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                corrupted_occurrences.append(f"{file_path.name}:{line_num}: {line.strip()}")

    assert not corrupted_occurrences, f"Tildes corruptas detectadas:\n" + "\n".join(corrupted_occurrences)


"""Smoke test para validar la importación del paquete y las dependencias base."""

from __future__ import annotations

import integrallab


def test_package_metadata() -> None:
    """Verifica que el paquete expone la versión correctamente."""
    assert hasattr(integrallab, "__version__")
    assert integrallab.__version__ == "0.1.0"


def test_core_imports() -> None:
    """Verifica que los módulos principales del core se importan sin errores."""
    from integrallab.core import (
        differentiate,
        integrate_definite,
        integrate_indefinite,
        is_math_engine_available,
        parse_math_expression,
        sample_expression,
    )

    assert callable(parse_math_expression)
    assert callable(differentiate)
    assert callable(integrate_indefinite)
    assert callable(integrate_definite)
    assert callable(sample_expression)
    assert is_math_engine_available() is True


def test_main_entry_point_importable() -> None:
    """Verifica que el punto de entrada __main__ es importable y main es ejecutable."""
    from integrallab.__main__ import main

    assert callable(main)



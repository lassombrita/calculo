"""Paquete de árboles de pasos tipo Photomath."""

from .step_tree import (
    StepTree, StepNode, FormulaStep, TextStep, StepType,
    create_sample_photomath_tree,
)

from .latex_to_png import (
    generate_latex_image, preprocess_latex_for_mathjax, build_mathjax_html,
    is_mathjax_fallback_needed,
)

# Importar funciones de generación automática para facilitar acceso
try:
    from .sympy_to_steps import (
        generate_steps_for_integral, create_photomath_tree,
        create_photomath_steps_from_expression, create_photomath_steps_from_result,
    )
except ImportError:
    # SymPy no disponible - funciones placeholder
    def generate_steps_for_integral(*args, **kwargs):
        raise NotImplementedError("SymPy requerido para generación automática de pasos.")

    def create_photomath_tree(*args, **kwargs):
        raise NotImplementedError("SymPy requerido para generar árbol desde fórmula LaTeX.")

    def create_photomath_steps_from_expression(*args, **kwargs):
        raise NotImplementedError("SymPy requerido para generar árbol desde expresión.")

    def create_photomath_steps_from_result(*args, **kwargs):
        raise NotImplementedError("SymPy requerido para generar árbol desde resultado.")


__all__ = [
    # Clases principales
    'StepTree',
    'StepNode', 
    'FormulaStep',
    'TextStep',
    'StepType',
    
    # Funciones de generación automática
    'generate_steps_for_integral',
    'create_photomath_tree',
    'create_photomath_steps_from_expression',
    'create_photomath_steps_from_result',
    
    # Renderizado offline
    'generate_latex_image',
    'preprocess_latex_for_mathjax',
    'build_mathjax_html',
    'is_mathjax_fallback_needed',
    
    # Demo
    'create_sample_photomath_tree',
]

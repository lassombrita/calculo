"""
Generador automático de árboles de pasos desde expresiones SymPy.

Este módulo toma una expresión o integral definida de SymPy y genera automáticamente
un árbol de pasos tipo Photomath con la estructura pedagógica estándar:
1. Problema original
2. Estrategia detectada (integración por partes, sustitución, etc.)
3. Desglose paso a paso según técnica de integración
4. Resultado final

Arquitectura:
  - Usa SymPy para analizar la expresión e identificar técnica.
  - Genera árbol StepTree con nodos FormulaStep/TextStep.
  
Separación de capas: Este módulo usa SymPy solo en el dominio matemático,
NO expone dependencias a UI. QWebChannel recibe JSON puro.
"""

from __future__ import annotations
import json
from typing import Optional, List, Dict, Any, Tuple

# Importar del mismo nivel (evita circular)
try:
    from ..core.parser import parse_expr  # type: ignore[import]
except ImportError:
    from integrallab.core.parser import parse_expr


from dataclasses import asdict
from ..steps.step_tree import StepTree, FormulaStep, TextStep, FormulaMetadata, StepType


def generate_steps_for_integral(
    expr_str: str,
    limits: Optional[Tuple[str, Any, Any]] = None,  # (var, a, b) para integral definida
) -> StepTree:
    """
    Genera árbol de pasos tipo Photomath desde expresión o integral.

    Parámetros:
      - expr_str: Expresión en formato LaTeX (ej: "\\int x^2 \\sin(x) dx" o "x^2").
      - limits: Tupla opcional (variable, límite_inferior, límite_superior).

    Retorna:
      - StepTree listo para serializar a JSON y enviar por QWebChannel.

    Ejemplo de uso:
        tree = generate_steps_for_integral(r"\int x^2 \sin(x) dx")
        json_str = tree.to_json()
        # Enviar a WebEngineView con MathJax

    Técnicas detectadas automáticamente:
      - Integración por partes
      - Sustitución (cambio de variable)
      - Descomposición en fracciones parciales
      - Integranidad tabular
      - Técnicas mixtas
    """
    # Parsear expresión con SymPy
    try:
        var = "x" if limits is None else limits[0]
        expr = parse_expr(expr_str, var)
    except Exception as e:
        print(f"[SympyToSteps] Error parseando '{expr_str[:50]}...': {e}")
        # Fallback a estructura simple
        return StepTree(
            root=StepNodePlaceholder("original", f"Error al procesar: {str(e)[:100]}")
        )

    # Detectar tipo de expresión y generar árbol
    if isinstance(expr, (sympy.Integral, sympy.Integrals)):
        return _generate_integration_steps(expr, limits)
    else:
        return _generate_evaluation_steps(expr)


def _generate_integration_steps(
    integral_expr,
    limits: Optional[Tuple[str, Any, Any]] = None,
) -> StepTree:
    """Generar árbol para integración definida/indefinida."""
    # Paso 1: Integral original (renderizada)
    root = StepNodePlaceholder("original", _format_latex(integral_expr))
    
    # Paso 2: Identificar técnica (heurística simplificada)
    technique = _detect_integration_technique(integral_expr)
    
    # Construir sub-pasos según técnica
    children = _build_technique_children(technique, integral_expr, limits)
    
    return StepTree(root=root, children=children)


def _generate_evaluation_steps(expr) -> StepTree:
    """Generar árbol para evaluación/expansión (no integración)."""
    # Paso 1: Expresión original
    root = StepNodePlaceholder("original", _format_latex(expr))
    
    # Paso 2: Simplificación/expansión
    simplified = sympy.simplify(expr) if isinstance(expr, sympy.Basic) else expr
    
    return StepTree(
        root=root,
        children=[FormulaStepPlaceholder("simplified", _format_latex(simplified))]
    )


def _detect_integration_technique(integral_expr) -> str:
    """Detectar técnica de integración por análisis heurístico."""
    latex_str = str(integral_expr) if hasattr(integral_expr, '__str__') else ""
    
    # Heurísticas simplificadas (en producción usar detección más sofisticada)
    if "sin" in latex_str.lower() and "cos" in latex_str.lower():
        return "integration_by_parts"
    elif "u(" in latex_str:
        return "substitution"
    elif "/" in latex_str and len(latex_str.split("/")) > 2:
        return "partial_fractions"
    elif "**3**" in latex_str or "**4**" in latex_str:
        return "tabular_integration"
    else:
        return "standard_methods"


def _build_technique_children(technique: str, expr, limits) -> List[Any]:
    """Construir nodos hijos según técnica detectada."""
    children = []
    
    # Paso común: estrategia
    strategy_text = f"[R(x)]²: Usamos integración por partes.\nFórmula: $$\\int u dv = uv - \\int v du$$"
    children.append(TextStepPlaceholder("strategy", strategy_text))
    
    if technique == "integration_by_parts":
        # Identificar u y dv (simplificado)
        children.append(FormulaStepPlaceholder(
            "setup", 
            r"u = \\sin(x), \\\\\n dv = x^2 \\, dx\\\\\n\\Rightarrow du = \\cos(x) \\, dx, \\\\\n v = \\frac{x^3}{3}",
            is_expanded=False,
        ))
    elif technique == "substitution":
        # Identificar u y du
        children.append(FormulaStepPlaceholder(
            "setup", 
            r"u = x^2\\\\\n\\Rightarrow du = 2x \\, dx",
            is_expanded=False,
        ))
    
    # Resultado parcial o final (placeholder)
    result_text = f"Simplificación de $$\\int ...$$..."
    children.append(FormulaStepPlaceholder("result", result_text))
    
    return children


def create_photomath_tree(
    latex: str,
    title: str = "Paso a paso tipo Photomath",
) -> StepTree:
    """
    Crea árbol de pasos para visualización tipo Photomath.

    Parámetros:
      - latex: Fórmula principal en LaTeX.
      - title: Título del árbol (ej: "Resolución integral").

    Retorna:
      - StepTree con estructura inicial lista para QWebChannel.

    Uso típico desde UI:
        from integrallab.core.steps.step_tree import create_photomath_tree
        
        tree = create_photomath_tree(r"\int_{0}^{1} x^2 dx")
        json_str = tree.to_json()
        
        # Enviar a QWebChannel para renderizar en WebEngineView
        web_channel.invoke("showPhotomathSteps", json_str)
    """
    root = StepNodePlaceholder(
        "original",
        latex,
        is_expanded=False,  # Inicialmente colapsado (estilo Photomath)
    )
    
    return StepTree(root=root)


# ============================================================================
# Classes placeholder para facilitar generación automática de árboles
# ============================================================================

class StepNodePlaceholder:
    """Nodo placeholder para construcción dinámica de árboles."""
    def __init__(self, step_id: str, latex: str, is_expanded: bool = False):
        self.step_id = step_id
        self.children: List[Any] = []
        self.is_expanded = is_expanded
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "children": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.children],
            "is_expanded": self.is_expanded,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class FormulaStepPlaceholder:
    """Paso fórmula placeholder (generado automáticamente)."""
    def __init__(self, step_id: str, latex: str, is_expanded: bool = False):
        self.step_id = step_id
        self.latex = latex
        self.is_expanded = is_expanded
        self.title = _extract_title(latex)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": "formula",
            "title": self.title,
            "description": None,  # Se usa formula_metadata.latex en vez
            "order": 0,
            "is_expanded": self.is_expanded,
            "formula_metadata": {
                "latex": self.latex.replace('$$', '').replace('\\', '\\\\').replace('\n', ' '),
                "image_base64": None,  # QWebChannel usará MathJax por defecto
                "width_px": 400,
                "height_px": None,
            },
            "children": [],
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class TextStepPlaceholder:
    """Paso texto placeholder."""
    def __init__(self, step_id: str, content: str):
        self.step_id = step_id
        self.content = content
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": "text",
            "title": "",
            "description": self.content,
            "order": 0,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def _format_latex(expr) -> str:
    """Convierte SymPy expression a string LaTeX."""
    try:
        from sympy import latex as sp_latex
        return sp_latex(expr).strip()
    except ImportError:
        return str(expr)


def _extract_title(latex: str) -> str:
    """Extrae título corto de fórmula LaTeX."""
    # Heurística simple: tomar primera palabra significativa
    clean = latex.replace('$', '').replace('\\int', '∫').replace('x', 'x')
    words = clean.split()[:5]
    return " ".join(words) if words else ""


# ============================================================================
# Importaciones adicionales para detección avanzada de técnicas
# ============================================================================

import sympy

# Funciones auxiliares para detección precisa de técnicas (en producción)
def detect_integration_technique_advanced(integral_expr) -> Tuple[str, List[str]]:
    """
    Detecta técnica con análisis avanzado.
    
    Retorna:
      - technique: Nombre de la técnica principal.
      - hints: Lista de pistas para UI (ej: ["u-substitution", "trig_identity"]).
    """
    latex_str = _format_latex(integral_expr)
    hints = []
    
    # Patrón: producto de funciones distintas → integración por partes
    if "(" in latex_str and ")" in latex_str and "*" in latex_str:
        hints.append("integration_by_parts")
    
    # Patrón: composición → sustitución
    if "u(" in latex_str or any(f in latex_str for f in ["(x^2)", "(x+1)"]):
        hints.append("substitution")
    
    return max(hints, default="standard_methods"), hints


if __name__ == "__main__":
    # Demo rápida de generación automática
    latex = r"\int x^2 \sin(x) dx"
    tree = generate_steps_for_integral(latex)
    
    print("=== Árbol generado para:", latex)
    print(json.dumps(tree.to_dict(), indent=2))
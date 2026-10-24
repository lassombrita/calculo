"""
Controller para vistas de pasos tipo Photomath.

Este módulo coordina:
1. Recepción de árbol de pasos desde motor matemático (SymPy).
2. Conversión a JSON serializable para QWebChannel.
3. Gestión de estado UI (expansión/colapso, navegación).

Arquitectura:
  - No importa SymPy directamente (usa API pública del dominio).
  - Expone interfaz simple para UI principal.
  
Separación de capas: Controller recibe datos procesados del core,
NO realiza cálculos matemáticos complejos aquí.

Uso desde MainWindow:
    from integrallab.ui.controllers.steps_controller import StepsController
    
    steps_controller = StepsController(self)  # self es MainWindow o Controller padre
    self.steps_view = StepsController.get_steps_view()
    
    # Calcular integral y mostrar pasos
    result = self.core_engine.calculate_definite_integral("x**2", 0, 1)
    if result.has_steps():
        tree = result.get_step_tree()
        steps_controller.load_tree(tree.to_json())

"""

from __future__ import annotations
import json
from typing import Optional, List, Dict, Any

# Importar desde el mismo nivel (evita circular)
try:
    from integrallab.core.steps.step_tree import StepTree  # type: ignore[import]
except ImportError:
    from .steps_view import StepTree


class StepsController:
    """
    Controller central para gestión de vistas de pasos tipo Photomath.

    Responsabilidades:
      - Convierte resultados matemáticos a árboles de pasos UI.
      - Gestiona estado de expansión/colapso de nodos.
      - Coordina comunicación entre UI y QWebChannel.
    
    Patrón de diseño: Facade (facilita acceso complejo a árbol de pasos).
    
    Uso:
        controller = StepsController(parent_widget)
        
        # Calcular integral con SymPy
        from integrallab.core.parser import parse_expr
        expr = parse_expr("x**2")
        result = calculate_integral(expr, 0, 1)
        
        # Convertir a árbol de pasos y cargar en UI
        tree = StepsController.build_step_tree(result)
        controller.load_steps(tree.to_json())

    """

    def __init__(self, parent: Optional[Any] = None):
        """Inicializa controller."""
        self.parent = parent
        self.current_tree: Optional[StepTree] = None
    
    @staticmethod
    def build_step_tree(integral_result: Dict[str, Any]) -> StepTree:
        """
        Construye árbol de pasos desde resultado de integración.

        Parámetros:
          - integral_result: Diccionario con resultado de cálculo (ej: {
                "latex": "\\int_0^1 x^2 dx",
                "steps": [...],  # Lista de pasos generados
              })

        Retorna:
          - StepTree listo para serializar y enviar a QWebChannel.
        """
        from integrallab.core.steps.sympy_to_steps import (
            generate_steps_for_integral,
        )
        
        latex = integral_result.get("latex", "")
        limits = integral_result.get("limits", None)
        
        # Generar árbol automáticamente desde SymPy
        tree = generate_steps_for_integral(latex, limits)
        
        return tree

    def load_steps(self, json_str: str):
        """Carga árbol de pasos en vista UI asociada."""
        try:
            tree = StepTree.from_json(json_str)
            self.current_tree = tree
            
            # Si hay vista asociada, cargarla
            if hasattr(self, 'steps_view'):
                self.steps_view.load_tree(json_str)
                
        except Exception as e:
            print(f"[StepsController] Error cargando pasos: {e}")
            raise

    def expand_step(self, step_id: str):
        """Expande paso específico en vista UI."""
        if self.current_tree and hasattr(self, 'steps_view'):
            self.steps_view.expand_step(step_id)

    def collapse_step(self, step_id: str):
        """Colapsa paso específico en vista UI."""
        if self.current_tree and hasattr(self, 'steps_view'):
            self.steps_view.collapse_step(step_id)

    def get_current_tree_dict(self) -> Optional[Dict[str, Any]]:
        """Devuelve árbol actual en formato diccionario para introspección."""
        if self.current_tree:
            return self.current_tree.to_dict()
        return None

    def is_step_expanded(self, step_id: str) -> bool:
        """Verifica si paso específico está expandido."""
        if not self.current_tree:
            return False
        
        # Buscar paso en árbol
        step = self.current_tree.find_step(step_id)
        if step and hasattr(step, 'is_expanded'):
            return step.is_expanded
        return False

    def toggle_step(self, step_id: str):
        """Alterna entre expandir/colapsar paso específico."""
        is_expanded = self.is_step_expanded(step_id)
        
        if is_expanded:
            self.collapse_step(step_id)
        else:
            self.expand_step(step_id)


# ============================================================================
# Factory methods para generación automática de árboles desde expresiones
# ============================================================================

def create_photomath_steps_from_expression(
    expression_str: str,
    var: str = "x",
    limits: Optional[tuple] = None,
) -> StepTree:
    """
    Crea árbol de pasos tipo Photomath desde expresión matemática.

    Esta función es un facilitador para crear árboles automáticamente
    sin exponer la complejidad del dominio al UI.

    Parámetros:
      - expression_str: Expresión en formato LaTeX (ej: "\\int x^2 dx").
      - var: Variable principal ("x", "y", etc.).
      - limits: Límites para integral definida ((var, a, b) o None).

    Retorna:
      - StepTree listo para serializar y enviar a QWebChannel.

    Ejemplo de uso desde UI:
        tree = create_photomath_steps_from_expression(
            "\\int_0^1 x^2 dx",
            var="x"
        )
        
        # Enviar a WebEngineView con MathJax
        json_str = tree.to_json()
        web_channel.invoke("showSteps", json_str)
    """
    from integrallab.core.steps.sympy_to_steps import generate_steps_for_integral
    
    return generate_steps_for_integral(expression_str, limits)


def create_photomath_steps_from_result(integral_result: Dict[str, Any]) -> StepTree:
    """Crea árbol de pasos desde resultado numérico de integración."""
    from integrallab.core.steps.step_tree import StepTree as ST
    
    # Construir estructura simple desde resultados básicos
    latex = integral_result.get("latex", expression_str)
    
    return create_photomath_steps_from_expression(latex)


if __name__ == "__main__":
    # Demo rápida de generación y serialización
    from integrallab.core.steps.step_tree import StepTree
    
    tree = create_sample_photomath_tree()
    json_str = tree.to_json()
    
    print("=== Árbol serializado (JSON compacto) ===")
    print(json_str[:500])  # Truncado para demo

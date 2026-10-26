"""Manejador de clics para interactividad tipo Photomath.

Responsabilidad:
1. Capturar eventos de clic en ecuaciones renderizadas (canvas 2D/3D)
2. Mapear coordenadas del clic a expresión matemática correspondiente
3. Extraer paso específico del desarrollo analítico
4. Mostrar explicación pedagógica y resaltar región tocada

Este módulo implementa la arquitectura base para interactividad tipo Photomath:
- Detección de clics en canvas 2D (Matplotlib)
- Detección de clics en canvas 3D (Three.js wrapper)
- Extracción de región de expresión tocada
- Mapeo a paso correspondiente del desarrollo analítico
"""

from __future__ import annotations

import math
from typing import Any

from integrallab.ui.photomath.region_detector import RegionDetector
from integrallab.ui.photomath.step_extractor import StepExtractor


class PhotomathClickHandler:
    """Manejador de clics para ecuaciones renderizadas con interactividad tipo Photomath."""

    def __init__(self, canvas_width: float = 600.0, canvas_height: float = 400.0):
        """Inicializa manejador con dimensiones del canvas.

        Args:
            canvas_width: Ancho del canvas en píxeles (ej. 600).
            canvas_height: Alto del canvas en píxeles (ej. 400).
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        
        # Detectores y extractores
        self.region_detector = RegionDetector(canvas_width, canvas_height)
        self.step_extractor = StepExtractor()

        # Estado del manejo de clics
        self._click_region: str | None = None
        self._click_step_number: int | None = None
        self._click_position: tuple[float, float] | None = None

        # Callback para mostrar explicación (implementado por la UI)
        self.on_explanation_shown_callback: Any = None

    @property
    def current_click_region(self) -> str | None:
        """Región de expresión actualmente detectada."""
        return self._click_region

    @property
    def current_click_step_number(self) -> int | None:
        """Número de paso del desarrollo analítico actual."""
        return self._click_step_number

    @property
    def current_click_position(self) -> tuple[float, float] | None:
        """Posición del último clic en coordenadas canvas."""
        return self._click_position

    def on_canvas_click(
        self,
        point: tuple[float, float],
        region: str | None = None,
        step_number: int | None = None,
    ) -> dict[str, Any]:
        """Maneja evento de clic en ecuación renderizada.

        Args:
            point: Punto (x, y) del clic en coordenadas del canvas.
            region: Región de expresión tocada (si se conoce desde renderer).
            step_number: Número de paso (si se conoce desde renderer).

        Returns:
            Diccionario con información extraída:
              - detected_expression: Expresión detectada o None
              - step_data: Datos del paso extraídos o {} si no hay coincidencia
              - is_highlight_active: True si hay clic activo para resaltar
              - explanation_text: Texto de explicación pedagógica

        Example:
            >>> handler = PhotomathClickHandler()
            >>> # Configurar región detectada (ej. desde LaTeX/MathJax)
            >>> handler.region_detector.add_region(
            ...     expression="sqrt(x)**2",
            ...     x_min=100, y_min=150, x_max=250, y_max=200,
            ...     step_number=1
            ... )
            >>> # Capturar clic
            >>> result = handler.on_canvas_click(point=(175, 175))
            >>> print(f"Expresión detectada: {result['detected_expression']}")
        """
        # Si región y paso proporcionados desde renderer, usarlos directamente
        if region and step_number is not None:
            self._click_region = region
            self._click_step_number = step_number
            self._click_position = point

            result = self._handle_configured_click()
            return result

        # Si no hay región conocida, intentar detectar por coordenadas
        detected_expr, detected_step = self.region_detector.get_expression_at_point(point)
        
        if detected_expr:
            self._click_region = detected_expr
            self._click_step_number = detected_step
            self._click_position = point

            result = self._handle_configured_click()
            return result
        else:
            # Clic sin región detectada (fuera de ecuación o no mapeado)
            self._clear_current_click()
            return {
                "detected_expression": None,
                "step_data": {},
                "is_highlight_active": False,
                "explanation_text": "Clic fuera de la expresión matemática.",
                "debug_info": f"Posición del clic: ({point[0]:.1f}, {point[1]:.1f})",
            }

    def _handle_configured_click(self) -> dict[str, Any]:
        """Maneja clic cuando región y paso ya están configurados."""
        if not self._click_region:
            return {
                "detected_expression": None,
                "step_data": {},
                "is_highlight_active": False,
                "explanation_text": "No hay expresión detectada.",
            }

        # Extraer paso para expresión detectada
        step_data = self.step_extractor.get_step_for_expression(self._click_region)
        
        if not step_data:
            # No hay paso registrado, crear placeholder
            step_data = {
                "step_number": 1,
                "title": f"Análisis de expresión: {self._click_region}",
                "explanation": f"Expresión detectada: {self._click_region}. Ver desarrollo analítico completo.",
                "math_expression": "",
                "latex": "",
            }

        # Generar explicación pedagógica
        explanation_text = self._generate_explanation(step_data)

        return {
            "detected_expression": self._click_region,
            "step_data": step_data,
            "is_highlight_active": True,
            "explanation_text": explanation_text,
            "debug_info": f"Posición: {self._click_position}",
        }

    def _clear_current_click(self) -> None:
        """Limpia estado actual de clic."""
        self._click_region = None
        self._click_step_number = None
        self._click_position = None

    def _generate_explanation(self, step_data: dict[str, Any]) -> str:
        """Genera explicación pedagógica para paso extraído.

        Args:
            step_data: Diccionario con datos del paso.

        Returns:
            String con explicación formatada.
        """
        title = step_data.get("title", "Análisis")
        explanation = step_data.get("explanation", "")
        latex = step_data.get("latex", "")
        analysis = step_data.get("analysis", "")

        lines = [f"📖 **{title}**"]

        if latex:
            lines.append(f"\n\n{latex}")

        if explanation:
            lines.append(f"\n\n🔍 {explanation}")

        if analysis:
            lines.append(f"\n💡 *Análisis: {analysis}*")

        # Alternativas si existen
        alternatives = step_data.get("alternatives", [])
        if alternatives:
            lines.append("\n🔄 **Alternativas:**")
            for method, latex_alt in alternatives[:2]:  # Mostrar máximo 2 alternativas
                lines.append(f"   - {method}: {latex_alt}")

        return "\n\n".join(filter(None, lines))

    def handle_slider_click(
        self,
        slider_value: float,
        expression: str | None = None,
    ) -> dict[str, Any]:
        """Maneja clic en deslizadores (ej. para mostrar slice representativa).

        Útil cuando el usuario interactúa con controles de UI en lugar del canvas.

        Args:
            slider_value: Valor actual del slider (ej. posición t del slice).
            expression: Expresión asociada al slider (opcional).

        Returns:
            Diccionario con información extraída o None si no aplica.
        """
        if not expression:
            return {
                "detected_expression": None,
                "step_data": {},
                "is_highlight_active": False,
                "explanation_text": f"Slider en posición {slider_value:.2f}.",
            }

        # Extraer paso para expresión del slider
        step_data = self.step_extractor.get_step_for_expression(expression)
        
        if not step_data:
            step_data = {
                "step_number": 1,
                "title": f"Slice en posición t={slider_value:.2f}",
                "explanation": "Muestra disco/arandela/casquillo individual en una posición específica.",
                "math_expression": f"\\text{Slice at } t = {slider_value:.2f}",
                "latex": f"\\text{{Slice at }} t = {{slider\_value}}",
            }

        explanation_text = self._generate_explanation(step_data)

        return {
            "detected_expression": expression,
            "step_data": step_data,
            "is_highlight_active": True,
            "explanation_text": explanation_text,
            "slider_value": slider_value,
        }

    def register_region_for_expression(
        self,
        expression: str,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        step_number: int,
        latex: str | None = None,
    ) -> None:
        """Registra región de expresión para detección.

        Debe llamarse antes del primer clic en la ecuación.

        Args:
            expression: Expresión matemática (ej. "sqrt(x)**2 + sin(x)").
            x_min: Coordenada X mínima del bounds (píxeles).
            y_min: Coordenada Y mínima del bounds (píxeles).
            x_max: Coordenada X máxima del bounds (píxeles).
            y_max: Coordenada Y máxima del bounds (píxeles).
            step_number: Número de paso en desarrollo analítico.
            latex: Latex de la expresión para renderizado (opcional).
        """
        self.region_detector.add_region(
            expression=expression,
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            step_number=step_number,
        )

        # Pre-registrar paso en extractor si latex disponible
        if latex:
            step_data = {
                "step_number": step_number,
                "title": f"Paso {step_number}: Análisis de {expression}",
                "explanation": f"Expresión detectada: {expression}.",
                "math_expression": latex or "",
                "latex": latex,
            }
            self.step_extractor.register_step(expression, step_data)

    def clear_region_detection(self) -> None:
        """Limpia detección de regiones para reiniciar interactividad."""
        self.region_detector.clear_regions()
        self._clear_current_click()

    def get_debug_info(self) -> dict[str, Any]:
        """Obtiene información de depuración del manejo de clics.

        Returns:
            Diccionario con estado actual de detección.
        """
        return {
            "current_region": self._click_region,
            "current_step_number": self._click_step_number,
            "current_position": self._click_position,
            "detected_regions_count": len(self.region_detector.regions),
            "regions": [(expr, bounds) for expr, _ in self.region_detector.regions],
        }


# ─────────────────────────────────────────────────────────────────────
# Facilitador para integración con canvas de Matplotlib (ejemplo de uso)
# ─────────────────────────────────────────────────────────────────────

def setup_photomath_click_handler_for_canvas(
    canvas_widget,
    click_callback=None,
    region_callbacks: list[callable] | None = None,
) -> PhotomathClickHandler:
    """Configura manejador de clics para canvas de Matplotlib.

    Args:
        canvas_widget: Widget del canvas (ej. FigureCanvasQTAgg).
        click_callback: Callback opcional para mostrar explicación al usuario.
        region_callbacks: Lista de callbacks para eventos de región detectada.

    Returns:
        Instancia de PhotomathClickHandler configurada para el canvas.
    """
    handler = PhotomathClickHandler()

    # Conectar evento de clic del canvas
    def on_mpl_click(event):
        if event.inaxes and hasattr(event.inaxes.figure, 'canvas'):
            # Obtener coordenadas relativas al canvas
            point = event.x, event.y
            result = handler.on_canvas_click(point)
            
            if result["is_highlight_active"] and click_callback:
                click_callback(result)

        return None  # Permitir evento de clic normal

    canvas_widget.mpl_connect("button_press_event", on_mpl_click)

    if region_callbacks:
        for callback, expr in region_callbacks or []:
            if len(region_callbacks) > 0:
                handler.register_region_for_expression(
                    expression=expr,
                    x_min=50, y_min=150, x_max=250, y_max=200,  # Valores por defecto
                    step_number=1,
                )

    return handler


# ─────────────────────────────────────────────────────────────────────
# Integración con canvas 3D (Three.js wrapper)
# ─────────────────────────────────────────────────────────────────────

def setup_photomath_click_handler_for_3d_canvas(
    threejs_viewer,
    click_callback=None,
    expression_bounds: dict[str, tuple[float, float, float, float]] | None = None,
) -> PhotomathClickHandler:
    """Configura manejador de clics para canvas 3D (Three.js wrapper).

    Args:
        threejs_viewer: Viewer de Three.js con método plot_solid_mesh.
        click_callback: Callback opcional para mostrar explicación al usuario.
        expression_bounds: Diccionario con expresión y bounds para cada región.

    Returns:
        Instancia de PhotomathClickHandler configurada para el canvas 3D.
    """
    handler = PhotomathClickHandler()

    # Mapear clic en canvas 3D a coordenadas aproximadas
    def on_3d_click(point_2d):
        if not hasattr(threejs_viewer, '_photomath_handler'):
            return

        result = handler.on_canvas_click(point_2d)

        if result["is_highlight_active"] and click_callback:
            click_callback(result)

        return None

    # Configurar bounds si proporcionados
    if expression_bounds:
        for expr, bounds in expression_bounds.items():
            x_min, y_min, x_max, y_max = bounds
            handler.register_region_for_expression(
                expression=expr,
                x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
                step_number=1,
            )

    return handler


__all__ = [
    "PhotomathClickHandler",
    "setup_photomath_click_handler_for_canvas",
    "setup_photomath_click_handler_for_3d_canvas",
]
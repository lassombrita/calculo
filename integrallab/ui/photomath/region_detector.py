"""Detector de región tocada para interactividad tipo Photomath.

Responsabilidad:
1. Detectar clic en ecuación renderizada (canvas 2D o LaTeX)
2. Extraer coordenadas del punto tocado
3. Determinar expresión matemática bajo el cursor
4. Mapear a paso específico del desarrollo analítico
"""

from __future__ import annotations

import numpy as np


class RegionDetector:
    """Detector de región matemática tocada en ecuaciones renderizadas."""

    def __init__(self, canvas_width: float = 600, canvas_height: float = 400):
        """Inicializa detector con dimensiones del canvas.

        Args:
            canvas_width: Ancho del canvas en píxeles.
            canvas_height: Alto del canvas en píxeles.
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self._regions: list[tuple[str, dict]] = []  # [(expresión, bounds), ...]
        self._step_map: dict[str, int] = {}  # expresión -> número de paso

    @property
    def regions(self) -> list[tuple[str, dict]]:
        """Lista de expresiones con sus bounds mapeados a pasos."""
        return self._regions

    @property
    def step_map(self) -> dict[str, int]:
        """Mapeo de expresión a número de paso del desarrollo analítico."""
        return self._step_map

    def add_region(
        self,
        expression: str,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        step_number: int,
    ) -> None:
        """Agrega región de expresión con bounds en coordenadas canvas.

        Args:
            expression: Expresión matemática (ej. "sqrt(x)**2 + sin(x)").
            x_min: Coordenada X mínima del bounds (píxeles).
            y_min: Coordenada Y mínima del bounds (píxeles).
            x_max: Coordenada X máxima del bounds (píxeles).
            y_max: Coordenada Y máxima del bounds (píxeles).
            step_number: Número de paso en desarrollo analítico.
        """
        self._regions.append((expression, {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}))
        self._step_map[expression] = step_number

    def get_expression_at_point(self, point: tuple[float, float]) -> tuple[str | None, int | None]:
        """Obtiene expresión matemática bajo punto dado (coordenadas canvas).

        Args:
            point: Punto (x, y) en coordenadas del canvas.

        Returns:
            Tupla de (expresión encontrada o None, número de paso o None).
        """
        x, y = point
        hit_region: dict[str, dict] | None = None

        # Detectar región con clic más cercano usando centroide de bounds
        for expr, bounds in self._regions:
            cx = (bounds["x_min"] + bounds["x_max"]) / 2
            cy = (bounds["y_min"] + bounds["y_max"]) / 2
            distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

            # Si clic está dentro de los bounds (con margen de tolerancia)
            if (x >= bounds["x_min"] and x <= bounds["x_max"] and
                y >= bounds["y_min"] and y <= bounds["y_max"]):
                hit_region = bounds
                break

        if hit_region is None:
            return None, None

        # Encontrar expresión correspondiente
        for expr, bounds in self._regions:
            if bounds == hit_region:
                step_number = self._step_map[expr]
                return expr, step_number

        return None, None

    def get_nearest_expression(self, point: tuple[float, float], max_distance: float = 50.0) -> tuple[str | None, int | None]:
        """Obtiene expresión matemática más cercana al punto dado (modo aproximado).

        Útil para clics ligeramente fuera del bounds exacto.

        Args:
            point: Punto (x, y) en coordenadas del canvas.
            max_distance: Máxima distancia permitida para detectar expresión "cerca".

        Returns:
            Tupla de (expresión encontrada o None, número de paso o None).
        """
        x, y = point
        min_distance = float("inf")
        nearest_expr: str | None = None
        nearest_step: int | None = None

        for expr, bounds in self._regions:
            cx = (bounds["x_min"] + bounds["x_max"]) / 2
            cy = (bounds["y_min"] + bounds["y_max"]) / 2
            distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

            if distance < max_distance and distance < min_distance:
                min_distance = distance
                nearest_expr = expr
                nearest_step = self._step_map[expr]

        return nearest_expr, nearest_step

    def clear_regions(self) -> None:
        """Limpia todas las regiones detectadas."""
        self._regions.clear()
        self._step_map.clear()


# ─────────────────────────────────────────────────────────────────────
# Factores de mapeo para diferentes tipos de renderizado
# ─────────────────────────────────────────────────────────────────────

def map_canvas_to_math_coords(canvas_point: tuple[float, float], canvas_size: tuple[float, float]) -> tuple[float, float]:
    """Convierte coordenadas del canvas a aproximación matemática.

    Para LaTeX renderizado por MathJax/PIL, esto es una aproximación
    basada en la bounding box de cada expresión almacenada.

    Args:
        canvas_point: Punto (x, y) en coordenadas del canvas.
        canvas_size: Tamaño del canvas (width, height).

    Returns:
        Tupla de (x_math, y_math) aproximado.
    """
    x, y = canvas_point
    width, height = canvas_size

    # Normalizar a [0, 1]
    return x / width, 1.0 - y / height  # Y invertida para coordenadas matemáticas


def map_math_to_canvas_coords(math_coords: tuple[float, float], canvas_size: tuple[float, float]) -> tuple[float, float]:
    """Convierte coordenadas matemáticas a coordenadas del canvas.

    Args:
        math_coords: Punto (x, y) en coordenadas matemáticas.
        canvas_size: Tamaño del canvas (width, height).

    Returns:
        Tupla de (x_canvas, y_canvas).
    """
    x, y = math_coords
    width, height = canvas_size

    # Invertir Y para mapear a coordenadas del canvas
    return x, 1.0 - y


# ─────────────────────────────────────────────────────────────────────
# Funciones auxiliares para análisis de expresión tocada
# ─────────────────────────────────────────────────────────────────────

def extract_subexpression_at_point(
    expression: str,
    point: tuple[float, float],
    variable: str = "x"
) -> dict[str, str | float]:
    """Extrae subexpresión matemática bajo punto dado.

    Esto permite resaltar solo la parte tocada de una expresión compuesta
    (ej. en "sqrt(x)**2 + sin(x)", si tocas sqrt(x), extraer solo eso).

    Args:
        expression: Expresión completa parseada.
        point: Punto del clic (coordenadas canvas).
        variable: Variable independiente ("x" o "y").

    Returns:
        Diccionario con:
          - full_expression: Expresión completa original
          - subexpression: Subexpresión bajo el punto (o None)
          - extracted_steps: Pasos del desarrollo analítico relevantes
    """
    result = {
        "full_expression": expression,
        "subexpression": None,
        "extracted_steps": [],
        "point_x": point[0],
        "point_y": point[1],
    }

    # Para simplificación inicial, extraer toda la expresión si clic está cerca
    # Implementación completa requeriría análisis sintáctico avanzado de LaTeX/SymPy
    result["subexpression"] = expression

    return result


# ─────────────────────────────────────────────────────────────────────
# Clase para contexto de detección (opcional, expandible)
# ─────────────────────────────────────────────────────────────────────

class RegionDetectionContext:
    """Contexto adicional para análisis avanzado de detección de región."""

    def __init__(self):
        self.detected_region: str | None = None
        self.step_number: int | None = None
        self.is_valid_click: bool = False
        self.debug_info: list[str] = []
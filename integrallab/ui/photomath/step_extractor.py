"""Extractor de pasos de desarrollo analítico para interactividad tipo Photomath.

Responsabilidad:
1. Extraer paso específico del desarrollo analítico correspondiente a expresión tocada
2. Obtener explicación pedagógica del paso
3. Proporcionar contexto matemático completo (análisis, justificación, alternativas)
"""

from __future__ import annotations

import re
from typing import Any


class StepExtractor:
    """Extractor de pasos de desarrollo analítico para ecuaciones renderizadas."""

    def __init__(self):
        """Inicializa extractor con base de conocimientos pedagógica."""
        self._step_registry: dict[str, dict] = {}  # expresión -> registro de pasos
        self._initialize_step_registry()

    def _initialize_step_registry(self) -> None:
        """Inicializa registro de pasos con ejemplos para diferentes tipos de expresión.

        Este registro puede expandirse dinámicamente según las expresiones calculadas.
        """
        # Ejemplos predefinidos para diferentes tipos de integración

        # Paso 1: Identificar el tipo de integral
        self._step_registry["sqrt(x)**2"] = {
            "step_number": 1,
            "title": "Identificación del integrando",
            "explanation": "Se identifica que sqrt(x)**2 simplifica a x en el dominio real positivo.",
            "math_expression": r"\sqrt{x}^2 \xrightarrow{\text{simplificar}} x",
            "latex": r"\\sqrt{x}^2 = x \\quad (\\text{para } x \\ge 0)",
            "analysis": "La raíz cuadrada al cuadrado se simplifica directamente: √(x²) = |x|. Para x ≥ 0, esto es igual a x.",
            "justification": "Propiedad de inversas: f(x) = √x y g(x) = x² son inversas cuando restringidas a dominios apropiados.",
            "alternatives": [
                ("simplificar algebraicamente", r"\\sqrt{x}^2 = |x| = x \\quad (\\text{para } x \\ge 0)"),
                ("analizar dominio", r"\\text{Dom}(\\sqrt{x}) = [0, \\infty)"),
            ],
        }

        self._step_registry["sin(x) + cos(x)"] = {
            "step_number": 1,
            "title": "Identificación de la función compuesta",
            "explanation": "La expresión contiene dos funciones trigonométricas que se suman.",
            "math_expression": r"f(x) = \\sin(x) + \\cos(x)",
            "latex": r"f(x) = \\sin(x) + \\cos(x)",
            "analysis": "Función compuesta de seno y coseno. Se puede analizar por separado o usar identidad trigonométrica.",
            "justification": "Funciones elementales de trigonometría con dominio [-∞, ∞] y rango [-1, 1].",
            "alternatives": [
                ("usar identidad", r"\\sin(x) + \\cos(x) = \\sqrt{2}\\sin(x + \\pi/4)"),
                ("analizar por partes", r"f_1(x) = \\sin(x), \\quad f_2(x) = \\cos(x)"),
            ],
        }

        # Paso 2: Preparar para integración (cuando aplica)
        self._step_registry["integral_sqrt"] = {
            "step_number": 2,
            "title": "Preparación para integración",
            "explanation": "Se prepara el integrando aplicando simplificaciones algebraicas.",
            "math_expression": r"\\int \\sqrt{x}^2\\,dx = \\int x\\,dx",
            "latex": r"\\int \\sqrt{x}^2\\,dx = \\int x\\,dx",
            "analysis": "Antes de integrar, simplificamos el integrando: √(x²) = x para x ≥ 0.",
            "justification": "La integración es más fácil después de simplificar el integrando. Simplificación algebraica previa.",
            "alternatives": [
                ("integrar directamente", r"\\int \\sqrt{x}^2\\,dx"),
                ("sustitución u = x", r"u = \\sqrt{x}, \\quad du = \\frac{1}{2\\sqrt{x}}dx"),
            ],
        }

        # Paso 3: Aplicar regla de potencia (para polinomios)
        self._step_registry["power_rule"] = {
            "step_number": 3,
            "title": "Aplicación de la regla de potencia",
            "explanation": "Se aplica la regla general ∫x^n dx = x^(n+1)/(n+1) + C.",
            "math_expression": r"\\int x^2\\,dx = \\frac{x^{2+1}}{2+1} = \\frac{x^3}{3}",
            "latex": r"\\int x^n\\,dx = \\frac{x^{n+1}}{n+1} + C",
            "analysis": "Regla de potencia para integración: aumentamos el exponente y dividimos por el nuevo exponente.",
            "justification": "La regla de potencia es caso especial de la regla fundamental del cálculo.",
            "alternatives": [
                ("definición límite", r"\\lim_{n\\to\\infty}\\sum f(x_i)\\Delta x"),
                ("integración por partes (no aplicable)", r"u=x, \\quad dv=x^2dx \\quad (sobresimplificación)"),
            ],
        }

    def get_step_for_expression(self, expression: str) -> dict[str, Any] | None:
        """Obtiene paso correspondiente para expresión dada.

        Args:
            expression: Expresión matemática (ej. "sqrt(x)**2", "sin(x) + cos(x)").

        Returns:
            Diccionario con registro de paso o None si no hay coincidencia.
        """
        expr_lower = expression.lower()

        # Buscar en registry por expresión exacta o parcial
        for key, step_data in self._step_registry.items():
            if key in expr_lower or expr_lower in key:
                return step_data.copy()

        return None

    def get_all_steps_for_expression(self, expression: str) -> list[dict[str, Any]]:
        """Obtiene todos los pasos relevantes para expresión compleja.

        Para expresiones compuestas (ej. "sqrt(x)**2 + sin(x)"), devuelve
        múltiples pasos correspondientes a subexpresiones diferentes.

        Args:
            expression: Expresión matemática completa.

        Returns:
            Lista de diccionarios con registros de pasos relevantes.
        """
        # Tokenizar expresión en subexpresiones
        tokens = self._tokenize_expression(expression)
        steps = []

        for token in tokens:
            step = self.get_step_for_expression(token)
            if step:
                steps.append(step)

        return steps

    def _tokenize_expression(self, expression: str) -> list[str]:
        """Tokeniza expresión matemática en subexpresiones relevantes.

        Divide expresión por operadores de alto nivel (+, -, *, /) manteniendo
        paréntesis intactos.

        Args:
            expression: Expresión matemática completa.

        Returns:
            Lista de subexpresiones tokenizadas.
        """
        # Simplificar primero (quitar espacios)
        expr = re.sub(r'\s+', '', expression)

        tokens = []
        current_token = ""
        paren_depth = 0

        for char in expr:
            if char == "(":
                paren_depth += 1
                current_token += char
            elif char == ")":
                paren_depth -= 1
                current_token += char
            elif char in "+-*/" and paren_depth == 0:
                tokens.append(current_token.strip())
                current_token = ""
            else:
                current_token += char

        # Agregar último token si existe
        if current_token.strip():
            tokens.append(current_token.strip())

        return tokens

    def register_step(self, expression: str, step_data: dict[str, Any]) -> None:
        """Registra nuevo paso para expresión (para uso dinámico).

        Útil cuando se calculan nuevas expresiones analíticamente.

        Args:
            expression: Expresión matemática.
            step_data: Diccionario con datos del paso (title, explanation, etc.).
        """
        self._step_registry[expression] = step_data.copy()

    def get_step_by_number(self, expression: str, step_number: int) -> dict[str, Any] | None:
        """Obtiene paso por número secuencial para expresión.

        Args:
            expression: Expresión matemática.
            step_number: Número de paso (1, 2, 3, ...).

        Returns:
            Diccionario con datos del paso o None si no existe.
        """
        all_steps = self.get_all_steps_for_expression(expression)

        # Filtrar por número de paso
        for step in all_steps:
            if step["step_number"] == step_number:
                return step

        return None


# ─────────────────────────────────────────────────────────────────────
# Funciones auxiliares para extraer información pedagógica
# ─────────────────────────────────────────────────────────────────────

def extract_common_steps(
    expression_type: str,
    integral_variable: str = "x",
) -> list[tuple[str, dict]]:
    """Extrae pasos comunes para tipo de expresión dado.

    Args:
        expression_type: Tipo de expresión (ej. "sqrt", "sin", "integral", etc.).
        integral_variable: Variable de integración ("x" o "y").

    Returns:
        Lista de tuplas (paso_num, dict con datos del paso).
    """
    steps = [
        (1, {
            "title": "Identificación del integrando",
            "explanation": f"Se identifica el integrando en función de la variable {integral_variable}.",
        }),
        (2, {
            "title": "Simplificación del integrando (si aplica)",
            "explanation": "Aplicamos simplificaciones algebraicas o trigonométricas para facilitar la integración.",
        }),
        (3, {
            "title": "Preparación para integración",
            "explanation": "Escribimos la integral en forma estándar preparada para aplicar reglas de integración.",
        }),
    ]

    return steps


def get_latex_rendering(step_data: dict[str, Any]) -> str:
    """Extrae LaTeX para renderizado del paso.

    Args:
        step_data: Diccionario con datos del paso.

    Returns:
        Cadena LaTeX formateada o string vacío si no hay LaTeX disponible.
    """
    latex = step_data.get("latex", "")
    math_expr = step_data.get("math_expression", "")

    if latex:
        return latex
    elif math_expr:
        return math_expr.replace("\\\\frac", "\\dfrac")  # Mejor fraccionamiento
    else:
        return ""


def format_step_display(step_number: int, title: str, expression: str) -> str:
    """Formatea paso para visualización en UI.

    Args:
        step_number: Número secuencial del paso.
        title: Título descriptivo del paso.
        expression: Expresión matemática LaTeX o texto plano.

    Returns:
        String formateado para mostrar en UI.
    """
    return (
        f"🔹 Paso {step_number}: {title}\n\n"
        f"{expression}" if expression else ""
    )
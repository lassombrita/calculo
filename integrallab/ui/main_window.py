"""Módulo de ventana principal de la interfaz gráfica de IntegralLab.

Responsabilidad:
Conectar la entrada del usuario (expresión matemática) con el motor de cálculo
simbólico (integrallab.core) y el widget de visualización (integrallab.viz.canvas).
Esta capa no importa SymPy directamente; toda la matemática va por el dominio.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from integrallab.core.operations import integrate_definite
from integrallab.core.parser import ExpressionParseError, parse_math_expression
from integrallab.core.sampling import sample_expression
from integrallab.viz.canvas import PlotCanvas

# Rango de visualización por defecto
_DEFAULT_X_MIN: float = -10.0
_DEFAULT_X_MAX: float = 10.0
_DEFAULT_POINTS: int = 400


class MainWindow(QMainWindow):
    """Ventana principal de IntegralLab.

    Organiza el campo de entrada de la función, los límites de integración,
    el botón de graficado/cálculo, la etiqueta de resultado y el lienzo de Matplotlib.
    La comunicación entre capas se realiza exclusivamente mediante
    objetos del dominio (ParsedExpression, CurveData, NumericResult).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construye la ventana principal con todos sus widgets.

        Args:
            parent: Widget padre opcional (None para ventana de nivel superior).
        """
        super().__init__(parent)
        self.setWindowTitle("IntegralLab — Visualizador de funciones y cálculo integral")
        self.setMinimumSize(850, 620)

        # Widget central y layout raíz
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(12, 12, 12, 8)
        root_layout.setSpacing(8)

        # ── Fila 1: Entrada de función y botón Graficar ───────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        input_label = QLabel("f(x) =")
        input_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        input_row.addWidget(input_label)

        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText(
            "Escribe una función, ej: sin(x), x**2, 1/x ..."
        )
        self.expression_input.returnPressed.connect(self._on_plot_clicked)
        self.expression_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        input_row.addWidget(self.expression_input)

        self.plot_button = QPushButton("Graficar")
        self.plot_button.setFixedWidth(110)
        self.plot_button.clicked.connect(self._on_plot_clicked)
        input_row.addWidget(self.plot_button)

        root_layout.addLayout(input_row)

        # ── Fila 2: Límites de integración y resultado de la integral ──────
        limits_row = QHBoxLayout()
        limits_row.setSpacing(8)

        label_a = QLabel("Límite a =")
        label_a.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        limits_row.addWidget(label_a)

        self.limit_a_input = QLineEdit()
        self.limit_a_input.setPlaceholderText("ej. 0")
        self.limit_a_input.setFixedWidth(80)
        self.limit_a_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_a_input)

        label_b = QLabel("Límite b =")
        label_b.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        limits_row.addWidget(label_b)

        self.limit_b_input = QLineEdit()
        self.limit_b_input.setPlaceholderText("ej. 2")
        self.limit_b_input.setFixedWidth(80)
        self.limit_b_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_b_input)

        self.result_label = QLabel("Área / Integral: —")
        self.result_label.setStyleSheet(
            "font-weight: bold; color: #2c3e50; padding-left: 8px;"
        )
        self.result_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        limits_row.addWidget(self.result_label)

        root_layout.addLayout(limits_row)

        # ── Lienzo de gráfica ──────────────────────────────────────────────
        self.canvas = PlotCanvas(parent=central_widget)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root_layout.addWidget(self.canvas)

        # ── Barra de estado ────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo. Escribe una función y pulsa Graficar.")

        # Cuando False, _show_parse_error no abre el diálogo modal (útil en tests headless).
        self._show_dialogs: bool = True

    # ── Manejadores de eventos ─────────────────────────────────────────────

    def _on_plot_clicked(self) -> None:
        """Slot que reacciona al clic del botón o Enter en los campos de texto.

        Flujo de datos (sin tocar SymPy directamente):
        1. Leer texto de f(x).
        2. Parsear a ParsedExpression (valida sintaxis).
        3. Muestrear en rango [-10, 10] y graficar la curva en el canvas.
        4. Si se especifican límites a y b:
           - Calcular la integral definida vía operations.integrate_definite.
           - Mostrar el resultado exacto y aproximado en self.result_label.
           - Sombrear la región correspondiente en el canvas.
        """
        raw_text = self.expression_input.text().strip()

        if not raw_text:
            self.status_bar.showMessage("⚠ El campo de función está vacío.")
            return

        # Paso 1: Parseo y validación de sintaxis vía el dominio
        try:
            parsed = parse_math_expression(raw_text)
        except ExpressionParseError as exc:
            self._show_parse_error(str(exc))
            return

        # Paso 2: Muestreo numérico de la función completa
        label = f"f(x) = {parsed.plain_text}"
        curve = sample_expression(
            parsed,
            x_min=_DEFAULT_X_MIN,
            x_max=_DEFAULT_X_MAX,
            num_points=_DEFAULT_POINTS,
            label=label,
        )

        if not curve.is_valid:
            self._show_parse_error(curve.error_message or "Error al evaluar la función.")
            return

        # Paso 3: Renderizado de la curva principal
        self.canvas.plot_curve(curve)

        # Paso 4: Procesar límites e integral si están presentes
        a_text = self.limit_a_input.text().strip()
        b_text = self.limit_b_input.text().strip()

        if a_text and b_text:
            self._calculate_and_shade_integral(parsed, a_text, b_text)
        else:
            self.result_label.setText("Área / Integral: —")
            self.status_bar.showMessage(f"✔ Graficada: {label}")

    def _parse_limit_to_float(self, limit_text: str) -> float | None:
        """Convierte una cadena de límite (número o expresión como 'pi') a float.

        Args:
            limit_text: Texto del límite ingresado.

        Returns:
            Valor float aproximado o None si no es convertible.
        """
        try:
            return float(limit_text)
        except ValueError:
            try:
                parsed_lim = parse_math_expression(limit_text)
                if parsed_lim.sympy_expr is not None:
                    return float(parsed_lim.sympy_expr.evalf())
            except Exception:
                return None
        return None

    def _calculate_and_shade_integral(
        self,
        parsed_expr: object,
        a_text: str,
        b_text: str,
    ) -> None:
        """Calcula la integral definida y sombrea el área bajo la curva."""
        a_val = self._parse_limit_to_float(a_text)
        b_val = self._parse_limit_to_float(b_text)

        if a_val is None or b_val is None:
            self.result_label.setText("Área / Integral: Error en límites")
            self._show_parse_error(
                "Los límites de integración deben ser números o constantes válidas (ej. 0, 3, pi)."
            )
            return

        res = integrate_definite(parsed_expr, a_text, b_text)  # type: ignore[arg-type]

        if not res.is_success:
            self.result_label.setText("Área / Integral: Error en cálculo")
            self._show_parse_error(f"Error al integrar: {res.error_message}")
            return

        # Formatear el texto de resultado
        approx_str = f" ≈ {res.value:.4f}" if res.value is not None else ""
        self.result_label.setText(
            f"∫ [{a_text}, {b_text}] = {res.exact_plain_text}{approx_str}"
        )

        if a_val is not None and b_val is not None and a_val != b_val:
            x_start = min(a_val, b_val)
            x_end = max(a_val, b_val)
            shade_curve = sample_expression(
                parsed_expr,  # type: ignore[arg-type]
                x_min=x_start,
                x_max=x_end,
                num_points=120,
            )
            if shade_curve.is_valid:
                self.canvas.shade_region(
                    shade_curve.x_values,
                    shade_curve.y_values,
                    color="#3498db",
                    alpha=0.35,
                    label=f"Área [{a_text}, {b_text}]",
                )

        self.status_bar.showMessage(
            f"✔ Integral calculada: ∫ [{a_text}, {b_text}] = {res.exact_plain_text}{approx_str}"
        )

    def _show_parse_error(self, message: str) -> None:
        """Muestra un error de parseo/evaluación en la UI sin lanzar excepción.

        Args:
            message: Texto descriptivo del error.
        """
        self.status_bar.showMessage(f"✖ Error: {message}")
        if not self._show_dialogs:
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Error en la expresión")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("No se pudo interpretar la expresión matemática.")
        dialog.setInformativeText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

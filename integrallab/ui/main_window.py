"""Módulo de ventana principal de la interfaz gráfica de IntegralLab.

Responsabilidad:
Orquestar la interfaz gráfica educativa conectando la entrada matemática del usuario
con el dominio de cálculo simbólico y sólidos de revolución (integrallab.core)
y los lienzos de visualización 2D y 3D (integrallab.viz).
Esta capa no importa SymPy directamente; toda la lógica matemática pasa por el dominio.
"""

from __future__ import annotations

import os
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from integrallab.core.interpolation import (
    interpolate_cubic_spline,
    interpolate_lagrange,
)
from integrallab.core.operations import integrate_definite
from integrallab.core.parser import (
    ExpressionParseError,
    is_points_input,
    parse_math_expression,
    parse_numeric_or_symbolic,
    parse_points,
)
from integrallab.core.sampling import robust_y_window, sample_expression
from integrallab.core.solids import (
    AxisOrientation,
    MethodRecommendation,
    Region2D,
    RevolutionAxis,
    SolidMethod,
    VolumeResult,
    calculate_revolution_volume,
    can_invert_for_method,
    generate_solid_mesh,
    is_method_compatible,
    recommend_method,
)
from integrallab.ui.theme import Palette, build_palette, build_stylesheet
from integrallab.ui.widgets.aurora import AuroraBackground
from integrallab.ui.widgets.glass import GlassCard
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.threejs_wrapper import ThreeJSViewer, WEBENGINE_AVAILABLE
from integrallab.viz.latex_render import latex_to_base64_html
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

# Rango de visualización 2D por defecto
_DEFAULT_X_MIN: float = -10.0
_DEFAULT_X_MAX: float = 10.0
_DEFAULT_POINTS: int = 400



from dataclasses import dataclass

@dataclass
class CalculationOutput:
    """Contenedor de resultados del cálculo en segundo plano."""
    res_2d: Any
    region: Region2D
    rec: MethodRecommendation
    vol_res: VolumeResult
    mesh: Any
    axis: RevolutionAxis
    chosen_method: SolidMethod | None


class CalculationWorker(QThread):
    """Worker en hilo secundario para cálculos simbólicos y de mallas 3D sin congelar la UI."""
    calculation_finished = Signal(object)
    calculation_error = Signal(str)

    def __init__(
        self,
        raw_f: str,
        raw_g: str,
        parsed_f: object,
        parsed_g: object | None,
        a_text: str,
        b_text: str,
        axis: RevolutionAxis,
        chosen_method: SolidMethod | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.raw_f = raw_f
        self.raw_g = raw_g
        self.parsed_f = parsed_f
        self.parsed_g = parsed_g
        self.a_text = a_text
        self.b_text = b_text
        self.axis = axis
        self.chosen_method = chosen_method
        self.is_cancelled = False

    def cancel(self) -> None:
        self.is_cancelled = True

    def run(self) -> None:
        try:
            if self.is_cancelled:
                return

            if self.parsed_g is not None:
                diff_parsed = parse_math_expression(f"({self.raw_f}) - ({self.raw_g})")
                res_2d = integrate_definite(diff_parsed, self.a_text, self.b_text)
            else:
                res_2d = integrate_definite(self.parsed_f, self.a_text, self.b_text)  # type: ignore[arg-type]

            if self.is_cancelled:
                return

            region = Region2D(
                f_expr=self.raw_f,
                g_expr=self.raw_g if self.raw_g else None,
                a=self.a_text,
                b=self.b_text,
                variable="x",
            )
            rec = recommend_method(region, self.axis)
            vol_res = calculate_revolution_volume(region, self.axis, method=self.chosen_method)

            if self.is_cancelled:
                return

            mesh = generate_solid_mesh(region, self.axis, num_radial=24, num_axial=18)

            output = CalculationOutput(
                res_2d=res_2d,
                region=region,
                rec=rec,
                vol_res=vol_res,
                mesh=mesh,
                axis=self.axis,
                chosen_method=self.chosen_method,
            )
            self.calculation_finished.emit(output)
        except Exception as exc:
            self.calculation_error.emit(str(exc))


class MainWindow(QMainWindow):
    """Ventana principal de IntegralLab.

    Integra:
    - Panel de configuración: funciones f(x) y g(x), límites de integración,
      eje de rotación cartesiano/desplazado, y selector de método de revolución.
    - Área de visualización con pestañas:
      * Pestaña 1: Región 2D (curvas y sombreado con Matplotlib).
      * Pestaña 2: Sólido 3D (malla tridimensional translúcida y eje de rotación con Axes3D).
    - Panel pedagógico de resultados: volumen exacto, numérico, fórmula e interpretación.
    """

    # Índice del combo de método -> método del dominio (0 = Automático = None).
    _METHOD_BY_INDEX: dict[int, SolidMethod] = {
        1: SolidMethod.DISKS,
        2: SolidMethod.WASHERS,
        3: SolidMethod.SHELLS,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construye la ventana principal con todos sus widgets y layouts."""
        super().__init__(parent)
        # Tema ANTES de crear widgets: la barra de Matplotlib tiñe sus iconos con la paleta.
        self.setPalette(build_palette())
        self.setStyleSheet(build_stylesheet())
        self.setWindowTitle("IntegralLab — Visualizador de Cálculo Integral y Sólidos de Revolución")
        self.resize(1320, 820)
        self.setMinimumSize(1040, 680)

        # Widget central y layout horizontal principal (panel lateral + pestañas gráficas)
        central_widget = AuroraBackground()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(18)

        # ── Panel lateral de configuración y resultados (izquierda) ────────
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(360)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        # Grupo 1: Región y Funciones
        region_group = QGroupBox("1. Definición de la Región 2D")
        region_layout = QVBoxLayout(region_group)
        region_layout.setSpacing(6)

        # Función f(x)
        f_row = QHBoxLayout()
        f_label = QLabel("f(x) =")
        f_label.setFixedWidth(45)
        f_row.addWidget(f_label)
        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText("ej. sin(x), x**2, sqrt(x)...")
        self.expression_input.returnPressed.connect(self._on_plot_clicked)
        f_row.addWidget(self.expression_input)
        region_layout.addLayout(f_row)

        # Segunda función g(x) (opcional)
        g_row = QHBoxLayout()
        g_label = QLabel("g(x) =")
        g_label.setFixedWidth(45)
        g_row.addWidget(g_label)
        self.g_expression_input = QLineEdit()
        self.g_expression_input.setPlaceholderText("Opcional: segunda curva, ej. x**2")
        self.g_expression_input.returnPressed.connect(self._on_plot_clicked)
        g_row.addWidget(self.g_expression_input)
        region_layout.addLayout(g_row)

        # Límites a y b
        limits_row = QHBoxLayout()
        limits_row.setSpacing(8)
        label_a = QLabel("Límite a =")
        limits_row.addWidget(label_a)
        self.limit_a_input = QLineEdit()
        self.limit_a_input.setPlaceholderText("ej. 0")
        self.limit_a_input.setFixedWidth(65)
        self.limit_a_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_a_input)

        label_b = QLabel("Límite b =")
        limits_row.addWidget(label_b)
        self.limit_b_input = QLineEdit()
        self.limit_b_input.setPlaceholderText("ej. 2")
        self.limit_b_input.setFixedWidth(65)
        self.limit_b_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_b_input)
        region_layout.addLayout(limits_row)

        sidebar_layout.addWidget(region_group)

        # Grupo 2: Sólido de Revolución y Método
        solid_group = QGroupBox("2. Configuración del Sólido 3D")
        solid_layout = QVBoxLayout(solid_group)
        solid_layout.setSpacing(6)

        # Selector de Eje de Rotación
        axis_type_row = QHBoxLayout()
        axis_label = QLabel("Eje de giro:")
        axis_type_row.addWidget(axis_label)
        self.axis_combo = QComboBox()
        self.axis_combo.addItems([
            "Eje X (y = 0)",
            "Eje Y (x = 0)",
            "Horizontal (y = k)",
            "Vertical (x = h)",
        ])
        self.axis_combo.currentIndexChanged.connect(self._on_axis_combo_changed)
        axis_type_row.addWidget(self.axis_combo)
        solid_layout.addLayout(axis_type_row)

        # Valor del eje desplazado
        axis_pos_row = QHBoxLayout()
        self.axis_pos_label = QLabel("Posición k / h:")
        axis_pos_row.addWidget(self.axis_pos_label)
        self.axis_value_input = QLineEdit("0")
        self.axis_value_input.setPlaceholderText("ej. 2 o -1")
        self.axis_value_input.setEnabled(False)
        self.axis_value_input.returnPressed.connect(self._on_plot_clicked)
        axis_pos_row.addWidget(self.axis_value_input)
        solid_layout.addLayout(axis_pos_row)

        # Selector de Método
        method_row = QHBoxLayout()
        method_label = QLabel("Método:")
        method_row.addWidget(method_label)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Automático (Recomendado)",
            "Discos",
            "Arandelas",
            "Casquillos",
        ])
        self.method_combo.setToolTip(
            "Automático elige el método según el eje. Los métodos no aplicables "
            "al eje elegido aparecen deshabilitados."
        )
        self.method_combo.currentIndexChanged.connect(self._on_method_combo_changed)
        method_row.addWidget(self.method_combo)
        solid_layout.addLayout(method_row)

        # Botón principal
        self.plot_button = QPushButton("⚙  Generar Gráficas y Sólido")
        self.plot_button.setObjectName("PrimaryButton")
        self.plot_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plot_button.clicked.connect(self._on_plot_clicked)
        solid_layout.addWidget(self.plot_button)

        sidebar_layout.addWidget(solid_group)

        # Grupo 3: Resultados y Justificación Pedagógica
        results_group = QGroupBox("3. Resultados y Análisis Pedagógico")
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(6)

        self.result_label = QLabel("Área / Integral: —")
        self.result_label.setObjectName("Result")
        self.result_label.setWordWrap(True)
        results_layout.addWidget(self.result_label)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText(
            "Aquí aparecerá el desarrollo pedagógico, el volumen exacto y la justificación del método."
        )
        self.results_text.setObjectName("Paper")
        results_layout.addWidget(self.results_text)

        sidebar_layout.addWidget(results_group)
        sidebar_card = GlassCard(radius=22, glow=Palette.CYAN)
        sidebar_card_layout = QVBoxLayout(sidebar_card)
        sidebar_card_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_card_layout.addWidget(sidebar_widget)
        main_layout.addWidget(sidebar_card)

        # ── Área gráfica principal con QTabWidget (derecha) ───────────────
        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Pestaña 1: Región 2D  (canvas envuelto con barra de herramientas Matplotlib)
        canvas2d_widget = QWidget(parent=self.tab_widget)
        canvas2d_layout = QVBoxLayout(canvas2d_widget)
        canvas2d_layout.setContentsMargins(0, 0, 0, 0)
        canvas2d_layout.setSpacing(0)
        self.canvas = PlotCanvas(parent=canvas2d_widget)
        self.nav_toolbar_2d = NavigationToolbar2QT(self.canvas, self)
        canvas2d_layout.addWidget(self.nav_toolbar_2d)
        canvas2d_layout.addWidget(self.canvas)
        self.tab_widget.addTab(canvas2d_widget, "Región 2D")

        # Pestaña 2: Sólido 3D (Visor interactivo con selector de motor WebGL / Matplotlib)
        solid_widget = QWidget(parent=self.tab_widget)
        solid_layout = QVBoxLayout(solid_widget)
        solid_layout.setContentsMargins(0, 0, 0, 0)
        solid_layout.setSpacing(0)

        # Barra superior de selección de motor 3D
        engine_bar = QWidget(parent=solid_widget)
        engine_layout = QHBoxLayout(engine_bar)
        engine_layout.setContentsMargins(8, 4, 8, 4)
        engine_layout.setSpacing(8)

        engine_label = QLabel("Motor 3D:", parent=engine_bar)
        self.engine_combo = QComboBox(parent=engine_bar)
        self.engine_combo.addItems(["WebGL (Three.js)", "Matplotlib (Clásico)"])
        engine_layout.addWidget(engine_label)
        engine_layout.addWidget(self.engine_combo)
        engine_layout.addStretch()

        # Stack de visores
        self.solid_stack = QStackedWidget(parent=solid_widget)

        # Página 0: ThreeJSViewer (WebGL)
        self.threejs_viewer = ThreeJSViewer(parent=self.solid_stack)
        self.solid_stack.addWidget(self.threejs_viewer)

        # Página 1: Matplotlib (Clásico)
        mpl_container = QWidget(parent=self.solid_stack)
        mpl_layout = QVBoxLayout(mpl_container)
        mpl_layout.setContentsMargins(0, 0, 0, 0)
        mpl_layout.setSpacing(0)
        self.canvas3d = PlotCanvas3D(parent=mpl_container)
        self.nav_toolbar_3d = NavigationToolbar2QT(self.canvas3d, self)
        mpl_layout.addWidget(self.nav_toolbar_3d)
        mpl_layout.addWidget(self.canvas3d)
        self.solid_stack.addWidget(mpl_container)

        solid_layout.addWidget(engine_bar)
        solid_layout.addWidget(self.solid_stack)

        self.engine_combo.currentIndexChanged.connect(self.solid_stack.setCurrentIndex)
        self.tab_widget.addTab(solid_widget, "Sólido 3D")

        # Pestaña 3: Desarrollo analítico paso a paso
        dev_widget = QWidget(parent=self.tab_widget)
        dev_layout = QVBoxLayout(dev_widget)
        dev_layout.setContentsMargins(0, 0, 0, 0)
        dev_layout.setSpacing(0)

        self.steps_text = QTextEdit(parent=dev_widget)
        self.steps_text.setReadOnly(True)
        self.steps_text.setPlaceholderText(
            "Aquí aparecerá el desarrollo analítico paso a paso de la resolución de la integral."
        )
        self.steps_text.setObjectName("Paper")
        dev_layout.addWidget(self.steps_text)

        # Botón exportar PDF (deshabilitado hasta que se genere un sólido)
        self.export_pdf_button = QPushButton("📄 Exportar a PDF")
        self.export_pdf_button.setEnabled(False)
        self.export_pdf_button.setToolTip(
            "Genera un archivo PDF con el desarrollo analítico completo. "
            "Disponible tras calcular un sólido."
        )
        self.export_pdf_button.setObjectName("PrimaryButton")
        self.export_pdf_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_pdf_button.clicked.connect(self.export_to_pdf)
        dev_layout.addWidget(self.export_pdf_button)

        self.tab_widget.addTab(dev_widget, "Desarrollo")

        tabs_card = GlassCard(radius=22, glow=Palette.VIOLET, elevated=False)
        tabs_card_layout = QVBoxLayout(tabs_card)
        tabs_card_layout.setContentsMargins(14, 12, 14, 14)
        tabs_card_layout.addWidget(self.tab_widget)
        main_layout.addWidget(tabs_card, 1)


        # ── Barra de estado ────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo. Escribe una función y pulsa Generar Gráficas y Sólido.")

        # Cuando False, _show_parse_error no abre diálogo modal (vital para tests headless)
        self._show_dialogs: bool = True

        # Estado inicial del selector de método según el eje por defecto.
        self._update_method_availability()

    # ── Manejo de controles ────────────────────────────────────────────────

    def _on_axis_combo_changed(self, index: int) -> None:
        """Habilita la entrada numérica del eje y los métodos aplicables a ese eje."""
        is_custom = index in (2, 3)
        self.axis_value_input.setEnabled(is_custom)
        if not is_custom:
            self.axis_value_input.setText("0")
        self._update_method_availability()

    def _update_method_availability(self) -> None:
        """Deshabilita en el combo los métodos que no aplican al eje elegido.

        La región siempre se integra respecto a x, así que un eje horizontal admite
        Discos/Arandelas y un eje vertical admite Casquillos (regla del dominio:
        ``is_method_compatible``). Si el método seleccionado deja de ser aplicable,
        se vuelve a Automático.
        """
        idx = self.axis_combo.currentIndex()
        probe = RevolutionAxis.horizontal(0.0) if idx in (0, 2) else RevolutionAxis.vertical(0.0)
        horizontal = probe.orientation == AxisOrientation.HORIZONTAL
        model = self.method_combo.model()

        f_text = self.expression_input.text().strip()
        lim_a = self.limit_a_input.text().strip()
        lim_b = self.limit_b_input.text().strip()

        probe_region = None
        if f_text and lim_a and lim_b:
            try:
                probe_region = Region2D(
                    f_expr=f_text,
                    g_expr=self.g_expression_input.text().strip() or None,
                    a=lim_a,
                    b=lim_b,
                    variable="x",
                )
            except Exception:
                probe_region = None

        for combo_index, method in self._METHOD_BY_INDEX.items():
            item = model.item(combo_index)  # type: ignore[attr-defined]
            direct = is_method_compatible(method, probe)
            invertible = False
            if not direct and probe_region is not None:
                invertible = can_invert_for_method(probe_region, probe, method)

            applicable = direct or invertible
            item.setEnabled(applicable)
            if direct:
                item.setToolTip("")
            elif invertible:
                item.setToolTip("Aplica invirtiendo analíticamente la función a términos de y (dy).")
            elif horizontal:
                item.setToolTip("Los casquillos con eje horizontal requieren integrar en dy (no invertible analíticamente).")
            else:
                item.setToolTip("Discos y arandelas con eje vertical requieren integrar en dy (no invertible analíticamente).")

        current = self.method_combo.currentIndex()
        if current in self._METHOD_BY_INDEX and not model.item(current).isEnabled():  # type: ignore[attr-defined]
            self.method_combo.blockSignals(True)
            self.method_combo.setCurrentIndex(0)
            self.method_combo.blockSignals(False)

    def _on_method_combo_changed(self, index: int) -> None:
        """Aplica de inmediato el método elegido recalculando el sólido."""
        model = self.method_combo.model()
        if index in self._METHOD_BY_INDEX and not model.item(index).isEnabled():  # type: ignore[attr-defined]
            # Selección programática de un método no aplicable: volver a Automático.
            self.method_combo.setCurrentIndex(0)
            return
        self._refresh_if_ready()

    def _refresh_if_ready(self) -> None:
        """Recalcula si f(x) y ambos límites están completos; sin diálogos modales."""
        if not (
            self.expression_input.text().strip()
            and self.limit_a_input.text().strip()
            and self.limit_b_input.text().strip()
        ):
            return
        previous = self._show_dialogs
        self._show_dialogs = False
        try:
            self._on_plot_clicked()
        finally:
            self._show_dialogs = previous

    def _get_selected_axis(self) -> RevolutionAxis:
        """Determina el RevolutionAxis configurado en la UI."""
        idx = self.axis_combo.currentIndex()
        pos_text = self.axis_value_input.text().strip() or "0"
        pos_val = self._parse_limit_to_float(pos_text)
        if pos_val is None:
            raise ValueError(f"El valor del eje '{pos_text}' no es un número válido.")

        if idx == 0:
            return RevolutionAxis.x_axis()
        elif idx == 1:
            return RevolutionAxis.y_axis()
        elif idx == 2:
            return RevolutionAxis.horizontal(pos_val)
        elif idx == 3:
            return RevolutionAxis.vertical(pos_val)
        return RevolutionAxis.x_axis()

    def _get_selected_method(self) -> SolidMethod | None:
        """Determina el método de cálculo de sólidos seleccionado."""
        return self._METHOD_BY_INDEX.get(self.method_combo.currentIndex())

    def _parse_limit_to_float(self, limit_text: str) -> float | None:
        """Convierte una cadena de límite (número o expresión como 'pi') a float de forma segura."""
        try:
            return float(limit_text)
        except ValueError:
            try:
                sym_val = parse_numeric_or_symbolic(limit_text)
                return float(sym_val.evalf())
            except Exception:
                return None
        return None

    # ── Orquestador principal ──────────────────────────────────────────────

    def _on_plot_clicked(self) -> None:
        """Slot principal que reacciona a 'Generar Gráficas y Sólido'.

        Flujo desacoplado:
        1. Leer y validar sintaxis de f(x) y opcionalmente g(x).
        2. Graficar en 2D en el rango [-10, 10].
        3. Si se definen límites a y b:
           - Calcular el área 2D y sombrear la región entre f(x) y g(x) (o y=0).
           - Construir Region2D y RevolutionAxis.
           - Solicitar al dominio recomendación pedagógica y cálculo de volumen.
           - Generar la malla 3D numérica y renderizarla en PlotCanvas3D.
           - Publicar el desarrollo analítico y justificación en results_text.
        """
        raw_f = self.expression_input.text().strip()
        raw_g = self.g_expression_input.text().strip()

        if not raw_f:
            self.status_bar.showMessage("⚠ El campo de función f(x) está vacío.")
            return

        # 0. Soporte para entrada de puntos discretos (Interpolación numérica)
        is_interpolated = False
        interp_method_name = ""
        if is_points_input(raw_f):
            try:
                pts = parse_points(raw_f)
                interp_res = interpolate_lagrange(pts) if len(pts) <= 4 else interpolate_cubic_spline(pts)
                if not interp_res.is_success:
                    self._show_parse_error(interp_res.error_message or "Error en interpolación numérica.")
                    return
                raw_f = interp_res.polynomial_plain_text
                is_interpolated = True
                interp_method_name = interp_res.method.value.capitalize()
                if not self.limit_a_input.text().strip():
                    self.limit_a_input.setText(str(pts[0][0]))
                if not self.limit_b_input.text().strip():
                    self.limit_b_input.setText(str(pts[-1][0]))
            except ExpressionParseError as exc:
                self._show_parse_error(str(exc))
                return

        # 1. Parseo y validación de expresiones matemáticas
        try:
            parsed_f = parse_math_expression(raw_f)
            parsed_g = parse_math_expression(raw_g) if raw_g else None
        except ExpressionParseError as exc:
            self._show_parse_error(str(exc))
            return

        # 2. Muestreo 2D general para el lienzo
        curve_f = sample_expression(
            parsed_f,
            x_min=_DEFAULT_X_MIN,
            x_max=_DEFAULT_X_MAX,
            num_points=_DEFAULT_POINTS,
            label=f"f(x) = {parsed_f.plain_text}",
            adaptive=True,
        )
        if not curve_f.is_valid:
            self._show_parse_error(curve_f.error_message or "Error al evaluar f(x).")
            return

        if parsed_g is not None:
            curve_g = sample_expression(
                parsed_g,
                x_min=_DEFAULT_X_MIN,
                x_max=_DEFAULT_X_MAX,
                num_points=_DEFAULT_POINTS,
                label=f"g(x) = {parsed_g.plain_text}",
                adaptive=True,
            )
            if not curve_g.is_valid:
                self._show_parse_error(curve_g.error_message or "Error al evaluar g(x).")
                return
            self.canvas.plot_curves([curve_f, curve_g], clear=True)
            self.canvas.set_y_window(robust_y_window([curve_f, curve_g]))
        else:
            self.canvas.plot_curve(curve_f, clear=True)
            self.canvas.set_y_window(robust_y_window([curve_f]))

        # 3. Procesar límites de integración y sólido 3D
        a_text = self.limit_a_input.text().strip()
        b_text = self.limit_b_input.text().strip()

        if not (a_text and b_text):
            self.canvas3d.clear_canvas()
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.clear_canvas()
            self.result_label.setText("Área / Integral: —")
            self.results_text.setPlainText(
                "Gráfica 2D trazada con éxito.\n"
                "Para calcular la integral y generar el sólido 3D, ingresa los límites 'a' y 'b'."
            )
            self.steps_text.setPlainText(
                "Gráfica 2D trazada con éxito.\n"
                "Para calcular la integral y ver el desarrollo analítico paso a paso, ingresa los límites 'a' y 'b'."
            )
            self.status_bar.showMessage(f"✔ Graficada: f(x) = {parsed_f.plain_text}")
            self.canvas.play_reveal()
            return

        self._process_region_and_solid(
            raw_f, raw_g, parsed_f, parsed_g, a_text, b_text,
            is_interpolated=is_interpolated, interp_method_name=interp_method_name
        )
        self.canvas.play_reveal()

    def _process_region_and_solid(
        self,
        raw_f: str,
        raw_g: str,
        parsed_f: object,
        parsed_g: object | None,
        a_text: str,
        b_text: str,
        is_interpolated: bool = False,
        interp_method_name: str = "",
    ) -> None:
        """Calcula el área 2D, sombreado, volumen 3D y renderizado del sólido."""
        a_val = self._parse_limit_to_float(a_text)
        b_val = self._parse_limit_to_float(b_text)

        if a_val is None or b_val is None:
            self.result_label.setText("Área / Integral: Error en límites")
            self._show_parse_error(
                "Los límites de integración deben ser números o constantes válidas (ej. 0, 3, pi)."
            )
            return

        if a_val >= b_val:
            self.result_label.setText("Área / Integral: Error en límites (a >= b)")
            self._show_parse_error(
                f"El límite inferior 'a' ({a_val}) debe ser menor que el límite superior 'b' ({b_val})."
            )
            return

        try:
            axis = self._get_selected_axis()
            chosen_method = self._get_selected_method()
        except Exception as exc:
            self.canvas3d.clear_canvas()
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.clear_canvas()
            self._show_parse_error(f"Error en configuración de sólido: {exc}")
            return

        is_testing = (not getattr(self, "_show_dialogs", True)) or os.environ.get("QT_QPA_PLATFORM") == "offscreen"

        if is_testing:
            self._execute_calculation_sync(
                raw_f, raw_g, parsed_f, parsed_g, a_text, b_text, a_val, b_val,
                axis, chosen_method, is_interpolated, interp_method_name
            )
        else:
            self._execute_calculation_async(
                raw_f, raw_g, parsed_f, parsed_g, a_text, b_text, a_val, b_val,
                axis, chosen_method, is_interpolated, interp_method_name
            )

    def _execute_calculation_sync(
        self,
        raw_f: str,
        raw_g: str,
        parsed_f: object,
        parsed_g: object | None,
        a_text: str,
        b_text: str,
        a_val: float,
        b_val: float,
        axis: RevolutionAxis,
        chosen_method: SolidMethod | None,
        is_interpolated: bool,
        interp_method_name: str,
    ) -> None:
        """Ejecuta el cálculo síncronamente (modo headless / testing)."""
        try:
            if parsed_g is not None:
                diff_parsed = parse_math_expression(f"({raw_f}) - ({raw_g})")
                res_2d = integrate_definite(diff_parsed, a_text, b_text)
            else:
                res_2d = integrate_definite(parsed_f, a_text, b_text)  # type: ignore[arg-type]
        except Exception as exc:
            self.result_label.setText("Área / Integral: Error en cálculo")
            self._show_parse_error(f"Error al integrar en 2D: {exc}")
            return

        if not res_2d.is_success:
            self.result_label.setText("Área / Integral: Error en cálculo")
            self._show_parse_error(f"Error al integrar en 2D: {res_2d.error_message}")
            return

        try:
            region = Region2D(f_expr=raw_f, g_expr=raw_g if raw_g else None, a=a_text, b=b_text, variable="x")
            rec = recommend_method(region, axis)
            vol_res = calculate_revolution_volume(region, axis, method=chosen_method)
        except Exception as exc:
            self.canvas3d.clear_canvas()
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.clear_canvas()
            self._show_parse_error(f"Error en configuración de sólido: {exc}")
            return

        if not vol_res.is_success:
            self.canvas3d.clear_canvas()
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.clear_canvas()
            err_msg = vol_res.error_message or "Error al calcular el volumen del sólido."
            self._show_parse_error(err_msg)
            self.results_text.setPlainText(f"Error al calcular el sólido de revolución:\n{err_msg}")
            self.steps_text.setPlainText(f"Error al generar el desarrollo paso a paso:\n{err_msg}")
            return

        mesh = generate_solid_mesh(region, axis, num_radial=24, num_axial=18)
        output = CalculationOutput(res_2d, region, rec, vol_res, mesh, axis, chosen_method)
        self._render_and_display_results(output, a_text, b_text, a_val, b_val, parsed_f, parsed_g, is_interpolated, interp_method_name)

    def _execute_calculation_async(
        self,
        raw_f: str,
        raw_g: str,
        parsed_f: object,
        parsed_g: object | None,
        a_text: str,
        b_text: str,
        a_val: float,
        b_val: float,
        axis: RevolutionAxis,
        chosen_method: SolidMethod | None,
        is_interpolated: bool,
        interp_method_name: str,
    ) -> None:
        """Ejecuta el cálculo en un hilo secundario sin bloquear la interfaz."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(100)

        self.status_bar.showMessage("⏳ Calculando integral y generando sólido 3D...")
        self.plot_button.setEnabled(False)
        self.plot_button.setText("⏳ Calculando...")

        self._worker = CalculationWorker(
            raw_f, raw_g, parsed_f, parsed_g, a_text, b_text, axis, chosen_method, parent=self
        )
        self._worker.calculation_finished.connect(
            lambda out: self._on_worker_finished(out, a_text, b_text, a_val, b_val, parsed_f, parsed_g, is_interpolated, interp_method_name)
        )
        self._worker.calculation_error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_finished(
        self,
        out: CalculationOutput,
        a_text: str,
        b_text: str,
        a_val: float,
        b_val: float,
        parsed_f: object,
        parsed_g: object | None,
        is_interpolated: bool,
        interp_method_name: str,
    ) -> None:
        """Callback invocado cuando el worker en segundo plano completa el cálculo."""
        self.plot_button.setEnabled(True)
        self.plot_button.setText("⚙  Generar Gráficas y Sólido")
        if not out.res_2d.is_success:
            self.result_label.setText("Área / Integral: Error en cálculo")
            self._show_parse_error(f"Error al integrar en 2D: {out.res_2d.error_message}")
            return

        if not out.vol_res.is_success:
            self.canvas3d.clear_canvas()
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.clear_canvas()
            err_msg = out.vol_res.error_message or "Error al calcular el volumen del sólido."
            self._show_parse_error(err_msg)
            self.results_text.setPlainText(f"Error al calcular el sólido de revolución:\n{err_msg}")
            self.steps_text.setPlainText(f"Error al generar el desarrollo paso a paso:\n{err_msg}")
            return

        self._render_and_display_results(out, a_text, b_text, a_val, b_val, parsed_f, parsed_g, is_interpolated, interp_method_name)

    def _on_worker_error(self, err_msg: str) -> None:
        """Callback invocado si el worker en segundo plano lanza una excepción."""
        self.plot_button.setEnabled(True)
        self.plot_button.setText("⚙  Generar Gráficas y Sólido")
        self.canvas3d.clear_canvas()
        if hasattr(self, "threejs_viewer") and self.threejs_viewer:
            self.threejs_viewer.clear_canvas()
        self._show_parse_error(f"Error en configuración de sólido: {err_msg}")

    def _render_and_display_results(
        self,
        out: CalculationOutput,
        a_text: str,
        b_text: str,
        a_val: float,
        b_val: float,
        parsed_f: object,
        parsed_g: object | None,
        is_interpolated: bool,
        interp_method_name: str,
    ) -> None:
        """Renderiza las mallas y publica los reportes pedagógicos con los resultados calculados."""
        res_2d = out.res_2d
        vol_res = out.vol_res
        rec = out.rec
        mesh = out.mesh
        axis = out.axis
        chosen_method = out.chosen_method

        # Muestreo fino para sombrear el área entre curvas en [a, b]
        shade_curve_f = sample_expression(parsed_f, x_min=a_val, x_max=b_val, num_points=120)  # type: ignore[arg-type]
        if shade_curve_f.is_valid:
            if parsed_g is not None:
                shade_curve_g = sample_expression(parsed_g, x_min=a_val, x_max=b_val, num_points=120)  # type: ignore[arg-type]
                y2_data = shade_curve_g.y_values if shade_curve_g.is_valid else 0.0
            else:
                y2_data = 0.0

            self.canvas.shade_region(
                shade_curve_f.x_values,
                shade_curve_f.y_values,
                y2_values=y2_data,
                color=Palette.VIOLET,
                alpha=0.30,
                label=f"Región [{a_text}, {b_text}]",
            )

        # Generar y dibujar la malla 3D numérica
        if mesh.is_valid:
            self.canvas3d.plot_solid_mesh(mesh, show_axis=True)
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.plot_solid_mesh(mesh, show_axis=True)
        else:
            self.canvas3d.clear_canvas()
            if hasattr(self, "threejs_viewer") and self.threejs_viewer:
                self.threejs_viewer.clear_canvas()

        # Actualizar etiquetas y reporte pedagógico
        area_str = f"∫ [{a_text}, {b_text}] = {res_2d.exact_plain_text}"
        approx_vol = (
            f" ≈ {vol_res.numeric_value:.4f}" if vol_res.numeric_value is not None else ""
        )
        self.result_label.setText(
            f"{area_str} | Volumen 3D: {vol_res.exact_plain_text}{approx_vol}"
        )

        self._display_pedagogical_report(res_2d, vol_res, rec, axis)
        self._display_steps_report(vol_res, rec, axis, a_text, b_text)
        self.export_pdf_button.setEnabled(True)

        method_note = ""
        if chosen_method is not None and vol_res.method != chosen_method:
            method_note = (
                f" ⚠ {chosen_method.value} no aplica aquí (hay hueco interior); "
                f"se usó {vol_res.method.value}."
            )
        prefix = f"✔ Interpolación ({interp_method_name}) | " if is_interpolated else "✔ "
        self.status_bar.showMessage(
            f"{prefix}Sólido generado: V = {vol_res.exact_plain_text}{approx_vol} "
            f"({vol_res.method.value}){method_note}"
        )

    def keyPressEvent(self, event) -> None:
        """Permite cancelar el cálculo en curso pulsando la tecla Escape."""
        if event.key() == Qt.Key.Key_Escape and self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.plot_button.setEnabled(True)
            self.plot_button.setText("⚙  Generar Gráficas y Sólido")
            self.status_bar.showMessage("⚠ Cálculo cancelado por el usuario.")
            return
        super().keyPressEvent(event)


    def _display_pedagogical_report(
        self,
        res_2d: object,
        vol_res: VolumeResult,
        rec: MethodRecommendation,
        axis: RevolutionAxis,
    ) -> None:
        """Formatea e inserta el análisis analítico y pedagógico en results_text."""
        method_names = {
            SolidMethod.DISKS: "Método de Discos",
            SolidMethod.WASHERS: "Método de Arandelas",
            SolidMethod.SHELLS: "Método de Casquillos Cilíndricos",
        }
        method_title = method_names.get(vol_res.method, vol_res.method.value.capitalize())

        axis_desc = f"{'Horizontal' if axis.orientation == AxisOrientation.HORIZONTAL else 'Vertical'} ({axis.label})"
        numeric_str = (
            f"V ≈ {vol_res.numeric_value:.5f} u³"
            if vol_res.numeric_value is not None
            else "No disponible"
        )

        vol_latex = f"V = {vol_res.exact_latex}" if vol_res.exact_latex else f"V = {vol_res.exact_plain_text}"
        vol_img = latex_to_base64_html(
            vol_latex,
            fontsize=13,
            color="#27ae60",
            fallback_text=f"V = {vol_res.exact_plain_text}",
        )

        setup_latex = vol_res.integral_setup_latex or vol_res.integrand_latex
        if setup_latex:
            setup_img = latex_to_base64_html(
                setup_latex,
                fontsize=12,
                color="#1e3a8a",
                fallback_text=vol_res.integrand_plain_text,
            )
        else:
            setup_img = f"<code>{vol_res.integrand_plain_text}</code>"

        html = f"""
        <div style="font-family: sans-serif; line-height: 1.4;">
            <h3 style="color: #2980b9; margin-bottom: 4px;">{method_title}</h3>
            <p><b>Eje de rotación:</b> {axis_desc}</p>
            <div style="margin: 6px 0;">
                <b>Volumen exacto:</b><br>
                {vol_img}
                <span style="font-size: 11px; color: #7f8c8d; margin-left: 6px;">({vol_res.exact_plain_text})</span>
            </div>
            <p><b>Volumen numérico:</b> <b>{numeric_str}</b></p>
            <div style="margin: 6px 0;">
                <b>Planteamiento de la integral:</b><br>
                {setup_img}
            </div>
            <hr style="border: 0; border-top: 1px solid #ddd;">
            <h4 style="color: #2c3e50; margin-bottom: 4px;">Justificación y Análisis Pedagógico:</h4>
            <p style="color: #34495e;">{rec.justification}</p>
        """

        all_warnings: list[str] = []
        if rec.limitations_or_warnings:
            all_warnings.extend(rec.limitations_or_warnings)
        if vol_res.warnings:
            all_warnings.extend(vol_res.warnings)

        if all_warnings:
            warning_text = "<br>".join(all_warnings)
            html += f"""
            <p style="color: #d35400; background-color: #fef5e7; padding: 6px; border-left: 3px solid #e67e22;">
                <b>Nota:</b> {warning_text}
            </p>
            """

        html += """
        <p style="margin-top: 10px; font-size: 11px; color: #2980b9;">
            👉 <i>Consulta la pestaña <b>'Desarrollo'</b> para ver los pasos analíticos detallados (antiderivada, evaluación y simplificación).</i>
        </p>
        </div>
        """
        self.results_text.setHtml(html)

    def _display_steps_report(
        self,
        vol_res: VolumeResult,
        rec: MethodRecommendation,
        axis: RevolutionAxis,
        a_text: str,
        b_text: str,
    ) -> None:
        """Formatea e inserta los pasos analíticos intermedios en la pestaña Desarrollo."""
        method_names = {
            SolidMethod.DISKS: "Método de Discos",
            SolidMethod.WASHERS: "Método de Arandelas",
            SolidMethod.SHELLS: "Método de Casquillos Cilíndricos",
        }
        method_title = method_names.get(vol_res.method, vol_res.method.value.capitalize())
        axis_desc = f"{'Horizontal' if axis.orientation == AxisOrientation.HORIZONTAL else 'Vertical'} ({axis.label})"

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; padding: 8px;">
            <div style="background-color: #1e3a8a; color: white; padding: 14px 18px; border-radius: 8px; margin-bottom: 16px;">
                <h2 style="margin: 0 0 4px 0; font-size: 17px; color: white;">Desarrollo Analítico Paso a Paso</h2>
                <div style="font-size: 12px; opacity: 0.95;">
                    <b>{method_title}</b> &nbsp;|&nbsp; <b>Eje de giro:</b> {axis_desc} &nbsp;|&nbsp; <b>Límites:</b> [{a_text}, {b_text}]
                </div>
            </div>
        """

        for step in vol_res.steps:
            expr_html = ""
            if step.expression_latex or step.expression_plain_text:
                if step.expression_latex:
                    img_tag = latex_to_base64_html(
                        step.expression_latex,
                        fontsize=12,
                        color="#0f172a",
                        fallback_text=step.expression_plain_text,
                    )
                else:
                    lines = step.expression_plain_text.split("\n")
                    expr_lines = "<br>".join(lines)
                    img_tag = f"<code>{expr_lines}</code>"

                expr_html = f"""
                <div style="background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 10px 14px; margin-top: 8px; border-radius: 0 4px 4px 0;">
                    {img_tag}
                </div>
                """

            html += f"""
            <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size: 13px; font-weight: bold; color: #1e40af; margin-bottom: 4px;">
                    {step.title}
                </div>
                <div style="font-size: 12px; color: #475569; line-height: 1.45;">
                    {step.explanation}
                </div>
                {expr_html}
            </div>
            """

        final_latex = f"V = {vol_res.exact_latex}" if vol_res.exact_latex else f"V = {vol_res.exact_plain_text}"
        final_img = latex_to_base64_html(
            final_latex,
            fontsize=14,
            color="#047857",
            fallback_text=f"V = {vol_res.exact_plain_text}",
        )
        approx_str = f" ≈ {vol_res.numeric_value:.5f} u³" if vol_res.numeric_value is not None else ""
        html += f"""
            <div style="background-color: #ecfdf5; border: 1px solid #a7f3d0; border-left: 5px solid #10b981; border-radius: 8px; padding: 12px 16px; margin-top: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: #065f46; margin-bottom: 6px;">
                    Resultado Final del Volumen
                </div>
                <div>
                    {final_img}
                    <span style="font-size: 13px; font-weight: bold; color: #047857; margin-left: 8px;">{approx_str}</span>
                </div>
                <div style="font-size: 11px; color: #059669; margin-top: 4px;">
                    Valor exacto: <code>{vol_res.exact_plain_text}</code>
                </div>
            </div>
        </div>
        """
        self.steps_text.setHtml(html)

    def _show_parse_error(self, message: str) -> None:
        """Muestra un error en la UI sin congelar la aplicación."""
        self.status_bar.showMessage(f"✖ Error: {message}")
        if not self._show_dialogs:
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Atención en el cálculo")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("No se pudo completar la operación solicitada.")
        dialog.setInformativeText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def export_to_pdf(self) -> None:
        """Abre el diálogo de guardado y exporta el desarrollo analítico a PDF.

        Si ``_show_dialogs`` es False (modo headless / tests), no muestra el
        diálogo de fichero y retorna sin hacer nada.
        """
        if not self._show_dialogs:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar desarrollo analítico a PDF",
            "IntegralLab_Desarrollo.pdf",
            "Documentos PDF (*.pdf)",
        )

        if not file_path:
            return

        success = self._export_to_pdf_path(file_path)
        if success:
            self.status_bar.showMessage(f"✔ PDF exportado correctamente: {file_path}")
        else:
            self.status_bar.showMessage("✖ No se pudo exportar el PDF.")

    def _export_to_pdf_path(self, file_path: str) -> bool:
        """Exporta el contenido HTML de la pestaña Desarrollo a un archivo PDF.

        Args:
            file_path: Ruta completa del archivo de destino (debe terminar en .pdf).

        Returns:
            True si la exportación fue exitosa, False en caso contrario
            (ruta vacía o excepción al escribir el fichero).
        """
        if not file_path:
            return False
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            self.steps_text.print_(printer)
            return True
        except Exception as exc:
            self.status_bar.showMessage(f"✖ No se pudo guardar el PDF: {exc}")
            return False

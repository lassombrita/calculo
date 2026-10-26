"""Módulo de ventana principal de la interfaz gráfica de IntegralLab.

Responsabilidad:
Orquestar la interfaz gráfica educativa conectando la entrada matemática del usuario
con el dominio de cálculo simbólico y sólidos de revolución (integrallab.core)
y los lienzos de visualización 2D y 3D (integrallab.viz).
Esta capa no importa SymPy directamente; toda la lógica matemática pasa por el dominio.

Modelo de concurrencia:
- Todo cálculo pasa por ``integrallab.core.pipeline.run_calculation`` (una sola ruta; antes
  había una copia síncrona para los tests y otra en el worker).
- Cada cálculo es un "trabajo" con un identificador creciente. Los resultados de trabajos
  cancelados o reemplazados se descartan, así que nunca se mezclan en pantalla.
- El trabajo corre en un proceso aparte (``ui/calc_backend.py``): SymPy no compite por el GIL
  con la interfaz y cancelar es inmediato. Si no se puede crear el proceso, se usa un hilo
  *daemon*. Los resultados llegan por señales Qt; la malla 3D antes que el volumen simbólico.
- ``_synchronous = True`` ejecuta el mismo trabajo en el hilo principal (pruebas).
"""

from __future__ import annotations

import html
import logging
import math
import threading
from dataclasses import dataclass, field, replace
from typing import Any

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QSlider,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
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
from integrallab.core.parser import (
    ExpressionParseError,
    ParsedExpression,
    is_points_input,
    parse_math_expression,
    parse_numeric_or_symbolic,
    parse_points,
)
from integrallab.core.pipeline import (
    CalculationCancelled,
    CalculationOutput,
    CalculationRequest,
    run_calculation,
)
from integrallab.core.sampling import robust_y_window, sample_expression
from integrallab.core.solids import (
    AxisOrientation,
    _evaluate_bounds,
    generate_representative_slice,
    generate_riemann_mesh,
    generate_solid_mesh,
    MethodRecommendation,
    Region2D,
    RevolutionAxis,
    SolidMesh3D,
    SolidMethod,
    VolumeResult,
    can_invert_for_method,
    inversion_is_cheap,
    is_method_compatible,
)
from integrallab.ui.calc_backend import ProcessCalculationBackend
from integrallab.ui.theme import Palette, build_palette, build_stylesheet
from integrallab.ui.widgets.aurora import AuroraBackground
from integrallab.ui.widgets.glass import GlassCard
from integrallab.ui.widgets.visual_input import (
    FIELD_LABELS,
    FIELD_NAMES,
    VisualMathEditor,
    visual_input_support,
)
from integrallab.viz.canvas import PlotCanvas
from integrallab.viz.canvas3d import PlotCanvas3D
from integrallab.viz.threejs_wrapper import ThreeJSViewer, WEBENGINE_AVAILABLE  # noqa: F401
from integrallab.viz.report_assets import (
    FormulaSpec,
    final_formula,
    render_formula,
    setup_formula,
    step_formula,
    volume_formula,
)
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

__all__ = ["MainWindow", "CalculationWorker", "CalculationOutput"]

logger = logging.getLogger(__name__)

# Rango de visualización 2D por defecto
_DEFAULT_X_MIN: float = -10.0
_DEFAULT_X_MAX: float = 10.0
_DEFAULT_POINTS: int = 400

_PLOT_BUTTON_TEXT = "⚙  Generar Gráficas y Sólido"
_BUSY_BUTTON_TEXT = "⏳ Calculando…  (Esc cancela)"
_VISUAL_OFF_TEXT = "√x  Editor visual"
_VISUAL_ON_TEXT = "⌨  Volver a texto"
_VISUAL_SETTING = "input/visual_editor"


def _fmt(value: float, digits: int = 4) -> str:
    """Número legible: fijo en rangos normales, científico si es enorme o diminuto.

    Con ``:.4f`` un volumen de 1,1e87 se imprimía con 88 cifras y 3,3e-37 salía «0.0000».
    """
    if value == 0 or 1e-3 <= abs(value) < 1e7:
        return f"{value:.{digits}f}"
    return f"{value:.{digits}e}"


def _esc(value: object) -> str:
    """Escapa texto dinámico antes de incrustarlo en HTML (QTextEdit.setHtml)."""
    return html.escape(str(value)).replace("\n", "<br>")


class _CalculationSignals(QObject):
    """Señales de los trabajos de cálculo. Viven en el hilo principal (conexión en cola)."""

    mesh_ready = Signal(int, object)   # (id del trabajo, SolidMesh3D)
    assets_ready = Signal(int, object)  # (id del trabajo, {FormulaSpec: html}) fórmulas ya renderizadas
    finished = Signal(int, object)     # (id del trabajo, CalculationOutput)
    failed = Signal(int, str)          # (id del trabajo, mensaje)


class CalculationWorker:
    """Ejecuta ``run_calculation`` fuera del hilo de la interfaz.

    Usa un hilo *daemon* de Python en lugar de un ``QThread`` hijo de la ventana: cerrar la
    ventana con un ``QThread`` aún en marcha abortaba el proceso («QThread: Destroyed while
    thread is still running»), y un cálculo de SymPy no se puede interrumpir a mitad. El hilo
    daemon no impide salir. La cancelación es cooperativa (se consulta entre pasos) y, además,
    la ventana descarta cualquier resultado de un trabajo que ya no es el actual.
    """

    def __init__(self, job_id: int, request: CalculationRequest, signals: _CalculationSignals) -> None:
        self.job_id = job_id
        self._request = request
        self._signals = signals
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self.run, name=f"integrallab-calculo-{self.job_id}", daemon=True
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def isRunning(self) -> bool:  # noqa: N802 - mismo nombre que QThread por compatibilidad
        return self._thread is not None and self._thread.is_alive()

    def run(self) -> None:
        try:
            output = run_calculation(
                self._request, on_mesh=self._emit_mesh, is_cancelled=self._cancel.is_set
            )
        except CalculationCancelled:
            return
        except Exception as exc:  # noqa: BLE001 - se informa a la interfaz, no se silencia
            logger.exception("Fallo inesperado en el cálculo %s", self.job_id)
            self._emit(self._signals.failed, str(exc) or exc.__class__.__name__)
            return
        if not self._cancel.is_set():
            self._emit(self._signals.finished, output)

    def _emit_mesh(self, mesh: SolidMesh3D) -> None:
        if not self._cancel.is_set():
            self._emit(self._signals.mesh_ready, mesh)

    def _emit(self, signal: Any, payload: object) -> None:
        try:
            signal.emit(self.job_id, payload)
        except RuntimeError:
            pass  # la ventana ya se destruyó: no hay a quién avisar


@dataclass
class _JobContext:
    """Datos de la petición en curso que se necesitan al pintar sus resultados."""

    job_id: int
    key: tuple
    a_text: str
    b_text: str
    a_val: float
    b_val: float
    parsed_f: ParsedExpression
    parsed_g: ParsedExpression | None
    axis: RevolutionAxis
    chosen_method: SolidMethod | None
    is_interpolated: bool
    interp_method_name: str
    show_dialogs: bool
    worker: CalculationWorker | None = None
    in_process: bool = False
    mesh_shown: bool = False
    request: CalculationRequest | None = None
    numeric_only: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


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
        # Estado de los trabajos de cálculo. Antes ``self._worker`` nunca se inicializaba: el
        # primer clic real (con límites) lanzaba AttributeError y el sólido no se calculaba.
        self._signals = _CalculationSignals(self)
        self._signals.mesh_ready.connect(self._on_job_mesh)
        self._signals.assets_ready.connect(self._on_job_assets)
        self._signals.finished.connect(self._on_job_finished)
        self._signals.failed.connect(self._on_job_failed)
        self._job_seq = 0
        self._job: _JobContext | None = None
        self._worker: CalculationWorker | None = None
        # True ejecuta el trabajo en el hilo principal (pruebas). Ya NO depende de
        # QT_QPA_PLATFORM ni de _show_dialogs: antes cambiar el método en el combo forzaba
        # el cálculo síncrono y congelaba la ventana varios segundos.
        self._synchronous = False
        self._backend: ProcessCalculationBackend | None = None
        self._backend_failed_at: float | None = None
        self._current_region: Region2D | None = None
        self._current_axis: RevolutionAxis | None = None
        self._revolution_timer: QTimer = QTimer(self)
        self._revolution_timer.setInterval(25)
        self._revolution_timer.timeout.connect(self._on_revolution_timer_tick)
        self._symbolic_timer = QTimer(self)
        self._symbolic_timer.setSingleShot(True)
        self._symbolic_timer.setInterval(8000)
        self._symbolic_timer.timeout.connect(self._on_symbolic_timeout)
        # Cuando False, _show_parse_error no abre diálogo modal (vital para tests headless)
        self._show_dialogs: bool = True
        self._invert_cache: dict[tuple, bool] = {}
        self._prerendered: dict[FormulaSpec, str] = {}
        # Editor visual de fórmulas (se crea al activarlo por primera vez) y preferencia guardada.
        self._visual_editor: VisualMathEditor | None = None
        self._syncing_visual = False
        self._settings = QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, "IntegralLab", "IntegralLab"
        )
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
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        # Grupo 1: Región y Funciones
        region_group = QGroupBox("1. Definición de la Región 2D")
        region_layout = QVBoxLayout(region_group)
        region_layout.setSpacing(6)
        self._region_layout = region_layout

        # Alternar entre escribir en texto y el editor visual (fracciones, raíces y potencias
        # dibujadas, como en GeoGebra o en una calculadora con «Natural Display»).
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addStretch(1)
        self.visual_input_button = QPushButton(_VISUAL_OFF_TEXT)
        self.visual_input_button.setObjectName("ModeToggle")
        self.visual_input_button.setCheckable(True)
        self.visual_input_button.setCursor(Qt.CursorShape.PointingHandCursor)
        visual_ok, visual_reason = visual_input_support()
        if visual_ok:
            self.visual_input_button.setToolTip(
                "Escribe las fórmulas como en GeoGebra o en una calculadora: la fracción dibuja su "
                "raya, la raíz su signo y la potencia su exponente. Vuelve a pulsar para escribir en texto."
            )
        else:
            self.visual_input_button.setEnabled(False)
            self.visual_input_button.setToolTip(f"Editor visual no disponible: {visual_reason}")
        self.visual_input_button.toggled.connect(self._on_visual_input_toggled)
        mode_row.addWidget(self.visual_input_button)
        region_layout.addLayout(mode_row)

        # Casillas de texto (modo clásico). En modo visual se ocultan, pero siguen siendo el
        # modelo: el editor visual escribe en ellas el texto ya traducido.
        self._text_inputs = QWidget()
        text_inputs_layout = QVBoxLayout(self._text_inputs)
        text_inputs_layout.setContentsMargins(0, 0, 0, 0)
        text_inputs_layout.setSpacing(6)

        # Función f(x)
        f_row = QHBoxLayout()
        f_label = QLabel("f(x) =")
        f_label.setFixedWidth(45)
        f_row.addWidget(f_label)
        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText("ej. sin(x), x**2, sqrt(x)...")
        self.expression_input.returnPressed.connect(self._on_plot_clicked)
        f_row.addWidget(self.expression_input)
        text_inputs_layout.addLayout(f_row)

        # Segunda función g(x) (opcional)
        g_row = QHBoxLayout()
        g_label = QLabel("g(x) =")
        g_label.setFixedWidth(45)
        g_row.addWidget(g_label)
        self.g_expression_input = QLineEdit()
        self.g_expression_input.setPlaceholderText("Opcional: segunda curva, ej. x**2")
        self.g_expression_input.returnPressed.connect(self._on_plot_clicked)
        g_row.addWidget(self.g_expression_input)
        text_inputs_layout.addLayout(g_row)

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
        text_inputs_layout.addLayout(limits_row)
        region_layout.addWidget(self._text_inputs)

        # Lo que se escriba (o se rellene solo, como los límites de una interpolación) llega al
        # editor visual si está activo.
        # (Método enlazado, no lambda: una lambda que captura ``self`` crea un ciclo de
        # referencias que se libera al cerrar Python, después de QApplication, y lo aborta.)
        for name in FIELD_NAMES:
            self._line_edit_for(name).textChanged.connect(self._on_line_edit_text_changed)

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
        self.plot_button = QPushButton(_PLOT_BUTTON_TEXT)
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
        # Panel desplazable: con el editor visual activo (o en pantallas de 768 px) el contenido
        # no cabe entero y, sin desplazamiento, Qt comprimía las casillas por debajo de su mínimo.
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidget(sidebar_widget)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setFixedWidth(360)
        self.sidebar_scroll.viewport().setAutoFillBackground(False)
        sidebar_card_layout.addWidget(self.sidebar_scroll)
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

        # Controles de vista que faltaban: no había forma de detener el giro ni de
        # recuperar el encuadre tras hacer zoom o paneo.
        self.auto_rotate_check = QCheckBox("Auto-rotación", parent=engine_bar)
        self.auto_rotate_check.setChecked(True)
        self.auto_rotate_check.setToolTip("Gira el sólido automáticamente al generarlo.")
        self.auto_rotate_check.toggled.connect(self._on_auto_rotate_toggled)
        engine_layout.addWidget(self.auto_rotate_check)
        self.fit_view_button = QPushButton("⟲ Reencuadrar", parent=engine_bar)
        self.fit_view_button.setToolTip("Vuelve a centrar la cámara en el sólido (también: doble clic en el visor WebGL).")
        self.fit_view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fit_view_button.clicked.connect(self._on_fit_view_clicked)
        engine_layout.addWidget(self.fit_view_button)

        # Stack de visores
        self.solid_stack = QStackedWidget(parent=solid_widget)

        # Página 0: ThreeJSViewer (WebGL)
        self.threejs_viewer = ThreeJSViewer(parent=self.solid_stack)
        self.threejs_viewer.backend_status_changed.connect(self._on_webgl_status)
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
        solid_layout.addWidget(self.solid_stack, stretch=1)
        solid_layout.addWidget(self._build_3d_interactive_controls(solid_widget))

        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
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

        # Estado inicial del selector de método según el eje por defecto.
        self._update_method_availability()

        # Arranca el proceso de cálculo en segundo plano para que el primer cálculo no espere
        # la importación de SymPy (no se arranca en modo síncrono / pruebas).
        QTimer.singleShot(600, self._prewarm_backend)

        # Se recuerda el modo de escritura elegido la última vez.
        if visual_ok and self._settings.value(_VISUAL_SETTING, False, type=bool):
            self.visual_input_button.setChecked(True)


    # ── Editor visual de fórmulas ──────────────────────────────────────────

    def _line_edit_for(self, box: str) -> QLineEdit:
        """Casilla de texto que hace de modelo para ``box`` (f, g, a o b)."""
        return {
            "f": self.expression_input,
            "g": self.g_expression_input,
            "a": self.limit_a_input,
            "b": self.limit_b_input,
        }[box]

    def _visual_input_active(self) -> bool:
        return self._visual_editor is not None and self.visual_input_button.isChecked()

    def _ensure_visual_editor(self) -> VisualMathEditor | None:
        """Crea el editor la primera vez (QtWebEngine tarda en arrancar: no se paga al abrir)."""
        if self._visual_editor is None:
            try:
                editor = VisualMathEditor(self._text_inputs.parentWidget())
            except Exception as exc:  # noqa: BLE001 - p. ej. QtWebEngine sin OpenGL
                logger.exception("No se pudo crear el editor visual")
                self._disable_visual_input(str(exc))
                return None
            editor.textChanged.connect(self._on_visual_text_changed)
            editor.submitted.connect(self._on_plot_clicked)
            editor.loadFailed.connect(self._disable_visual_input)
            editor.hide()
            self._region_layout.addWidget(editor)
            self._visual_editor = editor
        return self._visual_editor

    def _on_visual_input_toggled(self, checked: bool) -> None:
        """Cambia entre las casillas de texto y el editor visual, conservando lo escrito."""
        if checked:
            editor = self._ensure_visual_editor()
            if editor is None:
                return
            for box in FIELD_NAMES:
                editor.set_text(box, self._line_edit_for(box).text())
            self._text_inputs.hide()
            editor.show()
            editor.focus_field("f")
            self.visual_input_button.setText(_VISUAL_ON_TEXT)
            self.status_bar.showMessage(
                "Editor visual: usa los botones, o escribe / para fracciones, ^ para potencias y "
                "sqrt para raíces. Enter calcula."
            )
        else:
            if self._visual_editor is not None:
                self._visual_editor.hide()
            self._text_inputs.show()
            self.visual_input_button.setText(_VISUAL_OFF_TEXT)
        self._settings.setValue(_VISUAL_SETTING, checked)

    def _disable_visual_input(self, reason: str) -> None:
        """El editor no pudo cargarse: se vuelve al texto y se explica por qué."""
        self.visual_input_button.setChecked(False)
        self.visual_input_button.setEnabled(False)
        self.visual_input_button.setToolTip(f"Editor visual no disponible: {reason}")
        self._settings.setValue(_VISUAL_SETTING, False)
        self.status_bar.showMessage(f"ℹ Editor visual no disponible: {reason}", 10000)

    def _on_visual_text_changed(self, box: str, text: str) -> None:
        """El editor tradujo una casilla: se copia a su QLineEdit (sin eco hacia el editor)."""
        self._syncing_visual = True
        try:
            self._line_edit_for(box).setText(text)
        finally:
            self._syncing_visual = False

    def _on_line_edit_text_changed(self, text: str) -> None:
        """Un cambio hecho por código (p. ej. límites de una interpolación) llega al editor."""
        if self._syncing_visual or not self._visual_input_active():
            return
        box = next((name for name in FIELD_NAMES if self._line_edit_for(name) is self.sender()), None)
        if box is not None:
            assert self._visual_editor is not None
            self._visual_editor.set_text(box, text)

    # ── Manejo de controles ────────────────────────────────────────────────

    def _on_axis_combo_changed(self, index: int) -> None:
        """Habilita la entrada numérica del eje y los métodos aplicables a ese eje."""
        is_custom = index in (2, 3)
        self.axis_value_input.setEnabled(is_custom)
        if not is_custom:
            self.axis_value_input.setText("0")
        self._update_method_availability()

    def _can_invert_cached(self, region: Region2D, probe: RevolutionAxis, method: SolidMethod) -> bool:
        """``can_invert_for_method`` memorizado: invierte con SymPy en el hilo de la interfaz.

        Cada cambio de eje repetía la inversión (50–220 ms por cambio en las pruebas); con la
        caché solo se paga la primera vez para cada región.
        """
        key = (str(region.f_expr), str(region.g_expr), str(region.a), str(region.b),
               probe.orientation.value, method.value)
        if key not in self._invert_cache:
            if len(self._invert_cache) > 256:
                self._invert_cache.clear()
            if not inversion_is_cheap(region):
                # SymPy.solve en el hilo de Qt costaba hasta 1,2 s por cambio de eje; si no es un
                # polinomio de grado bajo se habilita el método y el trabajo informa si no se puede.
                self._invert_cache[key] = True
            else:
                self._invert_cache[key] = can_invert_for_method(region, probe, method)
        return self._invert_cache[key]

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
        if f_text and lim_a and lim_b and not is_points_input(f_text):
            probe_region = Region2D(
                f_expr=f_text,
                g_expr=self.g_expression_input.text().strip() or None,
                a=lim_a,
                b=lim_b,
                variable="x",
            )

        for combo_index, method in self._METHOD_BY_INDEX.items():
            item = model.item(combo_index)  # type: ignore[attr-defined]
            direct = is_method_compatible(method, probe)
            invertible = False
            if not direct and probe_region is not None:
                try:
                    invertible = self._can_invert_cached(probe_region, probe, method)
                except Exception:  # noqa: BLE001 - región incompleta mientras se escribe
                    invertible = False

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
        """Recalcula si f(x) y ambos límites están completos; sin diálogos modales.

        El recálculo es asíncrono como cualquier otro (antes, al desactivar los diálogos
        se activaba sin querer la rama síncrona y la ventana se congelaba).
        """
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

    def _on_engine_changed(self, index: int) -> None:
        """Cambia de visor 3D. El lienzo que queda oculto deja de dibujar y de animarse."""
        self.solid_stack.setCurrentIndex(index)

    def _on_webgl_status(self, ok: bool, reason: str) -> None:
        """Si WebGL no está disponible, cambia a Matplotlib en lugar de dejar la vista vacía."""
        item = self.engine_combo.model().item(0)  # type: ignore[attr-defined]
        if ok:
            item.setEnabled(True)
            item.setToolTip("")
            return
        item.setEnabled(False)
        item.setToolTip(f"WebGL no disponible en este equipo: {reason}")
        if self.engine_combo.currentIndex() == 0:
            self.engine_combo.setCurrentIndex(1)
        self.status_bar.showMessage(
            "ℹ WebGL no está disponible en este equipo; se usa el motor Matplotlib.", 10000
        )

    def _on_auto_rotate_toggled(self, enabled: bool) -> None:
        self.threejs_viewer.set_auto_rotate(enabled)
        self.canvas3d.set_auto_rotate(enabled)

    def _on_fit_view_clicked(self) -> None:
        self.threejs_viewer.fit_camera()
        self.canvas3d.reset_view()

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

    def _plot_window(self) -> tuple[float, float]:
        """Rango x de la gráfica 2D: [-10, 10] o, con límites válidos, [a, b] con margen."""
        a = self._parse_limit_to_float(self.limit_a_input.text().strip()) if self.limit_a_input.text().strip() else None
        b = self._parse_limit_to_float(self.limit_b_input.text().strip()) if self.limit_b_input.text().strip() else None
        if a is None or b is None or not (math.isfinite(a) and math.isfinite(b)) or a >= b:
            return _DEFAULT_X_MIN, _DEFAULT_X_MAX
        span = b - a
        lo, hi = a - 0.5 * span, b + 0.5 * span
        if lo > _DEFAULT_X_MIN and hi < _DEFAULT_X_MAX and span > 0.5:
            return _DEFAULT_X_MIN, _DEFAULT_X_MAX  # la región ya se ve bien en la vista estándar
        return lo, hi

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

    # ── Estado de la interfaz ──────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        """Estado visual del botón principal mientras hay un trabajo en curso."""
        self.plot_button.setEnabled(not busy)
        self.plot_button.setText(_BUSY_BUTTON_TEXT if busy else _PLOT_BUTTON_TEXT)

    def _clear_3d(self) -> None:
        self.canvas3d.clear_canvas()
        self.threejs_viewer.clear_canvas()
        self._current_region = None
        self._current_axis = None
        if hasattr(self, "_revolution_timer") and self._revolution_timer.isActive():
            self._revolution_timer.stop()
        self._enable_3d_interactive_controls(False)

    def _reset_outputs(self, message: str, label: str | None = None) -> None:
        """Deja la interfaz coherente tras un error o una cancelación.

        Antes, si un cálculo fallaba después de otro exitoso, quedaban a la vista el sólido,
        el desarrollo y el botón «Exportar a PDF» del caso anterior.
        """
        self._clear_3d()
        if label is not None:
            self.result_label.setText(label)
        self.results_text.setPlainText(message)
        self.steps_text.setPlainText(message)
        self.export_pdf_button.setEnabled(False)

    def _prewarm_backend(self) -> None:
        if not self._synchronous:
            self._get_backend()

    @property
    def _backend_failed(self) -> bool:
        return self._backend_failed_at is not None

    @_backend_failed.setter
    def _backend_failed(self, value: bool) -> None:
        import time
        self._backend_failed_at = time.time() if value else None

    def _get_backend(self) -> ProcessCalculationBackend | None:
        """Proceso de calculo (creado una vez). None en modo sincrono o si no se pudo crear."""
        if self._synchronous:
            return None
        if self._backend_failed_at is not None:
            import time
            if time.time() - self._backend_failed_at < 30.0:
                return None
            self._backend_failed_at = None
        if self._backend is None:
            try:
                self._backend = ProcessCalculationBackend(self._signals)
            except Exception:  # noqa: BLE001 - p. ej. entorno sin multiprocessing
                import time
                logger.exception("No se pudo crear el proceso de calculo; se usara un hilo")
                self._backend_failed_at = time.time()
                return None
        return self._backend

    def _on_symbolic_timeout(self) -> None:
        """Vence el tiempo limite simbolico (8s): conmuta a calculo numerico con mpmath."""
        if self._job is None or self._job.numeric_only or self._job.request is None:
            return
        self._job.numeric_only = True
        num_req = replace(self._job.request, numeric_only=True)
        self._job.request = num_req
        if self._job.in_process and self._backend is not None:
            self._backend.submit(self._job.job_id, num_req)
        elif self._worker is not None:
            self._worker.cancel()
            worker = CalculationWorker(self._job.job_id, num_req, self._signals)
            self._job.worker = worker
            self._worker = worker
            worker.start()
        self.status_bar.showMessage("SymPy no termino en 8 s: mostrando el valor numerico...")


    def _job_running(self) -> bool:
        if self._job is None:
            return False
        if self._job.in_process:
            return self._backend is not None and self._backend.is_busy
        return self._worker is not None and self._worker.isRunning()

    def _cancel_active_job(self) -> bool:
        """Cancela y descarta el trabajo en curso. Devuelve True si había uno."""
        self._symbolic_timer.stop()
        job, self._job = self._job, None
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.cancel()
        if job is not None and job.in_process and self._backend is not None:
            self._backend.cancel()  # termina el proceso: la cancelación es real
        self._set_busy(False)
        return job is not None

    def _input_error(self, message: str) -> None:
        """Error de entrada: se abandona cualquier cálculo anterior (sus resultados ya no aplican)."""
        if self._cancel_active_job():
            self._reset_outputs("Cálculo anterior descartado: corrija la entrada y vuelva a generar.")
        self._show_parse_error(message)

    def _region_error(self, message: str, label: str) -> None:
        """Error en límites o eje: la gráfica 2D ya muestra la nueva f(x), así que el sólido,
        los reportes y la exportación del caso anterior se retiran para no mezclar casos."""
        self._cancel_active_job()
        self._reset_outputs(message, label=label)
        self._show_parse_error(message)

    # ── Orquestador principal ──────────────────────────────────────────────

    def _on_plot_clicked(self) -> None:
        """Slot principal que reacciona a 'Generar Gráficas y Sólido'.

        Flujo:
        1. Leer y validar f(x) (o puntos discretos → interpolación) y opcionalmente g(x).
        2. Graficar en 2D en el rango [-10, 10].
        3. Si hay límites a y b: validar límites y eje, y lanzar el trabajo de cálculo
           (área, malla 3D, recomendación y volumen) fuera del hilo de la interfaz.
        """
        if self._visual_input_active() and (problem := self._visual_editor.first_error()) is not None:
            box, message = problem
            self._visual_editor.show_errors()
            self._input_error(f"{FIELD_LABELS[box]}: {message}")
            return

        raw_f = self.expression_input.text().strip()
        raw_g = self.g_expression_input.text().strip()

        if not raw_f:
            self.status_bar.showMessage("⚠ El campo de función f(x) está vacío.")
            return

        # 0. Puntos discretos → interpolación numérica
        is_interpolated = False
        interp_method_name = ""
        try:
            if is_points_input(raw_f):
                pts = parse_points(raw_f)
                interp_res = interpolate_lagrange(pts) if len(pts) <= 4 else interpolate_cubic_spline(pts)
                if not interp_res.is_success:
                    self._input_error(interp_res.error_message or "Error en interpolación numérica.")
                    return
                # Se usa la expresión simbólica directamente: un spline (Piecewise) no se puede
                # volver a parsear desde texto, así que con 5 o más puntos el flujo fallaba siempre.
                parsed_f = interp_res.to_parsed_expression(raw_f)
                is_interpolated = True
                interp_method_name = interp_res.method.value.capitalize()
                f_label = (
                    f"f(x) = spline cúbico natural ({len(pts)} puntos)"
                    if len(pts) > 4 else f"f(x) = {parsed_f.plain_text}"
                )
                if not self.limit_a_input.text().strip():
                    self.limit_a_input.setText(str(pts[0][0]))
                if not self.limit_b_input.text().strip():
                    self.limit_b_input.setText(str(pts[-1][0]))
            else:
                parsed_f = parse_math_expression(raw_f)
                f_label = f"f(x) = {parsed_f.plain_text}"
            parsed_g = parse_math_expression(raw_g) if raw_g else None
        except ExpressionParseError as exc:
            self._input_error(str(exc))
            return

        extra = sorted({*parsed_f.variables, *(parsed_g.variables if parsed_g else [])} - {"x"})
        if extra:
            self._input_error(
                f"La expresión usa símbolos sin valor: {', '.join(extra)}. Solo se admite la "
                "variable x (sustituya las constantes por números)."
            )
            return

        # 2. Muestreo 2D: centrado en [a, b] si hay límites (antes siempre [-10, 10], así que la
        # región sombreada en [20, 30] quedaba sin curva y en [-0,001; 0,001] era invisible).
        x_min, x_max = self._plot_window()
        curve_f = sample_expression(
            parsed_f,
            x_min=x_min,
            x_max=x_max,
            num_points=_DEFAULT_POINTS,
            label=f_label,
            adaptive=True,
        )
        if not curve_f.is_valid:
            self._input_error(curve_f.error_message or "Error al evaluar f(x).")
            return

        if parsed_g is not None:
            curve_g = sample_expression(
                parsed_g,
                x_min=x_min,
                x_max=x_max,
                num_points=_DEFAULT_POINTS,
                label=f"g(x) = {parsed_g.plain_text}",
                adaptive=True,
            )
            if not curve_g.is_valid:
                self._input_error(curve_g.error_message or "Error al evaluar g(x).")
                return
            self.canvas.plot_curves([curve_f, curve_g], clear=True)
            self.canvas.set_y_window(robust_y_window([curve_f, curve_g]))
        else:
            self.canvas.plot_curve(curve_f, clear=True)
            self.canvas.set_y_window(robust_y_window([curve_f]))
        self.nav_toolbar_2d.update()  # «Inicio» vuelve a la vista de ESTA función, no de la anterior

        # 3. Procesar límites de integración y sólido 3D
        a_text = self.limit_a_input.text().strip()
        b_text = self.limit_b_input.text().strip()

        if not (a_text and b_text):
            self._cancel_active_job()
            self._clear_3d()
            self.export_pdf_button.setEnabled(False)
            self.result_label.setText("Área / Integral: —")
            self.results_text.setPlainText(
                "Gráfica 2D trazada con éxito.\n"
                "Para calcular la integral y generar el sólido 3D, ingresa los límites 'a' y 'b'."
            )
            self.steps_text.setPlainText(
                "Gráfica 2D trazada con éxito.\n"
                "Para calcular la integral y ver el desarrollo analítico paso a paso, ingresa los límites 'a' y 'b'."
            )
            self.status_bar.showMessage(f"✔ Graficada: {f_label}")
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
        parsed_f: ParsedExpression,
        parsed_g: ParsedExpression | None,
        a_text: str,
        b_text: str,
        is_interpolated: bool = False,
        interp_method_name: str = "",
    ) -> None:
        """Valida límites y eje y lanza el trabajo de cálculo (área, malla y volumen)."""
        a_val = self._parse_limit_to_float(a_text)
        b_val = self._parse_limit_to_float(b_text)

        if a_val is None or b_val is None:
            self._region_error(
                "Los límites de integración deben ser números o constantes válidas (ej. 0, 3, pi).",
                "Área / Integral: Error en límites",
            )
            return

        if a_val >= b_val:
            self._region_error(
                f"El límite inferior 'a' ({a_val}) debe ser menor que el límite superior 'b' ({b_val}).",
                "Área / Integral: Error en límites (a >= b)",
            )
            return

        try:
            axis = self._get_selected_axis()
            chosen_method = self._get_selected_method()
        except Exception as exc:  # noqa: BLE001
            self._region_error(f"Error en configuración de sólido: {exc}", "Área / Integral: —")
            return

        key = (
            parsed_f.plain_text, parsed_g.plain_text if parsed_g is not None else "",
            a_text, b_text, axis.orientation.value, float(axis.position),
            chosen_method.value if chosen_method else None,
        )
        if self._job is not None and self._job.key == key and self._job_running():
            # Enter repetido o doble clic: no se lanza otro hilo para la misma región.
            self.status_bar.showMessage("⏳ Ya se está calculando esta región… (Esc cancela)")
            return

        ctx = _JobContext(
            job_id=0, key=key, a_text=a_text, b_text=b_text, a_val=a_val, b_val=b_val,
            parsed_f=parsed_f, parsed_g=parsed_g, axis=axis, chosen_method=chosen_method,
            is_interpolated=is_interpolated, interp_method_name=interp_method_name,
            show_dialogs=self._show_dialogs,
        )
        request = CalculationRequest(
            f=parsed_f, g=parsed_g, a_text=a_text, b_text=b_text, axis=axis, method=chosen_method,
        )
        self._start_job(ctx, request)

    def _start_job(self, ctx: _JobContext, request: CalculationRequest) -> None:
        """Lanza (o ejecuta en línea en modo síncrono) un trabajo, reemplazando al anterior."""
        self._cancel_active_job()
        self._job_seq += 1
        ctx.job_id = self._job_seq
        self._job = ctx
        self._set_busy(True)
        self.status_bar.showMessage("⏳ Calculando integral y generando sólido 3D…  (Esc cancela)")
        ctx.request = request
        if not self._synchronous:
            self._symbolic_timer.start(8000)
        backend = self._get_backend()
        if backend is not None:
            try:
                ctx.in_process = True
                backend.submit(ctx.job_id, request)
                return
            except Exception:  # noqa: BLE001 - proceso caído: seguir con un hilo
                logger.exception("El proceso de cálculo no aceptó el trabajo; se usará un hilo")
                ctx.in_process = False
                import time; self._backend_failed_at = time.time()
                backend.shutdown()
                self._backend = None
        worker = CalculationWorker(ctx.job_id, request, self._signals)
        ctx.worker = worker
        self._worker = worker
        if self._synchronous:
            worker.run()
        else:
            worker.start()

    def _is_current(self, job_id: int) -> bool:
        return self._job is not None and self._job.job_id == job_id

    def _on_job_mesh(self, job_id: int, mesh: object) -> None:
        """La malla llega antes que el volumen simbólico: se muestra de inmediato."""
        if not self._is_current(job_id) or not isinstance(mesh, SolidMesh3D):
            return
        assert self._job is not None
        self._job.mesh_shown = True
        # Si un motor no puede dibujar la malla, se limpia: antes conservaba el sólido anterior.
        if not self.canvas3d.plot_solid_mesh(mesh, show_axis=True):
            self.canvas3d.clear_canvas()
        if not self.threejs_viewer.plot_solid_mesh(mesh, show_axis=True):
            self.threejs_viewer.clear_canvas()
        self.status_bar.showMessage("⏳ Sólido 3D listo; calculando el volumen exacto…  (Esc cancela)")

    def _on_job_assets(self, job_id: int, assets: object) -> None:
        """Fórmulas LaTeX renderizadas en el proceso de cálculo (no en el hilo de Qt)."""
        if self._is_current(job_id) and isinstance(assets, dict):
            assert self._job is not None
            self._job.extra["formulas"] = assets

    def _formula_html(self, spec: FormulaSpec | None, fallback_html: str = "") -> str:
        if spec is None:
            return fallback_html
        cached = self._prerendered.get(spec)
        return cached if cached is not None else render_formula(spec)

    def _finish_job(self, job_id: int) -> _JobContext | None:
        if not self._is_current(job_id):
            return None  # resultado de un trabajo cancelado o reemplazado: se descarta
        self._symbolic_timer.stop()
        self._symbolic_timer.stop()
        ctx, self._job, self._worker = self._job, None, None
        self._set_busy(False)
        if self._backend is not None:
            self._backend.recycle_if_idle()
        return ctx

    def _on_job_finished(self, job_id: int, out: object) -> None:
        """Pinta los resultados del trabajo actual (o informa su error)."""
        ctx = self._finish_job(job_id)
        if ctx is None or not isinstance(out, CalculationOutput):
            return
        if not out.res_2d.is_success:
            self._reset_outputs(
                f"Error al integrar en 2D:\n{out.res_2d.error_message}",
                label="Área / Integral: Error en cálculo",
            )
            self._show_parse_error(f"Error al integrar en 2D: {out.res_2d.error_message}", ctx.show_dialogs)
            return

        if not out.vol_res.is_success:
            err_msg = out.vol_res.error_message or "Error al calcular el volumen del sólido."
            self._reset_outputs(
                f"Error al calcular el sólido de revolución:\n{err_msg}",
                label=f"∫ [{ctx.a_text}, {ctx.b_text}] = {out.res_2d.exact_plain_text} | Volumen 3D: no calculado",
            )
            self._show_parse_error(err_msg, ctx.show_dialogs)
            return

        self._render_and_display_results(out, ctx)

    def _on_job_failed(self, job_id: int, err_msg: str) -> None:
        """Excepción inesperada dentro del trabajo actual."""
        ctx = self._finish_job(job_id)
        if ctx is None:
            return
        self._reset_outputs(f"Error en configuración de sólido:\n{err_msg}", label="Área / Integral: Error en cálculo")
        self._show_parse_error(f"Error en configuración de sólido: {err_msg}", ctx.show_dialogs)

    def _render_and_display_results(self, out: CalculationOutput, ctx: _JobContext) -> None:
        """Sombrea la región, asegura el sólido en pantalla y publica los reportes."""
        res_2d = out.res_2d
        vol_res = out.vol_res
        axis = out.axis
        chosen_method = out.chosen_method

        # Muestreo fino para sombrear el área entre curvas en [a, b]
        shade_curve_f = sample_expression(ctx.parsed_f, x_min=ctx.a_val, x_max=ctx.b_val, num_points=120)
        if shade_curve_f.is_valid:
            if ctx.parsed_g is not None:
                shade_curve_g = sample_expression(ctx.parsed_g, x_min=ctx.a_val, x_max=ctx.b_val, num_points=120)
                y2_data = shade_curve_g.y_values if shade_curve_g.is_valid else 0.0
            else:
                y2_data = 0.0

            self.canvas.shade_region(
                shade_curve_f.x_values,
                shade_curve_f.y_values,
                y2_values=y2_data,
                color=Palette.VIOLET,
                alpha=0.30,
                label=f"Región [{ctx.a_text}, {ctx.b_text}]",
            )

        if not ctx.mesh_shown:
            if out.mesh is not None and out.mesh.is_valid:
                self.canvas3d.plot_solid_mesh(out.mesh, show_axis=True)
                self.threejs_viewer.plot_solid_mesh(out.mesh, show_axis=True)
            else:
                self._clear_3d()

        if out.mesh is not None and out.mesh.is_valid:
            self._current_region = out.region
            self._current_axis = out.axis
            self._enable_3d_interactive_controls(True)
        else:
            self._enable_3d_interactive_controls(False)

        area_str = f"∫ [{ctx.a_text}, {ctx.b_text}] = {res_2d.exact_plain_text}"
        approx_vol = (
            f" ≈ {_fmt(vol_res.numeric_value)}" if vol_res.numeric_value is not None else ""
        )
        self.result_label.setText(
            f"{area_str} | Volumen 3D: {vol_res.exact_plain_text}{approx_vol}"
        )

        self._prerendered = ctx.extra.get("formulas", {})
        try:
            self._display_pedagogical_report(res_2d, vol_res, out.rec, axis)
            self._display_steps_report(vol_res, out.rec, axis, ctx.a_text, ctx.b_text)
        finally:
            self._prerendered = {}
        self.export_pdf_button.setEnabled(True)

        method_note = ""
        if chosen_method is not None and vol_res.method != chosen_method:
            method_note = (
                f" ⚠ {chosen_method.value} no aplica aquí (hay hueco interior); "
                f"se usó {vol_res.method.value}."
            )
        prefix = f"✔ Interpolación ({ctx.interp_method_name}) | " if ctx.is_interpolated else "✔ "
        self.status_bar.showMessage(
            f"{prefix}Sólido generado: V = {vol_res.exact_plain_text}{approx_vol} "
            f"({vol_res.method.value}){method_note}"
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape cancela el cálculo en curso (sin errores si no hay ninguno)."""
        if event.key() == Qt.Key.Key_Escape and self._job is not None:
            self._cancel_active_job()
            self._reset_outputs("Cálculo cancelado por el usuario.", label="Área / Integral: —")
            self.status_bar.showMessage("⚠ Cálculo cancelado por el usuario.")
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Al cerrar, se cancela el trabajo; el hilo daemon no impide salir."""
        self._cancel_active_job()
        self._signals.blockSignals(True)
        if hasattr(self, "_revolution_timer"):
            self._revolution_timer.stop()
        if self._backend is not None:
            self._backend.shutdown()
        super().closeEvent(event)

    # ── Reportes (HTML compatible con QTextDocument) ───────────────────────
    #
    # QTextEdit solo entiende un subconjunto de HTML/CSS: ignora border-radius, box-shadow y el
    # padding/borde de los <div>, por eso las "tarjetas" del desarrollo se veían como texto
    # plano y el título quedaba como un subrayado azul. Aquí se usan tablas (que sí admiten
    # fondo, borde y relleno), con el mismo aspecto en pantalla y en el PDF exportado.
    # Todo texto dinámico pasa por html.escape.

    _METHOD_TITLES = {
        SolidMethod.DISKS: "Método de Discos",
        SolidMethod.WASHERS: "Método de Arandelas",
        SolidMethod.SHELLS: "Método de Casquillos Cilíndricos",
    }

    @staticmethod
    def _axis_description(axis: RevolutionAxis) -> str:
        kind = "Horizontal" if axis.orientation == AxisOrientation.HORIZONTAL else "Vertical"
        return f"{kind} ({axis.label})"

    def _display_pedagogical_report(
        self,
        res_2d: object,
        vol_res: VolumeResult,
        rec: MethodRecommendation | None,
        axis: RevolutionAxis,
    ) -> None:
        """Formatea e inserta el análisis analítico y pedagógico en results_text."""
        method_title = self._METHOD_TITLES.get(vol_res.method, vol_res.method.value.capitalize())
        numeric_str = (
            f"V ≈ {_fmt(vol_res.numeric_value, 5)} u³"
            if vol_res.numeric_value is not None
            else "No disponible"
        )

        vol_img = self._formula_html(volume_formula(vol_res))
        setup_img = self._formula_html(
            setup_formula(vol_res), f"<code>{_esc(vol_res.integrand_plain_text)}</code>"
        )

        justification = _esc(rec.justification) if rec is not None else ""
        html_parts = [f"""
        <div style="font-family: sans-serif;">
            <h3 style="color: #2980b9; margin-bottom: 4px;">{_esc(method_title)}</h3>
            <p><b>Eje de rotación:</b> {_esc(self._axis_description(axis))}</p>
            <p><b>Volumen exacto:</b><br>{vol_img}
               <span style="font-size: 11px; color: #7f8c8d;">({_esc(vol_res.exact_plain_text)})</span></p>
            <p><b>Volumen numérico:</b> <b>{_esc(numeric_str)}</b></p>
            <p><b>Planteamiento de la integral:</b><br>{setup_img}</p>
            <hr>
            <h4 style="color: #2c3e50; margin-bottom: 4px;">Justificación y Análisis Pedagógico:</h4>
            <p style="color: #34495e;">{justification}</p>
        """]

        all_warnings: list[str] = []
        if rec is not None and rec.limitations_or_warnings:
            all_warnings.extend(rec.limitations_or_warnings)
        if vol_res.warnings:
            all_warnings.extend(vol_res.warnings)

        if all_warnings:
            warning_text = "<br>".join(_esc(w) for w in all_warnings)
            html_parts.append(f"""
            <table width="100%" cellpadding="6" cellspacing="0" style="background-color: #fef5e7; margin-top: 6px;">
              <tr><td width="3" style="background-color: #e67e22;"></td>
                  <td style="color: #d35400;"><b>Nota:</b> {warning_text}</td></tr>
            </table>
            """)

        html_parts.append("""
        <p style="margin-top: 10px; font-size: 11px; color: #2980b9;">
            👉 <i>Consulta la pestaña <b>'Desarrollo'</b> para ver los pasos analíticos detallados (antiderivada, evaluación y simplificación).</i>
        </p>
        </div>
        """)
        self.results_text.setHtml("".join(html_parts))

    def _display_steps_report(
        self,
        vol_res: VolumeResult,
        rec: MethodRecommendation | None,
        axis: RevolutionAxis,
        a_text: str,
        b_text: str,
    ) -> None:
        """Formatea e inserta los pasos analíticos intermedios en la pestaña Desarrollo."""
        method_title = self._METHOD_TITLES.get(vol_res.method, vol_res.method.value.capitalize())
        axis_desc = self._axis_description(axis)

        parts = [f"""
        <table width="100%" cellpadding="14" cellspacing="0" style="background-color: #1e3a8a; margin-bottom: 12px;">
          <tr><td>
            <span style="font-size: 17px; font-weight: bold; color: #ffffff;">Desarrollo Analítico Paso a Paso</span><br>
            <span style="font-size: 12px; color: #dbeafe;"><b>{_esc(method_title)}</b> &nbsp;|&nbsp;
              <b>Eje de giro:</b> {_esc(axis_desc)} &nbsp;|&nbsp; <b>Límites:</b> [{_esc(a_text)}, {_esc(b_text)}]</span>
          </td></tr>
        </table>
        """]

        for step in vol_res.steps:
            expr_html = ""
            if step.expression_latex or step.expression_plain_text:
                content = self._formula_html(
                    step_formula(step), f"<code>{_esc(step.expression_plain_text)}</code>"
                )
                expr_html = f"""
                <table width="100%" cellpadding="8" cellspacing="0" style="background-color: #f8fafc; margin-top: 6px;">
                  <tr><td width="4" style="background-color: #2563eb;"></td><td>{content}</td></tr>
                </table>
                """

            parts.append(f"""
            <table width="100%" cellpadding="10" cellspacing="0" border="1"
                   style="border-color: #e2e8f0; border-style: solid; background-color: #ffffff; margin-bottom: 10px;">
              <tr><td>
                <span style="font-size: 13px; font-weight: bold; color: #1e40af;">{_esc(step.title)}</span><br>
                <span style="font-size: 12px; color: #475569;">{_esc(step.explanation)}</span>
                {expr_html}
              </td></tr>
            </table>
            """)

        final_img = self._formula_html(final_formula(vol_res))
        approx_str = f" ≈ {_fmt(vol_res.numeric_value, 5)} u³" if vol_res.numeric_value is not None else ""
        parts.append(f"""
            <table width="100%" cellpadding="10" cellspacing="0" style="background-color: #ecfdf5; margin-top: 12px;">
              <tr><td width="5" style="background-color: #10b981;"></td><td>
                <span style="font-size: 13px; font-weight: bold; color: #065f46;">Resultado Final del Volumen</span><br>
                {final_img}
                <span style="font-size: 13px; font-weight: bold; color: #047857;">{_esc(approx_str)}</span><br>
                <span style="font-size: 11px; color: #059669;">Valor exacto: <code>{_esc(vol_res.exact_plain_text)}</code></span>
              </td></tr>
            </table>
        """)
        self.steps_text.setHtml("".join(parts))

    def _show_parse_error(self, message: str, show_dialog: bool | None = None) -> None:
        """Muestra un error en la UI sin congelar la aplicación."""
        self.status_bar.showMessage(f"✖ Error: {message}")
        if not (self._show_dialogs if show_dialog is None else show_dialog):
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Atención en el cálculo")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("No se pudo completar la operación solicitada.")
        dialog.setInformativeText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()


    # ── Panel interactivo 3D (Deslizadores estilo GeoGebra) ───────────────────

    def _build_3d_interactive_controls(self, parent: QWidget) -> QWidget:
        """Crea el panel de controles interactivos 3D (deslizadores de ángulo, rebanada y Riemann)."""
        container = QWidget(parent=parent)
        container.setObjectName("Interactive3DPanel")
        container.setStyleSheet("""
            QWidget#Interactive3DPanel {
                background-color: rgba(15, 23, 42, 0.92);
                border-top: 1px solid rgba(255, 255, 255, 0.15);
                padding: 6px 12px;
            }
            QLabel {
                font-size: 11px;
                color: #e2e8f0;
            }
            QSlider::groove:horizontal {
                height: 5px;
                background: #334155;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #0284c7;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #f8fafc;
                border: 1px solid #0284c7;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #38bdf8;
                border: 1px solid #ffffff;
            }
            QCheckBox {
                font-size: 11px;
                font-weight: 600;
                color: #f1f5f9;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1px solid #64748b;
                background-color: #1e293b;
            }
            QCheckBox::indicator:hover {
                border-color: #38bdf8;
                background-color: #334155;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        # Fila 1: Rotación progresiva (estilo GeoGebra)
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_angle = QLabel("🔄 Rotación (θ):")
        lbl_angle.setFixedWidth(88)
        row1.addWidget(lbl_angle)

        self.revolution_slider = QSlider(Qt.Orientation.Horizontal)
        self.revolution_slider.setRange(5, 360)
        self.revolution_slider.setValue(360)
        self.revolution_slider.setEnabled(False)
        self.revolution_slider.setToolTip("Ajusta el ángulo de revolución para abrir el sólido o rotarlo poco a poco.")
        self.revolution_slider.valueChanged.connect(self._on_revolution_slider_changed)
        row1.addWidget(self.revolution_slider)

        self.revolution_angle_label = QLabel("360°")
        self.revolution_angle_label.setFixedWidth(40)
        self.revolution_angle_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row1.addWidget(self.revolution_angle_label)

        self.play_revolution_btn = QPushButton("▶ Girar poco a poco (GeoGebra)")
        self.play_revolution_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_revolution_btn.setEnabled(False)
        self.play_revolution_btn.setToolTip("Inicia la rotación continua de la curva para ver cómo barre el sólido paso a paso.")
        self.play_revolution_btn.clicked.connect(self._toggle_revolution_animation)
        row1.addWidget(self.play_revolution_btn)

        self.reset_revolution_btn = QPushButton("↺ 360°")
        self.reset_revolution_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_revolution_btn.setEnabled(False)
        self.reset_revolution_btn.setToolTip("Restaura el sólido completo a 360°.")
        self.reset_revolution_btn.clicked.connect(self._reset_revolution_to_full)
        row1.addWidget(self.reset_revolution_btn)

        layout.addLayout(row1)

        # Fila 2: Exploración didáctica (Rebanada representativa y Discos de Riemann)
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.slice_check = QCheckBox("Rebanada representativa (dx):")
        self.slice_check.setEnabled(False)
        self.slice_check.setToolTip("Muestra un disco/arandela individual en una posición específica del intervalo.")
        self.slice_check.toggled.connect(self._on_slice_check_toggled)
        row2.addWidget(self.slice_check)

        self.slice_slider = QSlider(Qt.Orientation.Horizontal)
        self.slice_slider.setRange(0, 1000)
        self.slice_slider.setValue(500)
        self.slice_slider.setEnabled(False)
        self.slice_slider.setToolTip("Mueve la rebanada representativa a lo largo del intervalo [a, b].")
        self.slice_slider.valueChanged.connect(self._on_slice_slider_changed)
        row2.addWidget(self.slice_slider)

        self.slice_pos_label = QLabel("x = —")
        self.slice_pos_label.setFixedWidth(70)
        row2.addWidget(self.slice_pos_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        row2.addWidget(sep)

        self.riemann_check = QCheckBox("Discos de Riemann:")
        self.riemann_check.setEnabled(False)
        self.riemann_check.setToolTip("Aproxima el sólido geométrico mediante cilindros discretos de Riemann.")
        self.riemann_check.toggled.connect(self._on_riemann_check_toggled)
        row2.addWidget(self.riemann_check)

        self.riemann_slider = QSlider(Qt.Orientation.Horizontal)
        self.riemann_slider.setRange(4, 40)
        self.riemann_slider.setValue(10)
        self.riemann_slider.setEnabled(False)
        self.riemann_slider.setToolTip("Ajusta la cantidad de discos de Riemann.")
        self.riemann_slider.valueChanged.connect(self._on_riemann_slider_changed)
        row2.addWidget(self.riemann_slider)

        self.riemann_count_label = QLabel("N = 10")
        self.riemann_count_label.setFixedWidth(45)
        row2.addWidget(self.riemann_count_label)

        layout.addLayout(row2)
        return container

    def _enable_3d_interactive_controls(self, enabled: bool) -> None:
        """Habilita o deshabilita los controles del panel interactivo según si hay un sólido activo."""
        if not hasattr(self, "revolution_slider"):
            return
        self.revolution_slider.setEnabled(enabled)
        self.play_revolution_btn.setEnabled(enabled)
        self.reset_revolution_btn.setEnabled(enabled)
        self.slice_check.setEnabled(enabled)
        self.slice_slider.setEnabled(enabled)
        self.riemann_check.setEnabled(enabled)
        self.riemann_slider.setEnabled(enabled)
        if enabled:
            self.revolution_slider.blockSignals(True)
            self.revolution_slider.setValue(360)
            self.revolution_angle_label.setText("360°")
            self.revolution_slider.blockSignals(False)
            self.play_revolution_btn.setText("▶ Girar poco a poco (GeoGebra)")
            if self._current_region is not None:
                num_a, num_b, _, _ = _evaluate_bounds(self._current_region.a, self._current_region.b)
                mid_x = 0.5 * (num_a + num_b)
                self.slice_pos_label.setText(f"{self._current_region.variable} = {mid_x:.2f}")
        else:
            if hasattr(self, "_revolution_timer") and self._revolution_timer.isActive():
                self._revolution_timer.stop()
            self.slice_check.blockSignals(True)
            self.slice_check.setChecked(False)
            self.slice_check.blockSignals(False)
            self.riemann_check.blockSignals(True)
            self.riemann_check.setChecked(False)
            self.riemann_check.blockSignals(False)

    def _on_revolution_slider_changed(self, value: int) -> None:
        self.revolution_angle_label.setText(f"{value}°")
        self._update_interactive_3d(fit_camera=False)

    def _toggle_revolution_animation(self) -> None:
        if self._revolution_timer.isActive():
            self._revolution_timer.stop()
            self.play_revolution_btn.setText("▶ Continuar giro")
        else:
            if self.revolution_slider.value() >= 360:
                self.revolution_slider.setValue(5)
            self._revolution_timer.start()
            self.play_revolution_btn.setText("⏸ Pausar")

    def _on_revolution_timer_tick(self) -> None:
        val = self.revolution_slider.value()
        if val >= 360:
            self._revolution_timer.stop()
            self.play_revolution_btn.setText("▶ Girar poco a poco (GeoGebra)")
        else:
            next_val = min(360, val + 4)
            self.revolution_slider.setValue(next_val)

    def _reset_revolution_to_full(self) -> None:
        """Restaura el sólido completo continuo a 360° y limpia rebanadas/Riemann."""
        if hasattr(self, "_revolution_timer") and self._revolution_timer.isActive():
            self._revolution_timer.stop()
            self.play_revolution_btn.setText("▶ Girar poco a poco (GeoGebra)")
        self.slice_check.blockSignals(True)
        self.slice_check.setChecked(False)
        self.slice_check.blockSignals(False)
        self.riemann_check.blockSignals(True)
        self.riemann_check.setChecked(False)
        self.riemann_check.blockSignals(False)
        self.revolution_slider.setValue(360)
        self.revolution_angle_label.setText("360°")
        self._update_interactive_3d(fit_camera=False)

    def _on_slice_check_toggled(self, checked: bool) -> None:
        if checked and self.riemann_check.isChecked():
            self.riemann_check.blockSignals(True)
            self.riemann_check.setChecked(False)
            self.riemann_check.blockSignals(False)
        self._update_interactive_3d(fit_camera=False)

    def _on_slice_slider_changed(self, _val: int) -> None:
        if self._current_region is not None:
            num_a, num_b, _, _ = _evaluate_bounds(self._current_region.a, self._current_region.b)
            frac = self.slice_slider.value() / 1000.0
            t_pos = num_a + frac * (num_b - num_a)
            self.slice_pos_label.setText(f"{self._current_region.variable} = {t_pos:.2f}")
        if not self.slice_check.isChecked():
            self.slice_check.setChecked(True)
        else:
            self._update_interactive_3d(fit_camera=False)

    def _on_riemann_check_toggled(self, checked: bool) -> None:
        if checked and self.slice_check.isChecked():
            self.slice_check.blockSignals(True)
            self.slice_check.setChecked(False)
            self.slice_check.blockSignals(False)
        self._update_interactive_3d(fit_camera=False)

    def _on_riemann_slider_changed(self, val: int) -> None:
        self.riemann_count_label.setText(f"N = {val}")
        if not self.riemann_check.isChecked():
            self.riemann_check.setChecked(True)
        else:
            self._update_interactive_3d(fit_camera=False)

    def _update_interactive_3d(self, fit_camera: bool = False) -> None:
        if self._current_region is None or self._current_axis is None:
            return

        theta_rad = math.radians(self.revolution_slider.value())
        num_a, num_b, _, _ = _evaluate_bounds(self._current_region.a, self._current_region.b)

        if self.slice_check.isChecked():
            frac = self.slice_slider.value() / 1000.0
            t_pos = num_a + frac * (num_b - num_a)
            self.slice_pos_label.setText(f"{self._current_region.variable} = {t_pos:.2f}")
            mesh = generate_representative_slice(
                self._current_region,
                axis=self._current_axis,
                position=t_pos,
                theta_max=theta_rad,
            )
            color_outer = "#F59E0B"
        elif self.riemann_check.isChecked():
            n = self.riemann_slider.value()
            self.riemann_count_label.setText(f"N = {n}")
            mesh = generate_riemann_mesh(
                self._current_region,
                axis=self._current_axis,
                num_disks=n,
                theta_max=theta_rad,
            )
            color_outer = "#38BDF8"
        else:
            mesh = generate_solid_mesh(
                self._current_region,
                axis=self._current_axis,
                theta_max=theta_rad,
            )
            color_outer = "#5CE1FF"

        if mesh.is_valid:
            self.canvas3d.plot_solid_mesh(mesh, color_outer=color_outer, show_axis=True)
            self.threejs_viewer.plot_solid_mesh(mesh, color_outer=color_outer, show_axis=True, fit_camera=fit_camera)

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
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

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
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            self.steps_text.print_(printer)
            return True
        except Exception as exc:
            self.status_bar.showMessage(f"✖ No se pudo guardar el PDF: {exc}")
            return False

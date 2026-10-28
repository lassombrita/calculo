"""Ventana principal de IntegralLab.

Responsabilidad:
Crear y gestionar la interfaz gráfica de usuario con todas las vistas principales
para entrada de expresiones, visualización 2D/3D, control de parámetros y reportes.
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
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Ventana principal con todas las vistas y controles."""
    
    def __init__(self) -> None:
        super().__init__()
        
        self.setWindowTitle("IntegralLab — Calculadora de integrales")
        self.setGeometry(100, 100, 1200, 800)
        
        # Configuración de tema Glass/Dark
        self.apply_theme()
        
        # Crear layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Vista de entrada de expresión (izquierda)
        input_panel = QWidget()
        input_layout = QHBoxLayout(input_panel)
        input_layout.addWidget(QLabel("Integral:"))
        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText("Ej. x**2 + sin(x)")
        input_layout.addWidget(self.expression_input, 1)
        input_layout.addStretch()
        input_panel.setFixedSize(300, 50)
        
        # Vista de resultados (centro-izquierda)
        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.addWidget(QLabel("Resultado:"))
        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)
        results_layout.addWidget(self.results_label, 1)
        results_panel.setFixedSize(400, 50)
        
        # Vista gráfica (derecha)
        graph_panel = QWidget()
        graph_layout = QVBoxLayout(graph_panel)
        from integrallab.viz.matplotlib import create_canvas
        self.canvas_widget = create_canvas()
        graph_layout.addWidget(self.canvas_widget, 1)
        graph_panel.setFixedSize(500, 400)
        
        # Panel de controles (inferior)
        controls_panel = QWidget()
        controls_layout = QHBoxLayout(controls_panel)
        
        self.calculate_button = QPushButton("Calcular")
        self.calculate_button.clicked.connect(self._on_calculate)
        controls_layout.addWidget(self.calculate_button)
        
        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self._on_clear)
        controls_layout.addWidget(self.clear_button)
        
        controls_panel.setFixedSize(200, 50)
        
        # Agregar paneles al layout principal
        main_layout.addWidget(input_panel)
        main_layout.addWidget(results_panel)
        main_layout.addStretch()
        main_layout.addWidget(graph_panel)
        main_layout.addWidget(controls_panel)
    
    def _on_calculate(self) -> None:
        """Botón para calcular la integral."""
        expr = self.expression_input.text().strip()
        if not expr:
            return
        
        self.results_label.setText(f"Calculando {expr}...")
        
        def run():
            from integrallab.core.operations import integrate_indefinite
            result = integrate_indefinite(expr)
            
            if result.is_success:
                self.results_label.setText(
                    f"Integral indefinida:\n{result.plain_text}"
                )
            else:
                self.results_label.setText(f"Error: {result.error_message}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def _on_clear(self) -> None:
        """Botón para limpiar el panel de resultados."""
        self.results_label.setText("")
        self.expression_input.clear()
    
    def apply_theme(self) -> None:
        """Aplica el tema Glass/Dark."""
        # Esta implementación está en ui/theme.py
        pass
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """Maneja el cierre de la ventana."""
        answer = QMessageBox.question(
            self,
            "Salir",
            "¿Desea realmente salir de IntegralLab?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if answer == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


def run() -> None:
    """Punto de entrada para ejecutar la aplicación."""
    import sys
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
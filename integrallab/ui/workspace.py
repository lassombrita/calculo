"""Espacio de trabajo principal: layout aurora + gráfica premium con AI panel.

Responsabilidad:
Proporcionar el esqueleto visual de IntegralLab con:
- Fondo "aurora": dos resplandores suaves sobre negro profundo (#05070D)
- Split horizontal entre gráfica (izquierda) y chat AI (derecha)
- GlassCard para los paneles con efectos de cristal translúcido

Esta clase es la base para el nuevo diseño premium. Para mantener compatibilidad
con tu código existente, usa ``Workspace`` como widget central en ``QMainWindow``.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from integrallab.ui.theme import Palette
from integrallab.ui.widgets.chat_panel import ChatPanel
from integrallab.ui.widgets.glass import GlassCard
from integrallab.viz.canvas import PremiumCanvas


class Workspace(QWidget):
    """Espacio de trabajo: izquierda gráfica premium (GlassCard), derecha chat AI.

    El widget central debe ser ``Workspace`` en tu ``QMainWindow.setCentralWidget()``.

    API pública para conectar con cálculos existentes:
    - workspace.canvas.plot_series(...): dibuja series con reveal animation
    - workspace.chat.begin_thinking(), begin_stream(), append_stream(), etc.: interacción IA
    - workspace.canvas.show_empty_state(): muestra mensaje inicial
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        # Componentes principales
        self.canvas = PremiumCanvas()  # Canvas premium con reveal + tooltip
        self.chat = ChatPanel()         # Panel de IA con streaming + pasos

        # ── Gráfica dentro de GlassCard (cristal translúcido) ────────────────────────
        plot_card = GlassCard(radius=22, glow=Palette.CYAN, elevated=False)
        col = QVBoxLayout(plot_card)
        col.setContentsMargins(20, 18, 20, 14)
        col.setSpacing(8)
        
        # Cabecera de gráfica (título + motor)
        head = QHBoxLayout()
        title = QLabel("Gráfica")
        engine = QLabel("Matplotlib")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(engine)
        col.addLayout(head)
        
        # Canvas ocupa el espacio restante
        col.addWidget(self.canvas, 1)

        # ── Split horizontal: gráfica (3 partes) | chat AI (2 partes) ─────────────────
        split = QHBoxLayout()  # Usando QSplitter implicito con layout
        split.setContentsMargins(22, 22, 22, 22)
        split.setSpacing(0)
        
        # Factor de estiramiento: gráfica más ancha que chat
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(plot_card)
        split.addLayout(plot_layout)

        # Chat AI con scroll auto
        chat_scroll = QScrollArea()
        chat_scroll.setWidgetResizable(True)
        chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chat_scroll.viewport().setStyleSheet("background: transparent;")
        
        chat_host = QWidget()
        chat_layout = QVBoxLayout(chat_host)
        chat_layout.addWidget(self.chat, 1)  # Chat expande verticalmente
        chat_scroll.setWidget(chat_host)
        split.addLayout(chat_layout)

        # Estirar gráfica a 3 partes y chat a 2 partes
        # Nota: En layout horizontal, usamos QWidget con fixedWidth o QSplitter
        # Aquí simplificamos: el canvas expande naturalmente
        plot_widget.setMinimumWidth(self.canvas.width() - plot_card.frameShape())

        split.addWidget(plot_widget)
        split.addWidget(chat_scroll)

        # Layout principal de la ventana
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(split)

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Fondo aurora: dos resplandores suaves sobre negro profundo."""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(Palette.VOID))
        
        # Primer resplandor: cian (esquina superior izquierda)
        center1 = QPointF(self.width() * 0.12, self.height() * 0.05)
        radius1 = self.width() * 0.55
        grad1 = QRadialGradient(center1, radius1)
        c1 = QColor(Palette.CYAN)
        c1.setAlpha(46)
        grad1.setColorAt(0.0, c1)
        c1.setAlpha(0)
        grad1.setColorAt(1.0, c1)
        p.fillRect(self.rect(), grad1)

        # Segundo resplandor: violeta (esquina inferior derecha)
        center2 = QPointF(self.width() * 0.95, self.height() * 0.98)
        radius2 = self.width() * 0.6
        grad2 = QRadialGradient(center2, radius2)
        c2 = QColor(Palette.VIOLET)
        c2.setAlpha(46)
        grad2.setColorAt(0.0, c2)
        c2.setAlpha(0)
        grad2.setColorAt(1.0, c2)
        p.fillRect(self.rect(), grad2)

        p.end()

    # ── API PÚBLICA PARA INTEGRACIÓN CON CÓDIGO EXISTENTE ────────────────────────

    def set_backend_label(self, text: str) -> None:
        """Actualiza la etiqueta del backend en el chat AI."""
        self.chat.set_backend_label(text)

    def begin_thinking(self) -> None:
        """Método para iniciar estado de 'pensando' en el panel AI."""
        self.chat.begin_thinking()

    def begin_stream(self) -> None:
        """Método para comenzar streaming de respuesta de la IA."""
        self.chat.begin_stream()

    def append_stream(self, chunk: str) -> None:
        """Método para agregar un chunk al streaming de la IA."""
        self.chat.append_stream(chunk)

    def add_steps(self, steps) -> None:
        """Método para agregar pasos explicativos a la respuesta de la IA."""
        self.chat.add_steps(steps)

    def show_error(self, message: str) -> None:
        """Método para mostrar un error en el panel AI."""
        self.chat.show_error(message)

    def finish(self) -> None:
        """Método para finalizar la interacción con la IA."""
        self.chat.finish()

    def show_empty_state(self, message: str = "Escribe una función para ver su gráfica") -> None:
        """Muestra el estado inicial vacío del canvas premium."""
        self.canvas.show_empty_state(message)

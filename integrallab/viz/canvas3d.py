"""Lienzo de visualización tridimensional para sólidos de revolución con Matplotlib.

Responsabilidad:
Proporcionar un widget Qt (FigureCanvasQTAgg con Axes3D) para renderizar mallas
numéricas de sólidos de revolución (SolidMesh3D) sin dependencias simbólicas ni SymPy.
Soporta renderizado de superficies exterior e interior con transparencia, visualización
del eje de rotación, animación automática de rotación al generar el sólido y zoom
interactivo con la rueda del ratón.
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import mpl_toolkits.mplot3d  # noqa: F401 - Registra projection='3d' en Matplotlib
from PySide6.QtCore import QTimer

from integrallab.core.solids import AxisOrientation, SolidMesh3D
from integrallab.viz.style import apply_mpl_theme, style_legend


class PlotCanvas3D(FigureCanvasQTAgg):
    """Widget de visualización 3D interactivo embebido en PySide6.

    Consume exclusivamente estructuras de datos numéricas generadas por el dominio
    (SolidMesh3D con matrices NumPy) y gestiona la cámara, iluminación, materiales
    translúcidos, el trazado del eje de giro, animación de rotación automática y
    zoom con la rueda del ratón.
    """

    def __init__(
        self,
        parent: object | None = None,
        width: float = 6.0,
        height: float = 5.0,
        dpi: int = 100,
    ) -> None:
        """Inicializa la figura de Matplotlib y configura el subsistema Axes3D.

        Args:
            parent: Widget padre en la jerarquía de PySide6 (opcional).
            width: Ancho inicial de la figura en pulgadas.
            height: Alto inicial de la figura en pulgadas.
            dpi: Resolución en puntos por pulgada.
        """
        apply_mpl_theme()
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.figure.patch.set_alpha(0.0)
        super().__init__(self.figure)
        self.setStyleSheet("background: transparent;")
        if parent is not None:
            self.setParent(parent)  # type: ignore[arg-type]

        self.axes = self.figure.add_subplot(111, projection="3d")
        self._surface_collections: list[object] = []
        self._axis_lines: list[object] = []
        self._setup_axes_style()

        # ── Animación de rotación automática ──────────────────────────────────
        self._rotation_timer: QTimer = QTimer()
        self._rotation_timer.setInterval(50)          # 50 ms ≈ 20 fps
        self._rotation_timer.timeout.connect(self._rotation_step)
        self._rotation_frame: int = 0
        self._rotation_total_frames: int = 80         # 80 × 50ms = 4 segundos
        self._rotation_elev: float = 25.0
        self._rotation_azim_start: float = 45.0

        # ── Zoom con rueda del ratón ──────────────────────────────────────────
        self.mpl_connect("scroll_event", self._on_scroll)

    def _rotation_step(self) -> None:
        """Avanza un frame de la animación de rotación automática del sólido 3D."""
        self._rotation_frame += 1
        azim = self._rotation_azim_start + self._rotation_frame * 4.5
        self.axes.view_init(elev=self._rotation_elev, azim=azim)
        self.draw()
        if self._rotation_frame >= self._rotation_total_frames:
            self._rotation_timer.stop()
            self._rotation_frame = 0

    def _on_scroll(self, event: object) -> None:
        """Realiza zoom in/out en el lienzo 3D mediante la rueda del ratón.

        Args:
            event: Evento de Matplotlib con atributo ``button`` ('up' / 'down').
        """
        if not hasattr(event, "button"):
            return
        current_dist = getattr(self.axes, "dist", 10)
        if getattr(event, "button", None) == "up":
            new_dist = max(2.0, current_dist * 0.88)
        else:
            new_dist = min(30.0, current_dist * 1.12)
        self.axes.dist = new_dist  # type: ignore[attr-defined]
        self.draw()

    def _setup_axes_style(self) -> None:
        """Establece la configuración inicial de etiquetas, orientación y rejilla 3D."""
        self.axes.set_xlabel("X", labelpad=8)
        self.axes.set_ylabel("Y", labelpad=8)
        self.axes.set_zlabel("Z", labelpad=8)
        # Vista en perspectiva isométrica educativa
        self.axes.view_init(elev=25, azim=45)
        self.axes.grid(True, linestyle=":", alpha=0.5)
        self.axes.set_facecolor("none")
        for axis in (self.axes.xaxis, self.axes.yaxis, self.axes.zaxis):
            axis.set_pane_color((1.0, 1.0, 1.0, 0.035))
            axis.pane.set_edgecolor((1.0, 1.0, 1.0, 0.10))
            axis.label.set_color("#8B95B5")
        self.axes.tick_params(colors="#8B95B5", labelsize=8)

    @property
    def surface_collections(self) -> list[object]:
        """Retorna la lista de superficies (Poly3DCollection) renderizadas en el lienzo."""
        return list(self._surface_collections)

    @property
    def axis_lines(self) -> list[object]:
        """Retorna las líneas que representan el eje de rotación en 3D."""
        return list(self._axis_lines)

    def clear_canvas(self) -> None:
        """Limpia las superficies y restablece la escena tridimensional."""
        self.axes.clear()
        self._surface_collections.clear()
        self._axis_lines.clear()
        self._setup_axes_style()
        self.draw()

    def plot_solid_mesh(
        self,
        mesh: SolidMesh3D,
        color_outer: str = "#5CE1FF",
        color_inner: str = "#FF6B8A",
        alpha: float = 0.6,
        show_axis: bool = True,
        clear: bool = True,
    ) -> bool:
        """Renderiza una malla tridimensional de revolución en el lienzo.

        Args:
            mesh: Contenedor SolidMesh3D con matrices NumPy finitas.
            color_outer: Color hexadecimal de la superficie exterior.
            color_inner: Color hexadecimal de la superficie interior (si existe vacío).
            alpha: Grado de transparencia (0.0 transparente a 1.0 opaco).
            show_axis: Si es True, traza una línea distintiva para el eje de giro.
            clear: Si es True, limpia el contenido previo del lienzo.

        Returns:
            True si el sólido se dibujó correctamente, False si la malla es inválida.
        """
        if not mesh.is_valid:
            return False

        if clear:
            self.clear_canvas()

        # 1. Dibujar la superficie exterior
        try:
            surf_out = self.axes.plot_surface(
                mesh.x_outer,
                mesh.y_outer,
                mesh.z_outer,
                color=color_outer,
                alpha=alpha,
                edgecolor="none",
                shade=True,
                antialiased=True,
            )
            self._surface_collections.append(surf_out)
        except Exception:
            return False

        # 2. Dibujar la superficie interior (en arandelas o sólidos con hueco)
        if (
            mesh.x_inner is not None
            and mesh.y_inner is not None
            and mesh.z_inner is not None
        ):
            try:
                surf_in = self.axes.plot_surface(
                    mesh.x_inner,
                    mesh.y_inner,
                    mesh.z_inner,
                    color=color_inner,
                    alpha=min(alpha + 0.15, 0.95),
                    edgecolor="none",
                    shade=True,
                    antialiased=True,
                )
                self._surface_collections.append(surf_in)
            except Exception:
                pass

        # 3. Dibujar el eje de rotación con línea discontinua destacada
        if show_axis:
            self._draw_revolution_axis(mesh)

        self.draw()

        # 4. Iniciar animación de rotación automática (360° en 4 segundos)
        self._rotation_frame = 0
        self._rotation_azim_start = 45.0
        self._rotation_timer.start()

        return True

    def _draw_revolution_axis(self, mesh: SolidMesh3D) -> None:
        """Traza el eje de giro (horizontal o vertical) extendido ligeramente sobre la figura."""
        pos = mesh.axis.position

        if mesh.axis.orientation == AxisOrientation.HORIZONTAL:
            # Eje horizontal y = k a lo largo de X
            x_min = float(np.nanmin(mesh.x_outer))
            x_max = float(np.nanmax(mesh.x_outer))
            pad = max(abs(x_max - x_min) * 0.2, 0.5)
            x_line = [x_min - pad, x_max + pad]
            y_line = [pos, pos]
            z_line = [0.0, 0.0]
        else:
            # Eje vertical x = h a lo largo de Y
            y_min = float(np.nanmin(mesh.y_outer))
            y_max = float(np.nanmax(mesh.y_outer))
            pad = max(abs(y_max - y_min) * 0.2, 0.5)
            x_line = [pos, pos]
            y_line = [y_min - pad, y_max + pad]
            z_line = [0.0, 0.0]

        lines = self.axes.plot(
            x_line,
            y_line,
            z_line,
            color="#FFB454",
            linestyle="--",
            linewidth=2.2,
            label=f"Eje de giro: {mesh.axis.label}",
        )
        self._axis_lines.extend(lines)
        style_legend(self.axes.legend(loc="upper right", framealpha=0.9))

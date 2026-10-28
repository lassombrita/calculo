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
        # Orden de dibujo fijo (interior → exterior → eje). Con el orden automático por
        # profundidad media, la superficie interior (rosa) se pintaba ENCIMA de la exterior.
        self.axes.computed_zorder = False
        self._surface_collections: list[object] = []
        self._draw_deferred = False
        self._auto_rotate = True
        self._axis_lines: list[object] = []

        # Escala de la vista: proporciones reales de la caja y factor de zoom.
        self._box_aspect: tuple[float, float, float] | None = None
        self._zoom: float = 1.0
        self._setup_axes_style()

        # ── Animación de rotación automática ──────────────────────────────────
        self._rotation_timer: QTimer = QTimer(self)
        self._rotation_timer.setInterval(50)          # 50 ms ≈ 20 fps
        self._rotation_timer.timeout.connect(self._rotation_step)
        self._rotation_frame: int = 0
        self._rotation_total_frames: int = 80         # 80 × 50ms = 4 segundos
        self._rotation_elev: float = 25.0
        self._rotation_azim_start: float = 45.0

        # ── Interacción: zoom con la rueda y cancelación de la animación al arrastrar ──
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("button_press_event", self._stop_rotation)

    # ── Dibujo solo cuando se ve ─────────────────────────────────────────────

    def _hidden_in_visible_window(self) -> bool:
        """True si la ventana está a la vista pero este lienzo no (motor WebGL u otra pestaña)."""
        win = self.window()
        return win is not None and win.isVisible() and not self.isVisible()

    def draw(self) -> None:  # noqa: D102 - pospone el dibujo si el lienzo está oculto
        if self._hidden_in_visible_window():
            self._draw_deferred = True
            return
        super().draw()

    def draw_idle(self) -> None:  # noqa: D102
        if self._hidden_in_visible_window():
            self._draw_deferred = True
            return
        super().draw_idle()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._draw_deferred:
            self._draw_deferred = False
            self.draw_idle()

    def set_auto_rotate(self, enabled: bool) -> None:
        """Activa o desactiva la animación de giro al dibujar un sólido (se recuerda)."""
        self._auto_rotate = bool(enabled)
        if not enabled:
            self._stop_rotation()

    def reset_view(self) -> None:
        """Vuelve a la vista isométrica inicial con zoom 1."""
        self._stop_rotation()
        self._zoom = 1.0
        self.axes.view_init(elev=25, azim=45)
        self._apply_view_scale()
        self.draw_idle()

    def _rotation_step(self) -> None:
        """Avanza un frame de la animación de rotación automática del sólido 3D."""
        if self._hidden_in_visible_window():
            # Oculto (motor WebGL activo u otra pestaña): no gastar CPU del hilo de la interfaz.
            self._stop_rotation()
            return
        self._rotation_frame += 1
        azim = self._rotation_azim_start + self._rotation_frame * 4.5
        self.axes.view_init(elev=self._rotation_elev, azim=azim)
        self.draw_idle()
        if self._rotation_frame >= self._rotation_total_frames:
            self._stop_rotation()

    def _stop_rotation(self, _event: object | None = None) -> None:
        """Detiene la rotación automática (p. ej. cuando el usuario toma el control)."""
        self._rotation_timer.stop()
        self._rotation_frame = 0

    def _apply_view_scale(self) -> None:
        """Aplica las proporciones reales de la caja 3D y el zoom actual."""
        self.axes.set_box_aspect(self._box_aspect, zoom=self._zoom)

    def _fit_box_aspect(self) -> None:
        """Ajusta la caja 3D a las proporciones reales de los datos (misma escala en x, y, z).

        Sin esto, Matplotlib dibuja una caja 4:4:3 y deforma el sólido (un plato poco
        profundo se ve como una trompeta alargada).
        """
        ranges = [
            abs(float(hi) - float(lo))
            for lo, hi in (
                self.axes.get_xlim3d(),
                self.axes.get_ylim3d(),
                self.axes.get_zlim3d(),
            )
        ]
        biggest = max(ranges)
        if not np.isfinite(biggest) or biggest <= 0.0:
            self._box_aspect = None
        else:
            floor = 0.05 * biggest
            self._box_aspect = (
                max(ranges[0], floor),
                max(ranges[1], floor),
                max(ranges[2], floor),
            )
            # Menos marcas en los ejes cortos para que las etiquetas no se amontonen.
            for axis_name, axis_range in zip("xyz", ranges):
                nbins = int(np.clip(round(6 * axis_range / biggest), 3, 7))
                self.axes.locator_params(axis=axis_name, nbins=nbins)
        self._apply_view_scale()

    def _on_scroll(self, event: object) -> None:
        """Realiza zoom in/out en el lienzo 3D mediante la rueda del ratón.

        Args:
            event: Evento de Matplotlib con atributo ``button`` ('up' / 'down').
        """
        button = getattr(event, "button", None)
        if button == "up":
            self._zoom = min(5.0, self._zoom * 1.12)
        elif button == "down":
            self._zoom = max(0.4, self._zoom / 1.12)
        else:
            return
        self._apply_view_scale()
        self.draw_idle()

    def _setup_axes_style(self) -> None:
        """Establece la configuración inicial de etiquetas, orientación y rejilla 3D."""
        self.axes.set_xlabel("X", labelpad=8)
        self.axes.set_ylabel("Y", labelpad=8)
        self.axes.set_zlabel("Z", labelpad=8)
        # Vista en perspectiva isométrica educativa
        self.axes.view_init(elev=25, azim=45)
        self._apply_view_scale()
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

    def clear_canvas(self, redraw: bool = True) -> None:
        """Limpia las superficies y restablece la escena tridimensional."""
        self._stop_rotation()
        self.axes.clear()
        self.axes.computed_zorder = False
        self._surface_collections.clear()
        self._axis_lines.clear()
        self._box_aspect = None
        self._zoom = 1.0
        self._setup_axes_style()
        if redraw:
            self.draw_idle()

    def plot_solid_mesh(
        self,
        mesh: SolidMesh3D,
        color_outer: str = "#5CE1FF",
        color_inner: str = "#FF6B8A",
        alpha: float = 0.6,
        show_axis: bool = True,
        clear: bool = True,
        keep_camera: bool = False,
    ) -> bool:
        """Renderiza una malla tridimensional de revolución en el lienzo.

        Args:
            mesh: Contenedor SolidMesh3D con matrices NumPy finitas.
            color_outer: Color hexadecimal de la superficie exterior.
            color_inner: Color hexadecimal de la superficie interior (si existe vacío).
            alpha: Grado de transparencia (0.0 transparente a 1.0 opaco).
            show_axis: Si es True, traza una línea distintiva para el eje de giro.
            clear: Si es True, limpia el contenido previo del lienzo.
            keep_camera: Conserva elevación, azimut y zoom y no relanza la rotación automática
                (cuadros de los deslizadores). Antes cada movimiento devolvía la vista a 25°/45°/1.

        Returns:
            True si el sólido se dibujó correctamente, False si la malla es inválida.
        """
        if not mesh.is_valid:
            return False

        camera = (self.axes.elev, self.axes.azim, self._zoom) if keep_camera and self._surface_collections else None
        limits = (self.axes.get_xlim3d(), self.axes.get_ylim3d(), self.axes.get_zlim3d()) if camera else None
        if clear and camera is not None:
            # Cuadro de un deslizador: se quitan solo las superficies y el eje. ``axes.clear()``
            # rehacía marcas, etiquetas y estilo (≈ 18 ms de los ≈ 40 ms de cada cuadro).
            for artist in [*self._surface_collections, *self._axis_lines]:
                try:
                    artist.remove()
                except (ValueError, NotImplementedError):
                    pass
            self._surface_collections.clear()
            self._axis_lines.clear()
            self._stop_rotation()
        elif clear:
            self.clear_canvas(redraw=False)  # un único dibujo al final, no dos

        # La malla puede venir densa (64 × 48) para el visor WebGL; Matplotlib la submuestrea a
        # una densidad parecida a la anterior (≈ 20 × 25 caras) para no encarecer cada cuadro.
        rows, cols = mesh.x_outer.shape
        stride = {"rcount": min(rows, 20), "ccount": min(cols, 25)}

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
                zorder=2,
                **stride,
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
                    zorder=1,
                    rcount=min(mesh.x_inner.shape[0], 20),
                    ccount=min(mesh.x_inner.shape[1], 25),
                )
                self._surface_collections.append(surf_in)
            except Exception:
                pass

        # 3. Dibujar el eje de rotación con línea discontinua destacada
        if show_axis:
            self._draw_revolution_axis(mesh)

        # 4. Proporciones reales (misma escala en los tres ejes) y zoom inicial (o el anterior)
        if camera is not None and limits is not None:
            # Misma caja y cámara: abrir el ángulo no debe acercar ni girar la vista.
            self.axes.set_xlim3d(*limits[0])
            self.axes.set_ylim3d(*limits[1])
            self.axes.set_zlim3d(*limits[2])
            self.axes.view_init(elev=camera[0], azim=camera[1])
            self._zoom = camera[2]
            self._apply_view_scale()
        else:
            self._zoom = 1.0
            self._fit_box_aspect()

        self.draw_idle()
        if camera is not None:
            return True

        # 5. Animación de rotación automática (360° en 4 segundos), solo si el lienzo se ve.
        #    Antes corría siempre: con el motor WebGL activo eran 80 redibujados ocultos de
        #    ~36 ms cada uno (≈ 2,9 s de CPU del hilo de la interfaz por cada sólido).
        self._rotation_frame = 0
        self._rotation_azim_start = 45.0
        if self._auto_rotate and not self._hidden_in_visible_window():
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
            zorder=3,
        )
        self._axis_lines.extend(lines)
        style_legend(self.axes.legend(loc="upper right", framealpha=0.9))

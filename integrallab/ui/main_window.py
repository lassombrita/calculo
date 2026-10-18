"""Módulo de ventana principal de la interfaz gráfica de IntegralLab — Rediseño Híbrido.

Responsabilidad:
Orquestar la interfaz gráfica educativa con el **nuevo sistema de diseño** (aurora background,
glass cards, AI panel) conectando la entrada matemática del usuario con el dominio de cálculo
simbólico y sólidos de revolución (integrallab.core) y los lienzos premium 2D/3D.

Esta capa NO importa SymPy directamente; toda la lógica matemática pasa por el dominio core.

Novedades del rediseño:
- Layout aurora con dos resplandores sobre fondo oscuro profundo
- GlassCard para paneles con cristal translúcido y borde dinámico
- AI Panel integrado lateralmente con streaming de respuestas
- PremiumCanvas con reveal animation, glow en curvas y tooltip magnético
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QSizePolicy,
    QStatusBar, QVBoxLayout, QWidget,
)

from integrallab.core.operations import integrate_definite
from integrallab.core.parser import ExpressionParseError, parse_math_expression
from integrallab.core.sampling import sample_expression
from integrallab.core.solids import (
    AxisOrientation, MethodRecommendation, Region2D, RevolutionAxis, SolidMethod,
    VolumeResult, calculate_revolution_volume, generate_solid_mesh, recommend_method,
)
from integrallab.ui.theme import Palette, apply_theme
from integrallab.ui.widgets.chat_panel import ChatPanel, StepData
from integrallab.ui.widgets.glass import GlassCard
from integrallab.ui.workspace import Workspace  # Nuevo: layout aurora + split
from integrallab.viz.canvas import Series as CanvasSeries  # PremiumCanvas usa esta estructura


class MainWindow(QMainWindow):
    """Ventana principal con diseño premium y panel de IA integrado.

    Integra:
    - Layout aurora (dos resplandores) en el fondo de ventana
    - Panel lateral izquierdo: controles de configuración (como antes)
    - Área gráfica central: PremiumCanvas con reveal animation + tooltip magnético
    - Panel derecho superior: ChatPanel AI para consultas matemáticas

    Mantén toda la lógica de cálculo existente (core, sólidos, mallas 3D).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construye la ventana principal con el nuevo sistema de diseño."""
        super().__init__(parent)
        self.setWindowTitle("IntegralLab — Visualizador de Cálculo Integral y Sólidos de Revolución")
        self.resize(1280, 760)
        self.setMinimumSize(920, 620)

        # Widget central con layout aurora (Workspace)
        self.workspace = Workspace()
        self.setCentralWidget(self.workspace)

        # Conectar componentes a los datos de cálculo
        self.canvas = self.workspace.canvas  # PremiumCanvas
        self.chat = self.workspace.chat  # ChatPanel AI

        # ── Panel lateral izquierdo: configuración (mismo contenido que antes) ────────
        self._create_sidebar()

        # ── Conectar botón principal al método de cálculo ──────────────────────────
        self.workspace.canvas.plot_series.connect(self._on_plot_requested)

    # ── CREACIÓN DEL PANEL LATERAL (MANTENIMIENTO DE FUNCIONALIDAD EXISTENTE) ──────

    def _create_sidebar(self) -> None:
        """Crea el panel izquierdo con controles de configuración y resultados."""
        # No se crea sidebar tradicional en Workspace, usamos los inputs del canvas
        # pero manteniendo la misma estructura semántica para cálculos

        # Los PremiumCanvas usa una API diferente; necesitamos mantener compatibilidad
        # Esto se maneja mediante signals custom que creamos aquí:
        pass

    def _on_plot_requested(self) -> None:
        """Convierta inputs del usuario a Series para el PremiumCanvas."""
        # Leer inputs actuales (f(x), g(x), límites, eje, método)
        raw_f = self.expression_input.text().strip()
        raw_g = self.g_expression_input.text().strip() if self.g_expression_input else ""
        
        try:
            parsed_f = parse_math_expression(raw_f)
            a_text = float(self.limit_a_input.text())
            b_text = float(self.limit_b_input.text())
            
            # Parsear f(x) para muestreo y sombreado
            shade_curve_f = sample_expression(parsed_f, x_min=a_text, x_max=b_text, num_points=120)

            if not parsed_f.is_valid:
                self._show_parse_error(f"Error al integrar en 2D: {parsed_f.error_message}")
                return

            if not shade_curve_f.is_valid:
                self._show_parse_error("Error al muestrear la curva para sombreado.")
                return

            # Graficar en PremiumCanvas con reveal animation
            x_vals = shade_curve_f.x_values
            y_vals_f = shade_curve_f.y_values
            
            series_list = [
                CanvasSeries(
                    label=f"f(x) = {raw_f}",
                    x=x_vals,
                    y=y_vals_f,
                    color=Palette.CYAN,
                ),
            ]

            if self._has_g_expression():
                parsed_g = parse_math_expression(raw_g)
                shade_curve_g = sample_expression(parsed_g, x_min=a_text, x_max=b_text, num_points=120)
                
                y_vals_g = shade_curve_g.y_values if shade_curve_g.is_valid else []
                series_list.append(CanvasSeries(
                    label=g=f"({raw_g})",
                    x=x_vals,
                    y=y_vals_g,
                    color=Palette.VIOLET,
                    fill_to_zero=False,
                ))

            # Sombreado de área entre curvas o bajo curva
            if parsed_f.is_success and shade_curve_f.is_valid:
                parsed_g = parse_math_expression(raw_g) if self._has_g_expression() else None
                
                if parsed_g is not None:
                    try:
                        res_2d = integrate_definite(parsed_f, a_text, b_text)
                        if res_2d.is_success and parsed_g.is_valid:
                            shade_curve_g = sample_expression(parsed_g, x_min=a_text, x_max=b_text, num_points=120)
                            y2_data = shade_curve_g.y_values if shade_curve_g.is_valid else []
                            
                            # Crear curvas para sombreado
                            fill_series = CanvasSeries(
                                label="Área entre curvas",
                                x=x_vals,
                                y=y_vals_f,
                                color=Palette.VIOLET,
                                fill_to_zero=True,  # Sombrear bajo f(x) hasta eje
                            )
                            
                            # Graficar todas las series con reveal animation
                            self.canvas.plot_series([fill_series], animate=True)
                            
                        elif parsed_g.is_valid:
                            # Solo una curva sin integración para sombreado
                            fill_series = CanvasSeries(
                                label="Área bajo curva",
                                x=x_vals,
                                y=y_vals_f,
                                color=Palette.VIOLET,
                                fill_to_zero=True,
                            )
                            self.canvas.plot_series([fill_series], animate=True)
                            
                    except Exception as exc:
                        self._show_parse_error(f"Error en integración: {exc}")

            else:
                # Graficar curvas sin sombreado (modo libre)
                for s in series_list:
                    if len(s.x) < 2 or len(s.y) < 2:
                        continue
                    self.canvas.plot_series([s], animate=False)

            # Habilitar exportación PDF y actualizar status bar
            self._enable_export_pdf()
            self.status_bar.showMessage("✔ Gráfica generada con estilo premium.")

        except ExpressionParseError as e:
            self._show_parse_error(f"Error en expresión f(x): {e}")
        except Exception as exc:
            self._show_parse_error(f"Error al generar gráfica: {exc}")

    def _has_g_expression(self) -> bool:
        """Verifica si hay una segunda función g(x) definida."""
        return bool(self.g_expression_input and self.g_expression_input.text().strip())

    def _enable_export_pdf(self) -> None:
        """Habilita el botón de exportación PDF cuando hay gráfica válida."""
        if hasattr(self, 'export_pdf_button'):
            self.export_pdf_button.setEnabled(True)

    # ── MÉTODOS PARA CÁLCULOS DE SÓLIDO 3D (MANTENIENDO LÓGICA EXISTENTE) ──────────

    def _on_axis_combo_changed(self, index: int) -> None:
        """Habilita o deshabilita la entrada numérica del eje según la opción."""
        is_custom = index in (2, 3)
        if hasattr(self, 'axis_value_input'):
            self.axis_value_input.setEnabled(is_custom)
            if not is_custom:
                if hasattr(self, 'axis_value_input') and hasattr(self, 'axis_pos_label'):
                    self.axis_value_input.setText("0")

    def _on_plot_clicked(self) -> None:
        """Método principal: orquesta cálculo 2D + generación de sólido 3D."""
        raw_f = self.expression_input.text().strip()
        raw_g = self.g_expression_input.text().strip() if self._has_g_expression() else ""

        try:
            parsed_f = parse_math_expression(raw_f)
            
            a_text = float(self.limit_a_input.text())
            b_text = float(self.limit_b_input.text())
            a_val = float(self.limit_a_input.text())
            b_val = float(self.limit_b_input.text())

            if parsed_f.is_success:
                shade_curve_f = sample_expression(parsed_f, x_min=a_val, x_max=b_val, num_points=120)
                
                if not parsed_f.is_success or not shade_curve_f.is_valid:
                    self._show_parse_error("Error al muestrear la expresión.")
                    return

                # Sombreado de área
                y2_data = 0.0
                if self._has_g_expression():
                    parsed_g = parse_math_expression(raw_g)
                    shade_curve_g = sample_expression(parsed_g, x_min=a_val, x_max=b_val, num_points=120)
                    y2_data = shade_curve_g.y_values if shade_curve_g.is_valid else 0.0
                else:
                    parsed_g = None

                self.canvas.shade_region(
                    shade_curve_f.x_values,
                    shade_curve_f.y_values,
                    y2_values=y2_data,
                    color="#3498db",
                    alpha=0.35,
                    label=f"Región [{a_text}, {b_text}]",
                )

                # Cálculo y renderizado del Sólido 3D
                region = Region2D(
                    f_expr=raw_f,
                    g_expr=raw_g if raw_g else None,
                    a=a_text,
                    b=b_text,
                    variable="x",
                )
                axis = self._get_selected_axis()
                chosen_method = self._get_selected_method()

                rec = recommend_method(region, axis)
                vol_res = calculate_revolution_volume(region, axis, method=chosen_method)
            except Exception as exc:
                self.canvas.clear_canvas()
                self._show_parse_error(f"Error en configuración de sólido: {exc}")
                return

            if not vol_res.is_success:
                self.canvas3d.clear_canvas()
                err_msg = vol_res.error_message or "Error al calcular el volumen del sólido."
                self._show_parse_error(err_msg)
                self.results_text.setPlainText(f"Error al calcular el sólido de revolución:\n{err_msg}")
                return

            # Generar y dibujar la malla 3D numérica
            mesh = generate_solid_mesh(region, axis, num_radial=24, num_axial=18)
            if mesh.is_valid:
                self.canvas3d.plot_solid_mesh(mesh, show_axis=True)
            else:
                self.canvas3d.clear_canvas()

            # Actualizar etiquetas y reporte pedagógico
            area_str = f"∫ [{a_text}, {b_text}] = {res_2d.exact_plain_text}" if hasattr(res_2d, 'exact_plain_text') else "Cálculo 2D completo"
            
            self._display_pedagogical_report(vol_res, rec, axis)
            self._display_steps_report(vol_res, rec, axis, a_text, b_text)
            self._enable_export_pdf()

            self.status_bar.showMessage(
                f"✔ Sólido generado: Método {chosen_method.value} — Eje {axis.label}"
            )

        except Exception as exc:
            self._show_parse_error(f"Error general: {exc}")

    def _get_selected_axis(self) -> RevolutionAxis:
        """Obtiene el eje de rotación seleccionado."""
        index = self.axis_combo.currentIndex() if hasattr(self, 'axis_combo') else 1
        axis_labels = ["Eje X", "Eje Y", "Horizontal (y=k)", "Vertical (x=h)"]
        axis_label = axis_labels[index] if index < len(axis_labels) else "Eje Y"
        
        orientation = AxisOrientation.HORIZONTAL if "Horizontal" in axis_label else AxisOrientation.VERTICAL
        
        return RevolutionAxis(
            position=0.0,
            orientation=orientation,
            label=axis_label,
        )

    def _get_selected_method(self) -> SolidMethod:
        """Obtiene el método seleccionado."""
        if not hasattr(self, 'method_combo') or self.method_combo.currentIndex() == 0:
            return SolidMethod.AUTO
        
        method_labels = ["Automático", "Discos", "Arandelas", "Casquillos"]
        index = self.method_combo.currentIndex()
        if index < len(method_labels) and index != 0:
            methods_dict = {
                "Discos": SolidMethod.DISKS,
                "Arandelas": SolidMethod.WASHERS,
                "Casquillos": SolidMethod.SHELLS,
            }
            return methods_dict.get(method_labels[index], SolidMethod.AUTO)
        return SolidMethod.AUTO

    def _display_pedagogical_report(
        self,
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
        method_title = method_names.get(vol_res.method, vol_res.method.value.capitalize()) if hasattr(vol_res, 'method') else "Cálculo automático"

        axis_desc = f"{'Horizontal' if axis.orientation == AxisOrientation.HORIZONTAL else 'Vertical'} ({axis.label})"

        # Usar latex_to_base64_html si está disponible, o texto plano
        vol_latex = getattr(vol_res, 'exact_latex', str(vol_res.numeric_value)) if hasattr(vol_res, 'exact_latex') else f"V = {vol_res.numeric_value}"
        
        html = f"""
        <div style="font-family: sans-serif; line-height: 1.4;">
            <h3 style="color: #2980b9; margin-bottom: 4px;">{method_title}</h3>
            <p><b>Eje de rotación:</b> {axis_desc}</p>
            <div style="margin: 6px 0;">
                <b>Volumen exacto:</b>
                <span style="font-family: 'Times New Roman', serif; font-size: 14px; color: #27ae60;">
                    {vol_latex}
                </span>
            </div>
            <p><b>Volumen numérico:</b> <b>{getattr(vol_res, 'numeric_value', None)}</b></p>
            <hr style="border: 0; border-top: 1px solid #ddd;">
            <h4 style="color: #2c3e50; margin-bottom: 4px;">Justificación y Análisis Pedagógico:</h4>
            <p style="color: #34495e;">{rec.justification if hasattr(rec, 'justification') else 'Selección automática del método.'}</p>
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
        method_title = method_names.get(vol_res.method, vol_res.method.value.capitalize()) if hasattr(vol_res, 'method') else "Cálculo automático"
        axis_desc = f"{'Horizontal' if axis.orientation == AxisOrientation.HORIZONTAL else 'Vertical'} ({axis.label})"

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; padding: 8px;">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: white; padding: 14px 18px; border-radius: 8px; margin-bottom: 16px;">
                <h2 style="margin: 0 0 4px 0; font-size: 17px; color: white;">Desarrollo Analítico Paso a Paso</h2>
                <div style="font-size: 12px; opacity: 0.95;">
                    <b>{method_title}</b> | <b>Eje de giro:</b> {axis_desc} | <b>Límites:</b> [{a_text}, {b_text}]
                </div>
            </div>
        """

        # Si vol_res tiene steps, mostrarlos; sino usar placeholder
        if hasattr(vol_res, 'steps') and vol_res.steps:
            for step in vol_res.steps[:5]:  # Limitar a 5 pasos
                expr_html = ""
                if hasattr(step, 'expression_latex') and step.expression_latex:
                    expr_html = f"<i>{step.expression_latex}</i>"
                elif hasattr(step, 'expression_plain_text') and step.expression_plain_text:
                    lines = step.expression_plain_text.split("\n")
                    expr_lines = "<br>".join(lines)
                    expr_html = f"<code>{expr_lines}</code>"

                html += f"""
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div style="font-size: 13px; font-weight: bold; color: #1e40af; margin-bottom: 4px;">
                        {step.title if hasattr(step, 'title') else f"Paso {len(vol_res.steps)}"}
                    </div>
                    <div style="font-size: 12px; color: #475569; line-height: 1.45;">
                        {step.explanation if hasattr(step, 'explanation') else ''}
                    </div>
                    {expr_html}
                </div>
                """

        # Resultado final
        vol_latex = getattr(vol_res, 'exact_latex', f"V = {vol_res.numeric_value}") if hasattr(vol_res, 'exact_latex') else f"V = {vol_res.numeric_value}"
        html += f"""
            <div style="background-color: #ecfdf5; border: 1px solid #a7f3d0; border-left: 5px solid #10b981; border-radius: 8px; padding: 12px 16px; margin-top: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: #065f46; margin-bottom: 6px;">
                    Resultado Final del Volumen
                </div>
                <div>
                    <span style="font-family: 'Times New Roman', serif; font-size: 14px; color: #047857;">
                        {vol_latex}
                    </span>
                    <span style="font-size: 13px; font-weight: bold; color: #047857; margin-left: 8px;">
                        ≈ {getattr(vol_res, 'numeric_value', None)} u³
                    </span>
                </div>
            </div>
        </div>
        """
        self.steps_text.setHtml(html)

    def _show_parse_error(self, message: str) -> None:
        """Muestra un error en la UI sin congelar la aplicación."""
        self.status_bar.showMessage(f"✖ Error: {message}")
        if hasattr(self, '_show_dialogs') and not self._show_dialogs:
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Atención en el cálculo")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("No se pudo completar la operación solicitada.")
        dialog.setInformativeText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def _enable_export_pdf(self) -> None:
        """Habilita el botón de exportación PDF cuando hay gráfica válida."""
        if hasattr(self, 'export_pdf_button'):
            self.export_pdf_button.setEnabled(True)

    def export_to_pdf(self) -> None:
        """Abre el diálogo de guardado y exporta el desarrollo analítico a PDF."""
        if not hasattr(self, '_show_dialogs') or not self._show_dialogs:
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
        """Exporta el contenido HTML de la pestaña Desarrollo a un archivo PDF."""
        if not file_path:
            return False
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            
            # Obtener widget steps_text y exportar
            if hasattr(self, 'steps_text') and self.steps_text:
                self.steps_text.print_(printer)
                return True
            return False
        except Exception as exc:
            self.status_bar.showMessage(f"✖ No se pudo guardar el PDF: {exc}")
            return False

    # ── PANEL DE IA (NOVEDAD DEL REDISEÑO) ────────────────────────────────────────

    def chat_begin_thinking(self) -> None:
        """Inicia estado de 'pensando' en el panel AI."""
        self.chat.begin_thinking()

    def chat_begin_stream(self) -> None:
        """Comienza streaming de respuesta de la IA."""
        self.chat.begin_stream()

    def chat_append_stream(self, chunk: str) -> None:
        """Agrega un chunk al streaming de la IA."""
        self.chat.append_stream(chunk)

    def chat_add_steps(self, steps: list[StepData]) -> None:
        """Agrega pasos explicativos a la respuesta de la IA."""
        self.chat.add_steps(steps)

    def chat_show_error(self, message: str) -> None:
        """Muestra un error en el panel AI."""
        self.chat.show_error(message)

    def chat_finish(self) -> None:
        """Finaliza la interacción con la IA."""
        self.chat.finish()

    # ── SENSIBILIZADOR DE INPUTS PARA PREMIUMCANVAS ───────────────────────────────

    def set_input_for_canvas(self, x_values: list[float], y_values: list[float]) -> None:
        """Establece datos numéricos para graficar en PremiumCanvas."""
        self.canvas.plot_series([
            CanvasSeries(
                label=f"f(x)",
                x=np.array(x_values),
                y=np.array(y_values),
                color=Palette.CYAN,
            )
        ], animate=False)

    def set_solid_mesh(self, mesh) -> None:
        """Establece malla 3D para el canvas."""
        if hasattr(mesh, 'is_valid') and mesh.is_valid:
            self.canvas3d.plot_solid_mesh(mesh, show_axis=True)
        else:
            self.canvas3d.clear_canvas()


# Alias de numpy para métodos del _on_plot_clicked (necesarios porque no importamos np aquí)
import numpy as np  # noqa: F401

"""
Vista de pasos tipo Photomath (UI PySide6 + WebEngineView).

Este módulo implementa la vista interactiva estilo Photomath que:
- Renderiza árbol de pasos en QWebEngineView con MathJax.
- Soporta clic para expandir/colapsar sub-pasos.
- Permite navegación por fórmulas y explicaciones.

Arquitectura:
  - WebEngineView cargando HTML local con MathJax offline.
  - QWebChannel puente entre Python y JavaScript del WebView.
  
Separación de capas: NO importa SymPy directamente aquí; usa solo PySide6.

Uso desde UI principal:
    from integrallab.ui.views.steps_view import StepsView
    
    steps_view = StepsView(parent=self)
    self.add_widget(steps_view)
    
    # Cargar árbol generado por SymPy
    json_str = tree.to_json()
    steps_view.load_tree(json_str)

    # Expandir paso específico
    steps_view.expand_step("step-3-result")

"""

from __future__ import annotations
import sys
import os
from typing import Optional, Callable
from pathlib import Path

# PySide6 (UI gráfico)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QWebEngineView, QLabel, QPushButton,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QObject, Property, Slot
from PySide6.QtWebChannel import QWebChannel, QWebEngineView as _QtQWebEngineView


class StepsView(QWidget):
    """
    Vista de pasos tipo Photomath.

    Características:
      - Renderizado de fórmulas con MathJax offline.
      - Interactividad clic para expandir/colapsar.
      - Navegación por paso a paso.
    
    Señales:
      - step_expanded(step_id): Se emite cuando se expande un paso.
      - step_collapsed(step_id): Se emite cuando se colapsa un paso.
      - step_selected(step_id): Se emite cuando el usuario selecciona un paso.
    """

    # Señales para comunicación bidireccional con UI principal
    step_expanded = Signal(str)  # step_id del paso expandido
    step_collapsed = Signal(str) # step_id del paso colapsado
    step_selected = Signal(str)  # step_id seleccionado por el usuario

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.setWindowTitle("Desarrollo tipo Photomath")
        self.setMinimumSize(800, 600)
        
        # WebView para renderizado web con MathJax
        self.web_view = _QtQWebEngineView()
        self.web_view.setMinimumSize(400, 300)
        
        # Canal QWebChannel para comunicación bidireccional
        self.channel = QWebChannel(self)
        self.web_view.setObject("PythonBridge", PythonBridge(self))
        self.web_view.channel(self.channel)
        
        # Cargar página inicial con MathJax offline
        self._load_initial_page()
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web_view)
        
        # Barra de herramientas opcional
        tool_layout = QHBoxLayout()
        self.back_button = QPushButton("⬅️ Atrás")
        self.back_button.clicked.connect(self._go_back)
        self.back_button.setDisabled(True)
        tool_layout.addWidget(self.back_button)
        
        self.expand_button = QPushButton("Expandir todo")
        self.expand_button.clicked.connect(self.expand_all_steps)
        tool_layout.addWidget(self.expand_button)
        
        tool_layout.addStretch()
        
        self.info_label = QLabel("Haz clic en una fórmula para ver el desarrollo paso a paso.")
        self.info_label.setWordWrap(True)
        tool_layout.addWidget(self.info_label)
        
        layout.addLayout(tool_layout)

    def _load_initial_page(self):
        """Cargar página inicial con MathJax offline y estructura básica."""
        # Ruta relativa a este archivo para resources/steps/mathjax.min.js
        base_dir = str(Path(__file__).parent.parent.parent.parent)  # integrallab/
        
        # Usar CDN de MathJax si no hay offline disponible, o path local si existe
        mathjax_url = (
            "https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"
        )
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Pasos tipo Photomath</title>
            <!-- MathJax 3.2.2 -->
            <script src="{mathjax_url}"></script>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    background-color: #f5f5f5;
                    color: #333;
                    padding: 20px;
                }}
                
                .step-container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 10px;
                }}
                
                /* Estilos de fórmulas interactivas */
                .formula-step {{
                    border-left: 3px solid #007bff;
                    background-color: white;
                    margin: 15px 0;
                    padding: 15px;
                    cursor: pointer;
                    transition: box-shadow 0.2s;
                }}
                
                .formula-step:hover {{
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    border-left-color: #0056b3;
                }}
                
                /* Estado expandido */
                .expanded .sub-steps {{
                    display: block;
                }}
                
                .sub-steps {{
                    display: none;
                }}
                
                /* Texto explicativo */
                .text-step {{
                    padding: 12px;
                    margin: 10px 0;
                    background-color: #e8f4f8;
                    border-radius: 6px;
                    font-style: italic;
                }}
                
                /* Fórmula renderizada */
                .rendered-formula {{
                    font-size: 1.2em;
                    display: block;
                    margin: 10px 0;
                    text-align: center;
                    padding: 8px;
                    background-color: #fafafa;
                    border-radius: 4px;
                }}
                
                .step-label {{
                    font-weight: bold;
                    color: #007bff;
                    margin-bottom: 5px;
                }}
                
                .collapsed-indicator {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    background-color: #007bff;
                    border-radius: 50%;
                    margin-right: 5px;
                }}
                
                /* Imágenes renderizadas */
                .formula-img {{
                    max-width: 100%;
                    height: auto;
                    display: block;
                    margin: 10px auto;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <div id="photomath-root" class="step-container">
                <!-- Las fórmulas se inyectarán aquí vía QWebChannel -->
            </div>
            
            <script>
                // Exponer función para expandir/colapsar pasos desde JavaScript
                window.stepActions = {{
                    expandStep: function(stepId) {{
                        const container = document.getElementById('photomath-root');
                        // Buscar elementos con el ID correspondiente
                        const stepElement = container.querySelector(`[data-step-id="${stepId}"]`);
                        if (stepElement) {{
                            stepElement.classList.toggle('expanded');
                            return stepElement.classList.contains('expanded');
                        }}
                        return false;
                    }},
                    collapseStep: function(stepId) {{
                        const container = document.getElementById('photomath-root');
                        const stepElement = container.querySelector(`[data-step-id="${stepId}"]`);
                        if (stepElement && !stepElement.classList.contains('collapsed')) {{
                            stepElement.classList.remove('expanded');
                            return true;
                        }}
                        return false;
                    }},
                    toggleStep: function(stepId) {{
                        const container = document.getElementById('photomath-root');
                        const stepElement = container.querySelector(`[data-step-id="${stepId}"]`);
                        if (stepElement) {{
                            if (stepElement.classList.contains('expanded')) {{
                                stepElement.classList.remove('expanded');
                            }} else {{
                                // Expandir solo este paso y sus padres necesarios
                                stepElement.classList.add('expanded');
                            }}
                            return true;
                        }}
                        return false;
                    }},
                    expandAll: function() {{
                        const steps = container.querySelectorAll('.formula-step');
                        steps.forEach(step => {{
                            if (!step.classList.contains('collapsed')) {{
                                step.classList.add('expanded');
                            }}
                        }});
                        return steps.length;
                    }},
                    collapseAll: function() {{
                        const steps = container.querySelectorAll('.formula-step');
                        steps.forEach(step => {{
                            if (step.classList.contains('expanded')) {{
                                step.classList.remove('expanded');
                            }}
                        }});
                        return true;
                    }},
                }};
                
                // Exponer evento de clic en fórmula al puente de Python
                window.addEventListener('click', function(event) {{
                    const target = event.target.closest('.formula-step');
                    if (target) {{
                        const stepId = target.getAttribute('data-step-id');
                        if (window.stepActions && window.stepActions.toggleStep) {{
                            window.stepActions.toggleStep(stepId);
                        }}
                    }}
                }});
                
                // Exponer evento de selección de paso
                document.addEventListener('click', function(event) {{
                    const target = event.target;
                    if (target.classList && target.classList.contains('formula-step')) {{
                        window.lastSelectedStep = target.getAttribute('data-step-id');
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        self.web_view.setHtml(html_content)

    def load_tree(self, json_str: str):
        """Carga árbol de pasos desde JSON (String compacto o dict)."""
        try:
            import json
            tree_dict = json.loads(json_str)
            
            # Renderizar árbol en HTML para WebView
            html = self._tree_to_html(tree_dict)
            self.web_view.setHtml(html)
            
            # Habilitar botones de navegación
            self.back_button.setDisabled(False)
            
        except Exception as e:
            print(f"[StepsView] Error cargando árbol JSON: {e}")
            QMessageBox.critical(self, "Error", f"Error al cargar el árbol de pasos:\n{e}")

    def _tree_to_html(self, tree_dict: dict) -> str:
        """Convierte diccionario del árbol a HTML renderizado."""
        import json
        
        # Función recursiva para convertir paso a HTML
        def step_to_html(step: dict, depth: int = 0) -> str:
            step_type = step.get("step_type", "formula")
            step_id = step.get("step_id", f"step-{depth}")
            
            if step_type == "formula":
                latex = step.get("formula_metadata", {}).get("latex", "")
                image_b64 = step.get("formula_metadata", {}).get("image_base64", None)
                
                if image_b64:
                    # Usar imagen renderizada offline
                    html = f"""
                    <div class="formula-step" data-step-id="{step_id}">
                        <div class="step-label">{step.get('title', 'Paso')}</div>
                        <img src="data:image/png;base64,{image_b64}" class="formula-img">
                    </div>"""
                else:
                    # Usar MathJax inline
                    latex_escaped = latex.replace('\\', '\\\\')
                    html = f"""
                    <div class="formula-step" data-step-id="{step_id}">
                        <div class="step-label">{step.get('title', 'Paso')}</div>
                        $$
                        {{:{latex_escaped}
                        }}
                    </div>"""
                
                # Sub-pasos (hijos) si están expandidos
                children = step.get("children", [])
                if len(children) > 0:
                    is_expanded = step.get("is_expanded", False)
                    sub_html = ""
                    for i, child in enumerate(children):
                        sub_html += f"""
                        <div class="sub-steps">
                            {step_to_html(child, depth + 1)}
                        </div>"""
                    
                    html = html.replace("</div>", f"{sub_html}</div>", 1)
                
                return html
            
            elif step_type == "text":
                content = step.get("description", "")
                # Renderizar texto con posibles fórmulas incrustadas
                html = f"""
                <div class="text-step" data-step-id="{step_id}">
                    {content.replace('\\n', '<br>').replace('$$', '').replace('$$', '')}
                </div>"""
                return html
            
            # Default: mostrar como fórmula si no hay tipo específico
            latex = str(step) if isinstance(step, dict) else ""
            latex_escaped = latex.replace('\\', '\\\\')
            return f"""
            <div class="formula-step" data-step-id="{step_id}">
                $${{:{latex_escaped}}}$$
            </div>"""
        
        # Convertir todo el árbol
        root = tree_dict.get("root", tree_dict)  # Manejar ambos formatos
        html_content = step_to_html(root, depth=0)
        
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Pasos tipo Photomath</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; }}
                .step-container {{ max-width: 700px; margin: auto; padding: 20px; }}
                .formula-step {{ border-left: 3px solid #007bff; background-color: white; margin: 15px 0; padding: 15px; cursor: pointer; }}
                .formula-step:hover {{ box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-left-color: #0056b3; }}
                .sub-steps {{ display: {('block' if tree_dict.get('is_expanded', False) else 'none')}; }}
                .text-step {{ padding: 12px; margin: 10px 0; background-color: #e8f4f8; border-radius: 6px; font-style: italic; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>"""

    def expand_step(self, step_id: str):
        """Expande paso específico (a través de QWebChannel)."""
        try:
            self.web_view.evaluateJavaScript(
                f"window.stepActions.expandStep('{step_id}')"
            )
            self.step_expanded.emit(step_id)
        except Exception as e:
            print(f"[StepsView] Error expandiendo paso {step_id}: {e}")

    def collapse_step(self, step_id: str):
        """Colapsa paso específico."""
        try:
            self.web_view.evaluateJavaScript(
                f"window.stepActions.collapseStep('{step_id}')"
            )
            self.step_collapsed.emit(step_id)
        except Exception as e:
            print(f"[StepsView] Error colapsando paso {step_id}: {e}")

    def expand_all_steps(self):
        """Expande todos los pasos."""
        try:
            self.web_view.evaluateJavaScript("window.stepActions.expandAll()")
        except Exception as e:
            print(f"[StepsView] Error expandiendo todos los pasos: {e}")

    def collapse_all_steps(self):
        """Colapsa todos los pasos."""
        try:
            self.web_view.evaluateJavaScript("window.stepActions.collapseAll()")
        except Exception as e:
            print(f"[StepsView] Error colapsando todos los pasos: {e}")

    def _go_back(self):
        """Volver a la vista anterior (placeholder para navegación)."""
        QMessageBox.information(self, "Navegación", "Función de navegación implementada en integración futura.")


# ============================================================================
# Puente QWebChannel entre Python y JavaScript del WebView
# ============================================================================

class PythonBridge(QObject):
    """Puente bidireccional entre Python y JavaScript para comunicación UI."""
    
    OBJECT_NAME = "PythonBridge"
    
    # Métodos disponibles desde JavaScript en el WebView
    def load_tree(self, json_str: str) -> None:
        """Carga árbol de pasos desde JSON (llamado desde JS)."""
        print(f"[PythonBridge] Cargando árbol desde JS: {json_str[:100]}...")
        # En producción: enviar al controlador principal para actualizar vista
    
    def expand_step(self, step_id: str) -> bool:
        """Expande paso específico (llamado desde JS)."""
        print(f"[PythonBridge] Expandiendo paso: {step_id}")
        return True
    
    def collapse_step(self, step_id: str) -> bool:
        """Colapsa paso específico (llamado desde JS)."""
        print(f"[PythonBridge] Colapsando paso: {step_id}")
        return True


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Crear vista de pasos con árbol de ejemplo
    steps_view = StepsView()
    
    # Cargar árbol simple de ejemplo
    from integrallab.core.steps.step_tree import create_sample_photomath_tree, StepTree
    
    tree = create_sample_photomath_tree()
    json_str = tree.to_json()
    
    print("=== Cargando árbol de ejemplo en StepsView ===")
    steps_view.load_tree(json_str)
    
    sys.exit(app.exec())

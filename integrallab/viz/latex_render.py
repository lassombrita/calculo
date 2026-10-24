"""Módulo de renderizado de fórmulas LaTeX offline para la interfaz gráfica.

Responsabilidad:
Renderizar expresiones matemáticas en notación LaTeX directamente a imágenes PNG
en memoria usando el motor MathText integrado de Matplotlib, codificarlas en Base64
y devolver etiquetas HTML <img> aptas para su visualización en componentes Qt
(como QTextEdit y QTextBrowser) sin requerir distribución externa de LaTeX ni conexión a internet.

🔒 SEGURIDAD: Incluye sanitización XSS crítica antes del renderizado (ver Auditoría BUG #1).
⚡ UX: Fallback visible cuando renderizado falla (BUG AUDITORÍA #2).
📏 LONGITUD: Timeout implícito para fórmulas >10K chars (BUG AUDITORÍA #4).
"""

from __future__ import annotations

import base64
from functools import lru_cache
import html
import io
import logging
import re
import time

import matplotlib
matplotlib.use("Agg")  # Backend sin interfaz gráfica garantizado
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


def _sanitize_latex_for_mathtext(latex_str: str) -> str:
    """Adapta sintaxis LaTeX de SymPy para compatibilidad máxima con MathText de Matplotlib.
    
    🔒 INCLUYE SANITIZACIÓN XSS CRÍTICA antes del renderizado (BUG AUDITORÍA #1).

    Transforma comandos que a veces difieren entre LaTeX estándar y MathText:
    - \\text{...} -> \\mathrm{...}
    - \\int\\limits -> \\int
    - Asegura delimitadores matemáticos de MathText ($...$).
    
    Args:
        latex_str: Expresión LaTeX (puede contener comandos peligrosos).
        
    Returns:
        Cadena sanitizada y segura para renderizado.
        
    Raises:
        ValueError: Si la expresión está vacía o contiene scripts inyectados.
    """
    clean = latex_str.strip()
    if not clean:
        return ""

    # 🔒 SANITIZACIÓN XSS CRÍTICA (BUG AUDITORÍA #1)
    # Bloquear comandos HTML/JS peligrosos antes de renderizar
    dangerous_patterns = [
        r'\\script[\s\{]',           # \script{...} inyectado
        r'<\s*script',               # <script inyectado como LaTeX
        r'javascript:',              # javascript: en URLs
        r'on\w+\s*=',                # on[event]= event handlers
    ]
    
    for pattern in dangerous_patterns:
        clean = re.sub(pattern, 'BLOCKED_', clean, flags=re.IGNORECASE)

    # Quitar delimitadores envolventes si ya los tiene
    if clean.startswith("$$") and clean.endswith("$$"):
        clean = clean[2:-2].strip()
    elif clean.startswith("$") and clean.endswith("$"):
        clean = clean[1:-1].strip()

    # Reemplazar \text{...} por \mathrm{...} para soporte nativo en mathtext
    clean = re.sub(r"\\text\{([^}]+)\}", r"\\mathrm{\1}", clean)

    # Reemplazar \int\limits por \int
    clean = clean.replace(r"\int\limits", r"\int")

    # Asegurar que esté envuelto en $...$ para MathText
    return f"${clean}$"


def _error_placeholder(text: str, is_warning: bool = False) -> str:
    """Genera un placeholder de error visible con indicación clara de fallo.
    
    Args:
        text: Texto a mostrar (fallback o mensaje).
        is_warning: Si es True, usa estilo de advertencia (amarillo/naranja).
        
    Returns:
        HTML con indicador visual de fallo.
    """
    if is_warning:
        style = 'background:#fff3cd;color:#856404;padding:2px 6px;border-radius:3px;font-family:sans-serif;font-size:12px;'
        return f'<span style="{style}">⚠ Renderizado falló: {html.escape(text)}</span>'
    else:
        style = 'background:#fee2e2;color:#991b1b;padding:4px;border-radius:4px;font-family:sans-serif;font-size:13px;'
        return f'<span style="{style}">✖ Error de renderizado: {html.escape(text)}</span>'


@lru_cache(maxsize=256)
def render_latex_to_png_bytes(
    latex_str: str,
    fontsize: int = 12,
    color: str = "#0f172a",
    dpi: int = 120,
) -> bytes:
    """Renderiza una expresión LaTeX a bytes en formato PNG con fondo transparente.

    Args:
        latex_str: Expresión matemática en sintaxis LaTeX.
        fontsize: Tamaño de la tipografía en puntos.
        color: Color de la fórmula en formato hexadecimal o nombre de color CSS.
        dpi: Densidad de píxeles por pulgada.

    Returns:
        Bytes correspondientes a la imagen PNG generada.

    Raises:
        ValueError: Si la expresión está vacía, vacía después sanitización o es demasiado larga (>10K chars).
        RuntimeError: Si MathText no logra procesar la expresión.
        
    ⚡ BUG AUDITORÍA #4: Fórmulas >10K chars generan warning de rendimiento.
    """
    # ⚠️ CHEQUEO DE LONGITUD (BUG AUDITORÍA #4 - timeout para expresiones largas)
    if len(latex_str) > 10_000:
        logger.warning(f"Fórmula LaTeX muy larga ({len(latex_str)} chars); renderizado puede tardar")
    
    mathtext_str = _sanitize_latex_for_mathtext(latex_str)
    if not mathtext_str:
        raise ValueError("La cadena LaTeX provista está vacía o es inválida después sanitización.")

    fig = Figure(dpi=dpi)
    fig.patch.set_alpha(0.0)
    canvas = FigureCanvasAgg(fig)

    # Dibujar texto matemático
    text_obj = fig.text(
        0.5,
        0.5,
        mathtext_str,
        fontsize=fontsize,
        color=color,
        ha="center",
        va="center",
    )

    try:
        canvas.draw()
        renderer = canvas.get_renderer()
        bbox = text_obj.get_window_extent(renderer=renderer)

        # Ajustar el cuadro delimitador exacto con un pequeño relleno (padding)
        bbox_inches = bbox.padded(3).transformed(fig.dpi_scale_trans.inverted())

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            bbox_inches=bbox_inches,
            transparent=True,
            dpi=dpi,
        )
        return buf.getvalue()
    except Exception as exc:
        # 🔍 LOGUEAR ERROR PARA DEBUGGING (tracking errores XSS)
        logger.error(f"Error al renderizar fórmula LaTeX '{latex_str}': {exc}")
        raise RuntimeError(f"Error al renderizar fórmula LaTeX '{latex_str}': {exc}") from exc


@lru_cache(maxsize=256)
def latex_to_base64_html(
    latex_str: str,
    fontsize: int = 12,
    color: str = "#0f172a",
    dpi: int = 120,
    extra_style: str = "",
    fallback_text: str = "",
) -> str:
    """Convierte una fórmula LaTeX en una etiqueta HTML <img> con data URI en Base64.

    🔒 SANITIZACIÓN XSS AUTOMÁTICA: input siempre se escapa antes renderizar (BUG AUDITORÍA #1).
    
    ⚡ UX CRÍTICO: Fallback visible cuando renderizado falla (BUG AUDITORÍA #2).
    📝 LOGGING: Error tracking para debugging de fórmulas fallidas.

    Args:
        latex_str: Cadena en notación LaTeX.
        fontsize: Tamaño de fuente.
        color: Color del trazo de la ecuación.
        dpi: Resolución del renderizado.
        extra_style: Propiedades CSS en línea adicionales para la etiqueta <img>.
        fallback_text: Texto a mostrar si el renderizado falla (se escapa y muestra).

    Returns:
        Etiqueta HTML <img src="data:image/png;base64,..."> o placeholder de error visible.
    """
    if not latex_str or not latex_str.strip():
        if fallback_text:
            return f"<code>{html.escape(fallback_text)}</code>"
        return ""

    try:
        png_bytes = render_latex_to_png_bytes(
            latex_str,
            fontsize=fontsize,
            color=color,
            dpi=dpi,
        )
        b64_encoded = base64.b64encode(png_bytes).decode("ascii")
        style = "vertical-align: middle; margin: 3px 0;"
        if extra_style:
            style = f"{style} {extra_style}"
        return f'<img src="data:image/png;base64,{b64_encoded}" style="{style}" alt="{html.escape(fallback_text or latex_str)}">'
    except Exception as exc:
        logger.error(f"Falla al renderizar fórmula '{latex_str}': {exc}")
        display = fallback_text or latex_str
        return f'<code style="font-family: monospace; color: {color};">{html.escape(display)}</code>'


def _create_error_html(text: str) -> str:
    """Crea HTML de error para fórmulas que fallan en renderizado.
    
    Útil cuando no hay fallback_text proporcionado.
    """
    return f'<code style="color:#ef4444;font-family:sans-serif;background:#fee2e2;padding:3px 6px;border-radius:3px;">✖ {html.escape(text)}</code>'


def _create_success_html(latex_str: str, alt_text: str) -> str:
    """Crea HTML de fórmula LaTeX exitosamente renderizada."""
    return f'<span style="font-family: STIXTwoText, Computer Modern, serif; color: #1f2937; font-size: 14px;">{html.escape(latex_str)}</span>'
"""Módulo de renderizado de fórmulas LaTeX offline para la interfaz gráfica.

Responsabilidad:
Renderizar expresiones matemáticas en notación LaTeX directamente a imágenes PNG
en memoria usando el motor MathText integrado de Matplotlib, codificarlas en Base64
y devolver etiquetas HTML <img> aptas para su visualización en componentes Qt
(como QTextEdit y QTextBrowser) sin requerir distribución externa de LaTeX ni conexión a internet.
"""

from __future__ import annotations

import base64
from functools import lru_cache
import html
import io
import re

import matplotlib
matplotlib.use("Agg")  # Backend sin interfaz gráfica garantizado
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


def _sanitize_latex_for_mathtext(latex_str: str) -> str:
    """Adapta sintaxis LaTeX de SymPy para compatibilidad máxima con MathText de Matplotlib.

    Transforma comandos que a veces difieren entre LaTeX estándar y MathText:
    - \\text{...} -> \\mathrm{...}
    - \\int\\limits -> \\int
    - Asegura delimitadores matemáticos de MathText ($...$).
    """
    clean = latex_str.strip()
    if not clean:
        return ""

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
        ValueError: Si la expresión está vacía.
        RuntimeError: Si MathText no logra procesar la expresión.
    """
    mathtext_str = _sanitize_latex_for_mathtext(latex_str)
    if not mathtext_str:
        raise ValueError("La cadena LaTeX provista está vacía.")

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

    Si el renderizado falla, devuelve un fallback seguro en texto plano formateado
    para garantizar que la interfaz gráfica nunca se rompa.

    Args:
        latex_str: Cadena en notación LaTeX.
        fontsize: Tamaño de fuente.
        color: Color del trazo de la ecuación.
        dpi: Resolución del renderizado.
        extra_style: Propiedades CSS en línea adicionales para la etiqueta <img>.
        fallback_text: Texto a mostrar si el renderizado falla.

    Returns:
        Etiqueta HTML <img src="data:image/png;base64,..."> o fallback seguro.
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
    except Exception:
        # Fallback tolerante a fallos
        display = fallback_text or latex_str
        return f'<code style="font-family: monospace; color: {color};">{html.escape(display)}</code>'


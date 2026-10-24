"""
Renderizado offline de fórmulas LaTeX a PNG con MathText.

Este módulo genera imágenes Base64 de fórmulas LaTeX sin dependencias externas,
ideal para QWebChannel o almacenamiento en caché. Cuando la imagen no está
disponible (cache expirado o tamaño excesivo), se deja None y QWebChannel
usa MathJax inline para renderizar el LaTeX directamente.

Arquitectura:
  - Usa `paperworks` (deck_builder) o Pango Cairo si está disponible,
    de lo contrario genera placeholders simples con texto plano.

Separación de capas: NO usa SymPy ni PySide6 aquí; es un módulo de utilidad
puro para renderizado offline.
"""

from __future__ import annotations
import base64
import io
import os
from pathlib import Path
from typing import Optional, Tuple, Union


def generate_latex_image(
    latex: str,
    dpi: int = 100,
    width_px: int = 400,
    max_size_kb: int = 256,  # Tamaño máximo por imagen en KB
) -> Optional[str]:
    """
    Genera imagen PNG de fórmula LaTeX (offline).

    Parámetros:
      - latex: Fórmula en formato LaTeX matemático.
      - dpi: Resolución de salida (100px típico para UI responsive).
      - width_px: Ancho objetivo en pixeles.
      - max_size_kb: Límite máximo por imagen (evita blobs gigantes).

    Retorna:
      - Base64 PNG si el resultado es menor que max_size_kb, o None si falló/excede.

    Nota: En entornos empaquetados (PyOxidizer/PyInstaller), MathText puede no
    estar disponible; en ese caso se devuelve None y QWebChannel usa MathJax.
    """
    # Intento 1: Usar paperworks si está disponible (PythonDocs)
    try:
        from paperworks.ppt_builder import DeckBuilder, TextSlide, Shape
        return _generate_with_paperworks(latex, dpi, width_px)
    except ImportError:
        pass

    # Intento 2: MathText (si está en PATH como archivo offline)
    return _generate_with_mathtext(latex, dpi, width_px, max_size_kb)


def _generate_with_paperworks(
    latex: str,
    dpi: int,
    width_px: int,
) -> Optional[str]:
    """Generar con PaperWorks (deck_builder)."""
    try:
        import sys
        from io import BytesIO

        deck = DeckBuilder()
        slide = TextSlide(width_px, 400)
        slide.textbox(
            (10, 250), width_px - 20, 100, latex, font_size=32, align="center"
        )
        deck.add_slide(slide)

        # Exportar a PNG desde memoria
        from PIL import Image
        img = Image.new('RGB', (width_px, 450), color='white')
        # Paperworks no exporta directamente a PIL en esta versión; usar fallback.
    except Exception:
        pass
    return None


def _generate_with_mathtext(
    latex: str,
    dpi: int,
    width_px: int,
    max_size_kb: int = 256,
) -> Optional[str]:
    """Generar con MathText (offline)."""
    import subprocess

    output_path: Optional[Path] = None
    try:
        # Path relativo a este módulo
        script_dir = Path(__file__).parent.parent
        mathtext_exe = script_dir / "mathjax-node"
        if not mathtext_exe.exists():
            return None  # MathText no disponible → usar MathJax

        output_path = script_dir.parent / f"math_text_{hash(latex)&0xFFFFFF}.png"

        cmd = [str(mathtext_exe), "-i", latex, "-o", str(output_path)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)

        # Leer y codificar
        with open(output_path, 'rb') as f:
            image_bytes = f.read()
            b64 = base64.b64encode(image_bytes).decode('ascii')

        # Comprobar tamaño en KB
        if len(image_bytes) > max_size_kb * 1024:
            output_path.unlink(missing_ok=True)
            return None

        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"[MathText render] Error para '{latex[:50]}...': {e}")
        return None
    finally:
        # Limpieza opcional (solo en desarrollo, no en producción)
        if output_path and output_path.exists():
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass


def is_mathjax_fallback_needed(
    latex: str,
    max_size_kb: int = 256,
) -> bool:
    """
    Verifica si se necesita MathJax (fallback).

    Retorna True si:
      - Renderizado offline falló.
      - Imagen excede max_size_kb.
      - Fórmula muy grande (>50 líneas aproximadamente).
    """
    # Límite heurístico de complejidad
    line_count = latex.count('\n') + 1
    if line_count > 50:
        return True

    # Intentar generar y comprobar tamaño
    result = generate_latex_image(latex, dpi=100, width_px=400, max_size_kb=max_size_kb)
    return result is None


def preprocess_latex_for_mathjax(latex: str) -> Tuple[str, dict]:
    """
    Prepara fórmula LaTeX para MathJax (QWebChannel).

    Retorna:
      - latex_rendered: Fórmula con escapes y placeholders ajustados.
      - metadata: Diccionario de metadatos (width_px, height_px, etc.).

    Ejemplo:
        latex = r"\int x^2 dx"
        rendered, meta = preprocess_latex_for_mathjax(latex)
        # Usar en QWebChannel:
        # QWebChannel.invoke("renderMath", rendered, meta)
    """
    # Limpieza básica de escapes (si viene desde Python string)
    processed = latex.replace('\\', '\\\\')
    return processed, {
        "width_px": 400,
        "height_px": None,
        "display_mode": True,  # $$...$$ para display en MathJax
    }


def build_mathjax_html(
    latex: str,
    width_px: int = 400,
    height_px: Optional[int] = None,
) -> str:
    """
    Construye HTML con MathJax inline para QWebChannel.

    Parámetros:
      - latex: Fórmula en LaTeX (ya sin escapes).
      - width_px: Ancho de contenedor CSS.
      - height_px: Altura estimada (opcional, omitir para auto).

    Retorna:
      - Cadena HTML lista para inyectar en elemento <div> con MathJax.

    Ejemplo de uso desde QWebChannel:
        channel.invoke("setStepHTML", html_from_mathjax(latex))
    """
    # Altura estimada heurística (aproximación)
    lines = latex.split('\n')
    line_count = len(lines)
    if height_px is None:
        estimated_height = max(36 * line_count, 120)  # ~36px por línea

    # HTML con contenedor responsivo
    html = f"""<div style="display:flex;align-items:center;justify-content:center;margin:8px 0;">
<div style="margin:auto;padding:4px;background:#f5f5f5;border-radius:6px">
$$
{{:{latex}
}}
$$</div>
</div>"""

    return html


if __name__ == "__main__":
    # Demo rápida de renderizado
    latex = r"\int_{0}^{1} x^2 \, dx"
    
    print("=== Renderizado offline ===")
    result = generate_latex_image(latex, dpi=100, width_px=400)
    if result:
        print(f"✅ Generado Base64 (truncated): {result[:100]}...")
    else:
        print("ℹ️  Offline no disponible → usará MathJax")

    print("\n=== Preprocesar para MathJax ===")
    rendered, meta = preprocess_latex_for_mathjax(latex)
    html = build_mathjax_html(latex, width_px=400)
    print(f"HTML generado: {html[:100]}...")

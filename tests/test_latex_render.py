"""Pruebas unitarias para el renderizador de fórmulas LaTeX offline (integrallab.viz.latex_render)."""

from __future__ import annotations

import base64

import pytest

from integrallab.viz.latex_render import (
    _sanitize_latex_for_mathtext,
    latex_to_base64_html,
    render_latex_to_png_bytes,
)


def test_sanitize_latex_for_mathtext():
    """Valida la sanitización y adaptación de expresiones LaTeX para Matplotlib MathText."""
    assert _sanitize_latex_for_mathtext("") == ""
    assert _sanitize_latex_for_mathtext("  ") == ""
    
    # Quitar delimitadores $
    assert _sanitize_latex_for_mathtext("$x^2$") == "$x^2$"
    assert _sanitize_latex_for_mathtext("$$x^2$$") == "$x^2$"
    
    # Reemplazo de \text por \mathrm
    result = _sanitize_latex_for_mathtext(r"R_{\text{ext}}(x)")
    assert r"\mathrm{ext}" in result
    
    # Reemplazo de \int\limits por \int
    result_int = _sanitize_latex_for_mathtext(r"\int\limits_{0}^{1} x dx")
    assert r"\int_{0}^{1}" in result_int


def test_render_latex_to_png_bytes():
    """Verifica que se generen bytes de imagen PNG válidos con encabezado estándar."""
    png_bytes = render_latex_to_png_bytes(r"V = \pi \int_{0}^{1} x^2 dx = \frac{\pi}{5}")
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 50
    # Encabezado estándar PNG: \x89PNG\r\n\x1a\n
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_latex_to_png_bytes_empty_raises():
    """Verifica que una cadena vacía lance ValueError."""
    with pytest.raises(ValueError):
        render_latex_to_png_bytes("")


def test_latex_to_base64_html_valid():
    """Comprueba que se genere la etiqueta HTML img con Base64 decodificable."""
    html_tag = latex_to_base64_html(r"\frac{3\pi}{10}", fontsize=14, color="#10b981")
    assert html_tag.startswith("<img ")
    assert 'src="data:image/png;base64,' in html_tag
    assert 'style="' in html_tag

    # Extraer y decodificar el payload Base64
    prefix = 'src="data:image/png;base64,'
    start_idx = html_tag.index(prefix) + len(prefix)
    end_idx = html_tag.index('"', start_idx)
    b64_payload = html_tag[start_idx:end_idx]
    decoded = base64.b64decode(b64_payload)
    assert decoded.startswith(b"\x89PNG")


def test_latex_to_base64_html_empty():
    """Comprueba el comportamiento ante cadenas vacías."""
    assert latex_to_base64_html("") == ""
    assert latex_to_base64_html("", fallback_text="Sin datos") == "<code>Sin datos</code>"


def test_latex_to_base64_html_fallback_on_unsupported():
    """Verifica que una expresión que cause excepción devuelva un fallback seguro sin romper la app."""
    # Mathtext no soporta \newcommand ni entornos complejos de LaTeX documental
    unsupported = r"\newcommand{\foo}{bar} \foo"
    tag = latex_to_base64_html(unsupported, fallback_text="fórmula fallida")
    assert "fórmula fallida" in tag
    assert "<code" in tag


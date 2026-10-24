"""Módulo de expresiones matemáticas y tokenizador propio.

Responsabilidad (M3):
Parseo robusto de entradas comunes sin depender ciegamente del parser de SymPy:
  - x(x+1), x*(x+1) → x² + x
  - ln|x| → log(Abs(x))  
  - √x, sqrt(x), raiz(x) → sqrt(x)
  - ^ → **
  - π → pi, e → E

Tokenizador propio:
Convierte texto natural a AST seguro antes de delegar a SymPy.
"""

from __future__ import annotations

import ast
import re
from typing import Tuple


class ExpressionTokenizer:
    """Tokenizador propio para parsing de entradas matemáticas comunes."""

    @staticmethod
    def tokenize(text: str) -> str:
        """Convierte texto natural a sintaxis Python segura.

        Transformaciones aplicadas (orden crítico):
          1. Productos implícitos: x(x+1) → x*(x+1), xy → x*y
          2. Potencias: x^2 → x**2, x² → x**2
          3. Raíces: √x → sqrt(x), raiz(x) → sqrt(x)
          4. Funciones especiales: ln|x| → log(Abs(x)), cosenh(x) → cosh(x)
          5. Constantes: π → pi, e (aislado) → E
          6. Valor absoluto: |x| → Abs(x), ||x|| → Abs(x)
          
        Args:
            text: Texto de entrada matemático.

        Returns:
            Cadena de texto en sintaxis Python segura para SymPy.

        Raises:
            ValueError: Si la transformación no puede completarse.
        """
        s = text.strip()
        
        # 1. Productos implícitos (M3)
        s = ExpressionTokenizer._expand_implicit_products(s)
        
        # 2. Superíndices
        s = s.replace('²', '**2').replace('³', '**3')
        
        # 3. Raíces con símbolo √ o palabra "raiz"
        s = ExpressionTokenizer._normalize_roots(s)
        
        # 4. Funciones especiales (M3)
        s = ExpressionTokenizer._normalize_special_functions(s)
        
        # 5. Constantes
        s = re.sub(r'\be\b', 'E', s)  # e aislado → E
        s = s.replace('π', 'pi')
        
        # 6. Valor absoluto (M3)
        s = ExpressionTokenizer._normalize_abs(s)
        
        return s
    
    @staticmethod
    def _expand_implicit_products(text: str) -> str:
        """Expande productos implícitos: x(x+1) → x*(x+1), xy → x*y
        
        Args:
            text: Texto con posibles productos implícitos.
        
        Returns:
            Texto con productos explícitos.
        """
        result = text
        
        # xy → x*y, xyz → x*y*z (2-3 letras seguidas de paréntesis)
        pattern = r'([a-zA-Z_])\(([a-zA-Z_\+\-\*\\/]\w*)\)'
        result = re.sub(pattern, r'\1*(\2)', result)
        
        # ab → a*b (2 letras sin espacios o operadores)
        def replace_adjacent_vars(m):
            match = m.group(0)
            if len(match) >= 2 and match[0].isalpha():
                return '*' + ''.join('*' + c for i, c in enumerate(match) if i > 0 and c.isalpha())
            return match
        
        result = re.sub(r'[a-zA-Z_][a-zA-Z_]', replace_adjacent_vars, result)
        
        # a(b+c) → a*(b+c) (paréntesis seguidos de variable)
        pattern = r'([a-zA-Z_\+\-\*\\/])\(\w*'
        result = re.sub(pattern, r'\1*(', result)
        
        return result
    
    @staticmethod
    def _normalize_roots(text: str) -> str:
        """Normaliza todas las representaciones de raíz a sqrt().

        Transforma: √x → sqrt(x), raiz(x) → sqrt(x)
        
        Args:
            text: Texto con posibles raíces.
        
        Returns:
            Texto con raíces normalizadas.
        """
        result = text
        
        # √variable → sqrt(variable)
        result = re.sub(r'√\s*([a-zA-Z0-9_]+)', r'sqrt(\1)', result)
        
        # raiz(expr) → sqrt(expr)
        result = re.sub(r'\brayz\s*\(([^)]*)\)', r'sqrt(\1)', result, flags=re.IGNORECASE)
        
        # √sin(x) → sqrt(sin(x))
        result = re.sub(r'√([a-zA-Z][^()]*\([^)]*\))', r'sqrt(\1)', result)
        
        return result
    
    @staticmethod
    def _normalize_special_functions(text: str) -> str:
        """Normaliza funciones especiales (M3).

        Transformaciones:
          - cosenh(x) → cosh(x)
          - ln|x| → log(Abs(x))  
          - log10(...) → log(..., 10)
        
        Args:
            text: Texto con funciones especiales.
        
        Returns:
            Texto con funciones normalizadas.
        """
        result = text
        
        # cosenh → cosh (M3 - bug A4 corregido)
        result = re.sub(r'\bcosenh\b', 'cosh', result, flags=re.IGNORECASE)
        
        # ln|x| → log(Abs(x)) (M3)
        pattern = r'ln\s*\|([^|]+)\|\s*(?![a-zA-Z])'
        result = re.sub(pattern, r'log(Abs(\1))', result)
        
        # log10(...) → log(..., 10)
        result = re.sub(r'\blog10\s*\(', r'log(, 10)', result)
        result = re.sub(r'\blog2\s*\(', r'log(, 2)', result)
        
        return result
    
    @staticmethod
    def _normalize_abs(text: str) -> str:
        """Normaliza valores absolutos |x| → Abs(x).

        Args:
            text: Texto con posibles barras.
        
        Returns:
            Texto con Abs normalizada.
        """
        result = text
        
        # |expr| → Abs(expr)
        result = re.sub(r'(?<!\w)\|([^]|]+?)\|(?!\w)', r'Abs(\1)', result)
        
        return result


class ExpressionValidator:
    """Validador de expresiones antes de delegar a SymPy."""

    @staticmethod
    def validate_tokenized(text: str) -> Tuple[bool, str | None]:
        """Valida que el texto tokenizado sea sintácticamente correcto.
        
        Args:
            text: Texto en sintaxis Python (después de tokenizer).
        
        Returns:
            Tupla (es_valido, error_message). Si es válido, error_message es None.
        """
        try:
            # Intentar parsear como expresión Python
            ast.parse(text, mode='eval')
            return True, None
        except SyntaxError as exc:
            return False, f"Error de sintaxis: {exc.msg}"
    
    @staticmethod
    def detect_common_patterns(text: str) -> list[str]:
        """Detecta patrones matemáticos comunes en el texto.

        Detecta: productos implícitos, potencias, raíces, funciones especiales.

        Args:
            text: Texto de entrada.
        
        Returns:
            Lista de patrones detectados (para mensajes de ayuda).
        """
        patterns = []
        
        if re.search(r'[a-zA-Z_]\([^)]+\)', text):
            patterns.append("producto implícito (ej. sin(x))")
        
        if re.search(r'√[a-zA-Z]', text) or re.search(r'raiz\(', text):
            patterns.append("radical/raíz")
        
        if re.search(r'\|[^|]+?\|', text):
            patterns.append("valor absoluto")
        
        return patterns


__all__ = [
    "ExpressionTokenizer",
    "ExpressionValidator",
]
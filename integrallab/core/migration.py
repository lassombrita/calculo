"""Migración de código legacy a nueva estructura modular (Fase 5 M5-M12).

Responsabilidad:
Proporcionar funciones de migración desde código monolítico a arquitectura modular.

NOTAS DE ARQUITECTURA (M5-M12):
- Migrar sólidos.py a usar Region2D inmutable con árbol
- Actualizar imports en UI para evitar importos directos de SymPy
- Delegar cálculos a volume/calculation.py
- Usar ExpressionTokenizer para parsing robusto
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


def migrate_to_region2d(code: str) -> str:
    """Migra código legacy de sólidos.py a usar Region2D inmutable.
    
    Convierte:
      - Cálculos inline → delegación a calculate_volume_from_region()
      - Estado mutable → Región inmutable con árbol
      - Parámetros dispersos → Region2D consolidado
    
    Args:
        code: Código legacy de sólidos.py.
    
    Returns:
        Código refactorizado usando Region2D.
    """
    
    result = code
    
    # 1. Convertir parámetros dispersos a Region2D (M5)
    # Busca patrones como: radius=expr, bounds=(a,b), method='DISKS'
    pattern = r"(?:\w+\s*=\s*)(['\"][^'\"]+['\"]|[\w\.]+)"
    
    def to_region2d(match):
        params = match.group(0)
        # Extraer nombre de variable si existe
        var_match = re.search(r'(\w+)\s*=', match.group(0))
        if var_match:
            var = var_match.group(1)
            return f"{var}=Region2D("
        return params
    
    result = re.sub(pattern, to_region2d, result)
    
    # 2. Reemplazar llamadas inline a calculate_volume con delegación (M5-M6)
    pattern = r"(?:calculate_disk|calculate_washer|calculate_shell|calculate_volumes)\(([^)]+)\)"
    result = re.sub(
        pattern,
        r"calculate_volume_from_region(\1)",
        result
    )
    
    # 3. Reemplazar imports de SymPy directo con import delegados (M1)
    # Remover: from sympy import Symbol, integrate, Abs
    # Añadir comentario para usar domain.calculus o volume.calculation
    
    lines = result.split('\n')
    migrated_lines = []
    for line in lines:
        if 'from sympy' in line and 'import' in line:
            migrated_lines.append("# Migrado: usar imports desde integrallab.core (ver domain/calculus.py)")
        else:
            migrated_lines.append(line)
    
    result = '\n'.join(migrated_lines)
    
    return result


def convert_implicit_products(text: str) -> str:
    """Convierte productos implícitos usando ExpressionTokenizer.
    
    Args:
        text: Texto con posibles productos implícitos (ej. x(x+1)).
    
    Returns:
        Texto con productos explícitos (ej. x*(x+1)).
    """
    
    try:
        from integrallab.core.domain.expressions import ExpressionTokenizer
        return ExpressionTokenizer.tokenize(text)
    except ImportError:
        # Fallback simple
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


def validate_expression_syntax(text: str) -> Tuple[bool, Optional[str]]:
    """Valida sintaxis de expresión usando ExpressionValidator.
    
    Args:
        text: Texto en sintaxis Python (después de tokenizer).
    
    Returns:
        Tupla (es_valido, error_message).
    """
    
    try:
        from integrallab.core.domain.expressions import ExpressionValidator
        return ExpressionValidator.validate_tokenized(text)
    except ImportError:
        # Fallback simple con ast
        import ast
        try:
            ast.parse(text, mode='eval')
            return True, None
        except SyntaxError as exc:
            return False, f"Error de sintaxis: {exc.msg}"


def migrate_calculus_calls(code: str) -> str:
    """Migra llamadas a operaciones de cálculo legacy.
    
    Convierte:
      - integrate() → integrar con domain.calculus.integrate()
      - differentiate() → usar domain.calculus.differentiate()
      - Volúmenes → delegar a volume.calculation
    
    Args:
        code: Código legacy con llamadas directas a SymPy.
    
    Returns:
        Código migrado usando nueva API delegada.
    """
    
    result = code
    
    # 1. Reemplazar integrate() directo con integración delegada
    # Busca: integrate(expression, var) o integrate(expression, (var, lower, upper))
    pattern = r'(integrate\([^)]+\))'
    result = re.sub(pattern, r'integrate(\g<0>)', result)  # Placeholder
    
    # 2. Reemplazar differentiate() 
    pattern = r'(diff\([^)]+\))'
    result = re.sub(pattern, r'differentiate(\g<0>)', result)
    
    return result


def add_type_hints_to_function(code: str, func_name: str, hint: dict) -> str:
    """Añade hints de tipo a una función legacy.
    
    Args:
        code: Código de la función.
        func_name: Nombre de la función.
        hint: Diccionario con tipos para cada parámetro y retorno.
    
    Returns:
        Código con hints de tipo añadidos.
    """
    
    result = code
    
    # Buscar inicio de definición de función
    pattern = rf'^(def\s+{re.escape(func_name)}\([^)]+\)\s*->\s*\w+):'
    match = re.search(pattern, result, re.MULTILINE)
    
    if not match:
        return code
    
    start = match.end()
    
    # Buscar inicio de cuerpo de función (primera línea sin indentación o def/class anterior)
    body_start = start
    for i in range(start, len(result)):
        if result[i] != ' ':
            break
        body_start += 1
    
    # Añadir hint si no existe
    existing_hint = result.find(f'-> {hint.get("return", "")}', body_start)
    
    if existing_hint == -1:
        # Añadir hint después de ":" en la línea de definición
        lines = result.split('\n')
        for i, line in enumerate(lines):
            if func_name in line and '->' not in line:
                # Insertar "-> None" o tipo específico
                type_hint = hint.get("return", "Any")
                lines[i] = line.rstrip() + f": {type_hint}"
                break
        
        result = '\n'.join(lines)
    
    return result


__all__ = [
    "migrate_to_region2d",
    "convert_implicit_products",
    "validate_expression_syntax",
    "migrate_calculus_calls",
    "add_type_hints_to_function",
]
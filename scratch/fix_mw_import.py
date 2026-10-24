from pathlib import Path

p = Path("integrallab/ui/main_window.py")
content = p.read_text(encoding="utf-8")

target = """from integrallab.core.parser import (
    ExpressionParseError,
    ParsedExpression,"""

repl = """from integrallab.core.parser import (
    MAX_EXPRESSION_LENGTH,
    ExpressionParseError,
    ParsedExpression,"""

assert target in content
content = content.replace(target, repl, 1)
p.write_text(content, encoding="utf-8")
print("Added MAX_EXPRESSION_LENGTH import to main_window.py")


from pathlib import Path

p = Path("integrallab/core/parser.py")
content = p.read_text(encoding="utf-8")

target = '''        "min": sympy.Min,
    }'''

repl = '''        "min": sympy.Min,
        "factorial": sympy.factorial,
    }'''

assert target in content, "target not found in parser.py"
content = content.replace(target, repl, 1)
p.write_text(content, encoding="utf-8")
print("Successfully added factorial to safe_funcs")


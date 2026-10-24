from pathlib import Path

# 1. Update integrallab/core/parser.py
parser_path = Path("integrallab/core/parser.py")
content = parser_path.read_text(encoding="utf-8")

# Fix cosenh alias
assert "('cosenh',  'asinh')," in content, "cosenh alias not found"
content = content.replace("('cosenh',  'asinh'),", "('cosenh',  'cosh'),", 1)

# Fix factorial limit
factorial_target = """        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)):
            continue"""

factorial_replacement = """        # Acotar argumentos de factorial para evitar congelar el hilo de UI
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "factorial"
            and node.args
        ):
            val = _estimate_constant(node.args[0])
            if val is not None and val > MAX_FACTORIAL_ARG:
                raise ExpressionParseError(
                    f"El factorial admite argumentos de hasta {MAX_FACTORIAL_ARG}."
                )

        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)):
            continue"""

assert "MAX_LITERAL_EXPONENT = 300" in content, "MAX_LITERAL_EXPONENT not found"
content = content.replace(
    "MAX_LITERAL_EXPONENT = 300",
    "MAX_LITERAL_EXPONENT = 300\nMAX_FACTORIAL_ARG = 1000",
    1
)
assert factorial_target in content, "factorial_target not found"
content = content.replace(factorial_target, factorial_replacement, 1)

# Fix _PT_NUM for linear regex
old_pt_num = '_PT_NUM = r"[-+]?(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][-+]?\\d+)?"'
new_pt_num = '_PT_NUM = r"[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][-+]?\\d+)?"'
assert old_pt_num in content, "old_pt_num not found"
content = content.replace(old_pt_num, new_pt_num, 1)

parser_path.write_text(content, encoding="utf-8")
print("parser.py updated")

# 2. Update integrallab/core/pipeline.py
pipeline_path = Path("integrallab/core/pipeline.py")
p_content = pipeline_path.read_text(encoding="utf-8")
p_content = p_content.replace("daba ?rea compleja", "daba área compleja")
p_content = p_content.replace("atraviese la regi?n", "atraviese la región")
p_content = p_content.replace('warnings=["C?lculo num?rico (sin forma exacta)."]', 'warnings=["Cálculo numérico (sin forma exacta)."]')
p_content = p_content.replace('No se calcul? el volumen.', 'No se calculó el volumen.')
pipeline_path.write_text(p_content, encoding="utf-8")
print("pipeline.py updated")

# 3. Update integrallab/core/solids.py
solids_path = Path("integrallab/core/solids.py")
s_content = solids_path.read_text(encoding="utf-8")
s_content = s_content.replace("V?lido porque el eje no atraviesa", "Válido porque el eje no atraviesa")
s_content = s_content.replace("la regi?n (axis_crossing_error ya lo garantiza)", "la región (axis_crossing_error ya lo garantiza)")

# Add _cross_check helper and wire into calculate_revolution_volume
cross_check_def = '''def _cross_check(res: VolumeResult, region: Region2D, axis: RevolutionAxis) -> VolumeResult:
    """Rechaza un volumen simbólico proveniente de inversión que no coincide con la cuadratura independiente."""
    if not res.is_success or res.numeric_value is None:
        return res
    ref = numeric_volume(region, axis)
    if ref is None or math.isclose(res.numeric_value, ref, rel_tol=1e-5, abs_tol=1e-7):
        return res
    return VolumeResult(
        method=res.method,
        is_success=False,
        error_message=(
            f"El planteamiento invertido da {res.numeric_value:.6g}, pero la cuadratura da "
            f"{ref:.6g}. Use el método directo para este eje."
        ),
    )
'''

if "_cross_check(res: VolumeResult" not in s_content:
    # Insert before calculate_revolution_volume
    target_func = "def calculate_revolution_volume("
    assert target_func in s_content, "calculate_revolution_volume not found"
    s_content = s_content.replace(target_func, cross_check_def + "\n\n" + target_func, 1)

old_ret = """                    return _reject_negative(VolumeResult(
                        method=method,
                        exact_plain_text=res.exact_plain_text,
                        exact_latex=res.exact_latex,
                        numeric_value=res.numeric_value,
                        integrand_plain_text=res.integrand_plain_text,
                        integrand_latex=res.integrand_latex,
                        integral_setup_latex=res.integral_setup_latex,
                        is_success=True,
                        steps=new_steps,
                        warnings=res.warnings,
                    ))"""

new_ret = """                    return _cross_check(_reject_negative(VolumeResult(
                        method=method,
                        exact_plain_text=res.exact_plain_text,
                        exact_latex=res.exact_latex,
                        numeric_value=res.numeric_value,
                        integrand_plain_text=res.integrand_plain_text,
                        integrand_latex=res.integrand_latex,
                        integral_setup_latex=res.integral_setup_latex,
                        is_success=True,
                        steps=new_steps,
                        warnings=res.warnings,
                    )), region, axis)"""

assert old_ret in s_content, "old_ret not found in solids.py"
s_content = s_content.replace(old_ret, new_ret, 1)
solids_path.write_text(s_content, encoding="utf-8")
print("solids.py updated")

# 4. Update integrallab/ui/main_window.py (Max length controls)
mw_path = Path("integrallab/ui/main_window.py")
mw_content = mw_path.read_text(encoding="utf-8")

if "from integrallab.core.parser import MAX_EXPRESSION_LENGTH" not in mw_content:
    mw_content = mw_content.replace(
        "from integrallab.core.parser import parse_points",
        "from integrallab.core.parser import parse_points, MAX_EXPRESSION_LENGTH",
        1
    )

old_mw_init_inputs = """        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText("ej. sin(x), x**2, sqrt(x)...")
        self.expression_input.returnPressed.connect(self._on_plot_clicked)
        f_row.addWidget(self.expression_input)
        region_layout.addLayout(f_row)

        # Segunda función g(x) (opcional)
        g_row = QHBoxLayout()
        g_label = QLabel("g(x) =")
        g_label.setFixedWidth(45)
        g_row.addWidget(g_label)
        self.g_expression_input = QLineEdit()
        self.g_expression_input.setPlaceholderText("Opcional: segunda curva, ej. x**2")
        self.g_expression_input.returnPressed.connect(self._on_plot_clicked)
        g_row.addWidget(self.g_expression_input)
        region_layout.addLayout(g_row)

        # Límites a y b
        limits_row = QHBoxLayout()
        limits_row.setSpacing(8)
        label_a = QLabel("Límite a =")
        limits_row.addWidget(label_a)
        self.limit_a_input = QLineEdit()
        self.limit_a_input.setPlaceholderText("ej. 0")
        self.limit_a_input.setFixedWidth(65)
        self.limit_a_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_a_input)

        label_b = QLabel("Límite b =")
        limits_row.addWidget(label_b)
        self.limit_b_input = QLineEdit()
        self.limit_b_input.setPlaceholderText("ej. 2")
        self.limit_b_input.setFixedWidth(65)
        self.limit_b_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_b_input)"""

new_mw_init_inputs = """        self.expression_input = QLineEdit()
        self.expression_input.setMaxLength(20_000)
        self.expression_input.setPlaceholderText("ej. sin(x), x**2, sqrt(x)...")
        self.expression_input.returnPressed.connect(self._on_plot_clicked)
        f_row.addWidget(self.expression_input)
        region_layout.addLayout(f_row)

        # Segunda función g(x) (opcional)
        g_row = QHBoxLayout()
        g_label = QLabel("g(x) =")
        g_label.setFixedWidth(45)
        g_row.addWidget(g_label)
        self.g_expression_input = QLineEdit()
        self.g_expression_input.setMaxLength(MAX_EXPRESSION_LENGTH)
        self.g_expression_input.setPlaceholderText("Opcional: segunda curva, ej. x**2")
        self.g_expression_input.returnPressed.connect(self._on_plot_clicked)
        g_row.addWidget(self.g_expression_input)
        region_layout.addLayout(g_row)

        # Límites a y b
        limits_row = QHBoxLayout()
        limits_row.setSpacing(8)
        label_a = QLabel("Límite a =")
        limits_row.addWidget(label_a)
        self.limit_a_input = QLineEdit()
        self.limit_a_input.setMaxLength(MAX_EXPRESSION_LENGTH)
        self.limit_a_input.setPlaceholderText("ej. 0")
        self.limit_a_input.setFixedWidth(65)
        self.limit_a_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_a_input)

        label_b = QLabel("Límite b =")
        limits_row.addWidget(label_b)
        self.limit_b_input = QLineEdit()
        self.limit_b_input.setMaxLength(MAX_EXPRESSION_LENGTH)
        self.limit_b_input.setPlaceholderText("ej. 2")
        self.limit_b_input.setFixedWidth(65)
        self.limit_b_input.returnPressed.connect(self._on_plot_clicked)
        limits_row.addWidget(self.limit_b_input)"""

assert old_mw_init_inputs in mw_content, "old_mw_init_inputs not found"
mw_content = mw_content.replace(old_mw_init_inputs, new_mw_init_inputs, 1)

assert 'self.axis_value_input = QLineEdit("0")' in mw_content, "axis_value_input not found"
mw_content = mw_content.replace(
    'self.axis_value_input = QLineEdit("0")',
    'self.axis_value_input = QLineEdit("0")\n        self.axis_value_input.setMaxLength(MAX_EXPRESSION_LENGTH)',
    1
)
mw_path.write_text(mw_content, encoding="utf-8")
print("main_window.py updated")


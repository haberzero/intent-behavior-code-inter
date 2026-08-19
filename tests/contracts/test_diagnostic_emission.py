"""
tests/contracts/test_diagnostic_emission.py
============================================

幽灵诊断码发射判别性回归（T05 §六.3）。

锁定 8 个此前"全仓零发射"的诊断码现各有真实发射点（发射 or 删减）：
- RUN_DIVISION_BY_ZERO：除零
- RUN_INDEX_ERROR：下标越界/键不存在
- RUN_ATTRIBUTE_ERROR：属性/方法缺失
- RUN_PERMISSION_ERROR：权限拒绝
- RUN_LLMEXCEPT_SNAPSHOT_VIOLATION：llmexcept 快照篡改（警告）
- LEX_INVALID_NUMBER：非法数字字面量
- PAR_INDENTATION_ERROR：缩进失配（原误用 LEX_INVALID_ESCAPE）
- PAR_MULTIPLE_INTENTS：已删减（语言无"同位置多意图"约束，杜绝死契约）

断言方式：编译/运行触发相应错误，校验输出含预期诊断码（不再裸
RUN_GENERIC_ERROR / RUNTIME_ERROR / 内部错误）。
"""
from tests.conftest import run_ibci, compile_ibci
from core.kernel.issue import CompilerError
from core.engine import IBCIEngine


def _run_err_code(code: str) -> str:
    """运行代码并提取首行诊断码（如 RUN_DIVISION_BY_ZERO）。"""
    import io
    import contextlib

    from core.engine import IBCIEngine
    from tests.conftest import _default_root

    lines = []
    engine = IBCIEngine(root_dir=_default_root())
    try:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    except Exception as e:
        text = str(e)
    else:
        text = err.getvalue() if lines is None else ""
    # 从异常消息提取 [ERROR][CODE]
    import re
    m = re.search(r"\[(?:ERROR|WARNING)\]\[([A-Z][A-Z0-9_]*)\]", text)
    return m.group(1) if m else "NO_CODE"


def _compile_err_codes(code: str) -> list:
    """编译并返回诊断码列表（编译期码）。"""
    from tests.conftest import _default_root

    engine = IBCIEngine(root_dir=_default_root())
    try:
        engine.compile_string(code, silent=True)
    except CompilerError as e:
        return [getattr(d, "code", "") for d in e.diagnostics]
    return []


class TestRuntimeEmission:
    """运行时码发射。"""

    def test_division_by_zero_emits_specific_code(self):
        code = "int a = 10 / 0\n"
        assert _run_err_code(code) == "RUN_DIVISION_BY_ZERO"

    def test_index_error_emits_specific_code(self):
        code = "list[int] l = [1, 2]\nprint(l[5])\n"
        assert _run_err_code(code) == "RUN_INDEX_ERROR"

    def test_dict_key_error_emits_specific_code(self):
        code = 'dict[str, int] d = {"a": 1}\nprint(d["missing"])\n'
        assert _run_err_code(code) == "RUN_INDEX_ERROR"

    def test_attribute_error_emits_specific_code(self):
        code = (
            "class Box:\n"
            "    int v\n"
            "    func __init__(self, int v) -> auto:\n"
            "        self.v = v\n"
            "Box b = Box(5)\n"
            "print(b.nonexistent())\n"
        )
        assert _run_err_code(code) == "RUN_ATTRIBUTE_ERROR"

    def test_permission_error_emits_specific_code(self):
        from tests.conftest import _default_root

        engine = IBCIEngine(root_dir=_default_root())
        code = 'import fs\nfs.read(fs.open("../outside.txt"))\n'
        import re
        try:
            engine.run_string(code, silent=True)
        except Exception as e:
            assert "RUN_PERMISSION_ERROR" in str(e), str(e)
        else:
            raise AssertionError("越权路径应被权限拒绝")


class TestLexerParserEmission:
    """词法/语法码发射。"""

    def test_invalid_number_hex(self):
        assert "LEX_INVALID_NUMBER" in _compile_err_codes("int a = 0x\n")

    def test_invalid_number_trailing_ident(self):
        assert "LEX_INVALID_NUMBER" in _compile_err_codes("int a = 12abc\n")

    def test_invalid_number_hex_trailing_ident(self):
        assert "LEX_INVALID_NUMBER" in _compile_err_codes("int a = 0x1fg\n")

    def test_invalid_number_incomplete_scientific(self):
        assert "LEX_INVALID_NUMBER" in _compile_err_codes("int a = 1e+\n")

    def test_valid_number_literals_still_compile(self):
        """合法数字字面量不误报（0x/0b/0o/小数/科学计数）。"""
        from tests.conftest import _default_root

        engine = IBCIEngine(root_dir=_default_root())
        code = (
            "int h = 0x1f\n"
            "int b = 0b101\n"
            "float f = 1e3\n"
            "float d = 12.5\n"
            "print(h)\n"
        )
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        assert lines == ["31"]

    def test_indentation_error_code(self):
        code = (
            "func f() -> int:\n"
            "    if True:\n"
            "        return 1\n"
            "      return 2\n"
        )
        assert "PAR_INDENTATION_ERROR" in _compile_err_codes(code)


class TestDeletedGhostCode:
    """PAR_MULTIPLE_INTENTS 已删减：语言无该约束，码不再存在于目录。"""

    def test_code_removed_from_catalog(self):
        from core.base.diagnostics.catalog import CODE_CATALOG

        assert "PAR_MULTIPLE_INTENTS" not in CODE_CATALOG


class TestSnapshotViolationEmission:
    """RUN_LLMEXCEPT_SNAPSHOT_VIOLATION：llmexcept 快照篡改发警告。"""

    def test_snapshot_violation_emits_warning(self):
        import warnings

        from tests.conftest import AI_MOCK_PREFIX, REPO_ROOT

        eng = IBCIEngine(root_dir=REPO_ROOT)
        code = AI_MOCK_PREFIX + """
class Box:
    int v
    func __init__(self, int v) -> auto:
        self.v = v
Box b = Box(1)
str r = @~ MOCK:SEQ:[FAIL,DONE] ~
llmexcept:
    b.v = 99
    retry "hint"
print("done")
"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            eng.run_string(code, output_callback=lambda t: None, silent=True)
        msgs = [str(w.message) for w in caught]
        assert any("RUN_LLMEXCEPT_SNAPSHOT_VIOLATION" in m or "快照隔离违规" in m for m in msgs), msgs

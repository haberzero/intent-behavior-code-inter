"""
tests/compiler/test_bare_declaration.py

语句域裸类型声明编译期拒绝（round3 R3-⑧ D-7 语义裁定）：

- 裁定：(c) 编译期检查——语句域 `int x` 式裸声明无合法运行期语义
  （未初始化的类型化变量读取即类型违约；无 None 缺省初始化魔法默认），
  fail-fast 编译期拒绝，精确定位声明语句；
- 合法形态不受限：类字段裸声明（构造器必填参数）/ for 循环变量 /
  函数形参 / 正常带初始值赋值（编译通过面——运行期行为归 e2e 层）。

compiler/ 层 = compile-only（meta 红线：运行期执行用例归 e2e/）——
位置断言经 CompilerError 诊断对象（不执行），合法形态 = 编译通过。
"""
import pytest

from tests.conftest import compile_ibci, compile_or_errors

CODE = "SEM_DECLARATION_WITHOUT_INITIALIZER"


def _compile_errors(code):
    _, errs = compile_or_errors(code)
    return errs


class TestBareDeclarationRejected:
    def test_top_level_bare_declaration(self):
        assert CODE in _compile_errors("int x\nprint('ok')\n")

    def test_function_local_bare_declaration(self):
        code = (
            "func f() -> int:\n"
            "    int x\n"
            "    x = 5\n"
            "    return x\n"
            "print(f())\n"
        )
        assert CODE in _compile_errors(code)

    def test_multiple_types_rejected(self):
        for t in ("int", "str", "float", "bool"):
            assert CODE in _compile_errors(f"{t} x\nprint('ok')\n"), t

    def test_error_location_is_declaration(self):
        """定位 = 声明语句（line 1）——非读取点（fail-fast 精确归因）。"""
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError
        from tests.conftest import TESTS_ROOT
        with pytest.raises(CompilerError) as ei:
            IBCIEngine(root_dir=TESTS_ROOT).compile_string(
                "int x\nprint('ok')\n", silent=True
            )
        d = ei.value.diagnostics[0]
        assert d.code == CODE
        assert d.location.line == 1


class TestLegalFormsUnaffected:
    def test_class_field_bare_declaration_compiles(self):
        """类字段裸声明 = 构造器必填参数（合法形态，编译通过不受限）。"""
        compile_ibci("class P:\n    int v\np = P(3)\nprint(p.v)\n")

    def test_class_field_bare_declaration_missing_arg_still_reported(self):
        """类字段未传参 = 既有 SEM_MISSING_REQUIRED_ARG（非本码）。"""
        errs = _compile_errors("class P:\n    int v\np = P()\nprint(p.v)\n")
        assert CODE not in errs
        assert "SEM_MISSING_REQUIRED_ARG" in errs

    def test_for_loop_variable(self):
        compile_ibci("for int i in range(3):\n    print(i)\n")

    def test_initialized_assignment(self):
        compile_ibci("int x = 5\nprint(x)\n")

    def test_function_param_declaration(self):
        compile_ibci("func f(int x) -> int:\n    return x\nprint(f(7))\n")

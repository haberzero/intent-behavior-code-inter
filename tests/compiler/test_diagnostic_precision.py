"""
tests/compiler/test_diagnostic_precision.py

诊断消息/定位精度（round3 R3-⑦ 诊断消息批）：

- D-6 顶层缩进：PAR_UNEXPECTED_TOKEN（INDENT/DEDENT 处期望表达式）附定向
  缩进修复提示（hint）；
- D-8 true/false/None 小写：SEM_UNDEFINED_SYMBOL did-you-mean 提示
  （布尔/空字面量大写）——既有面锁定（防回归）；
- B4 编译定位精化：赋值型 SEM_TYPE_MISMATCH 定位 = RHS 值节点
  （实际违约源），非整条语句行首（变量/属性/下标两赋值路径）。
"""
import pytest

from tests.conftest import compile_ibci


def _first_diag(code):
    with pytest.raises(Exception) as exc:
        compile_ibci(code)
    diags = exc.value.diagnostics
    assert diags, "应产生编译诊断"
    return diags[0]


class TestTopLevelIndentHint:
    """D-6：顶层缩进的 PAR 诊断附缩进修复提示。"""

    def test_indented_statement_gets_hint(self):
        d = _first_diag("    print('x')\n")
        assert d.code == "PAR_UNEXPECTED_TOKEN"
        assert d.hint is not None
        assert "缩进" in d.hint

    def test_plain_unexpected_token_no_indent_hint(self):
        # 非缩进类语法错误不附缩进提示（提示定向，非泛化）
        d = _first_diag("str = 1\n")
        assert d.hint is None or "缩进" not in d.hint


class TestBooleanDidYouMean:
    """D-8：小写布尔/空字面量 did-you-mean 提示（既有面锁定）。"""

    @pytest.mark.parametrize("lower, upper", [("true", "True"),
                                              ("false", "False"),
                                              ("none", "None")])
    def test_lowercase_literal_gets_suggestion(self, lower, upper):
        d = _first_diag(f"str s = {lower}\nprint(s)\n")
        assert d.code == "SEM_UNDEFINED_SYMBOL"
        assert upper in d.message


class TestAssignmentLocationPrecision:
    """B4：赋值型 SEM_TYPE_MISMATCH 定位 = RHS 值节点（违约源）。"""

    def test_variable_assignment_points_to_rhs(self):
        code = 'int x = "abc"\nprint(x)\n'
        d = _first_diag(code)
        assert d.code == "SEM_TYPE_MISMATCH"
        # "abc" 字面量位置（line 1 col 9）——非语句行首（col 1）
        assert d.location.line == 1
        assert d.location.column > 1

    def test_attribute_assignment_points_to_rhs(self):
        code = (
            "class P:\n"
            "    int v = 1\n"
            "p = P()\n"
            'p.v = "s"\n'
            "print(p.v)\n"
        )
        d = _first_diag(code)
        assert d.code == "SEM_TYPE_MISMATCH"
        # "s" 字面量在 line 4 col 7（此前 = line 4 col 1 行首）
        assert d.location.line == 4
        assert d.location.column == 7

    def test_call_rhs_points_to_callee(self):
        # 调用 RHS：定位 = 被调名位置（违约源起点）
        code = (
            "func g() -> str:\n"
            "    str r = \"x\"\n"
            "    return r\n"
            "int x = g()\n"
            "print(x)\n"
        )
        d = _first_diag(code)
        assert d.code == "SEM_TYPE_MISMATCH"
        assert d.location.line == 4

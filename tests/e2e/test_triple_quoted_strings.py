"""
tests/e2e/test_triple_quoted_strings.py

三引号多行字符串字面量契约（round3 需求 D-2，试用方 v3 统一自动机高频摩擦）：

- 语法面：三个连续同类引号定界的双/单两种形态（与 Python 同构，本文件
  测试代码内以三引号字面量直接书写）；raw 形态正交（r 前缀 + 三引号定界）；
- 值语义（对照 Python）：换行保留为真实换行（含开定界符后首个换行，无
  docstring 式剥离）；缩进保留；转义表与单行字符串同一规则源
  （_apply_string_escape 共享）；反斜杠+换行 = 拼接（结果不含换行，缩进保留）；
  闭合 = 连续三个同类引号（孤立引号/转义引号不闭合）；
- 既有缺陷修复面：字符串内反斜杠+换行续行不再泄漏语句级 continuation_mode
  标志（此前声明收尾换行被吞 → PAR_EXPECTED_TOKEN；单行/三引号同路径）；
- 未闭合三引号串 → LEX_UNTERMINATED_STRING（带 ibci 源行）。
"""
from tests.conftest import compile_or_errors, run_ibci


def eq(code_value: str, expected_repr: str) -> str:
    """构造"值相等断言"代码：print(<value> == <expected>)。"""
    return f'print(({code_value}) == {expected_repr})\n'


class TestTripleQuotedValueSemantics:
    def test_basic_double_triple(self):
        lines = run_ibci('str s = """abc\ndef"""\n' + eq("s", '"abc\\ndef"'))
        assert lines == ["True"]

    def test_basic_single_triple(self):
        lines = run_ibci("str s = '''abc\ndef'''\n" + eq("s", '"abc\\ndef"'))
        assert lines == ["True"]

    def test_first_newline_after_open_preserved(self):
        lines = run_ibci('str s = """\nabc"""\n' + eq("s", '"\\nabc"'))
        assert lines == ["True"]

    def test_indentation_preserved(self):
        lines = run_ibci('str s = """abc\n    def"""\n' + eq("s", '"abc\\n    def"'))
        assert lines == ["True"]

    def test_empty_triple(self):
        lines = run_ibci('str s = """"""\n' + eq("s", '""'))
        assert lines == ["True"]

    def test_escapes_handled(self):
        # IBCI 源: str s = """a\tb\"c"""  （\t = tab、\" = 引号）
        lines = run_ibci(
            'str s = """a\\tb\\"c"""\n'
            + 'print((s) == "a\\tb\\"c")\n'
        )
        assert lines == ["True"]

    def test_backslash_newline_join(self):
        lines = run_ibci('str s = """abc\\\n   def"""\n' + eq("s", '"abc   def"'))
        assert lines == ["True"]

    def test_raw_triple_preserves_backslash(self):
        # IBCI 源: str s = r"""C:\path\x"""（raw 保留反斜杠）；
        # 期望字面量用非 raw 串 "\\path" 表达同一值（\\ = 反斜杠）
        lines = run_ibci(
            'str s = r"""C:\\path\\x"""\n'
            + 'print((s) == "C:\\\\path\\\\x")\n'
        )
        assert lines == ["True"]

    def test_lone_quotes_inside(self):
        # IBCI 源: str s = """a'b"c"""（孤立双引号不闭合三引号串）；
        # 期望字面量 "a'b\"c" 中 \" 转义 IBCI 引号
        lines = run_ibci(
            'str s = """a\'b"c"""\n'
            + 'print((s) == "a\'b\\"c")\n'
        )
        assert lines == ["True"]

    def test_multi_line_content_display(self):
        lines = run_ibci('str s = """line1\nline2\nline3"""\nprint(s)\n')
        assert lines == ["line1\nline2\nline3"]

    def test_class_field_default(self):
        lines = run_ibci(
            'class X:\n    str t = """multi\nline"""\n'
            + eq("X().t", '"multi\\nline"')
        )
        assert lines == ["True"]

    def test_function_return(self):
        lines = run_ibci(
            'func f() -> str:\n    return """a\nb"""\n'
            + eq("f()", '"a\\nb"')
        )
        assert lines == ["True"]

    def test_code_after_closing_same_line(self):
        lines = run_ibci('str s = """abc"""\nprint(s)\nprint("done")\n')
        assert lines == ["abc", "done"]

    def test_comment_after_closing_same_line(self):
        lines = run_ibci('str s = """abc"""  # trailing comment\nprint(s)\n')
        assert lines == ["abc"]


class TestSingleLineStringRegression:
    """对照面：单行字符串/既有续行机制行为（含既有缺陷修复）。"""

    def test_single_line_unchanged(self):
        lines = run_ibci('str s = "abc"\n' + eq("s", '"abc"'))
        assert lines == ["True"]

    def test_empty_single_line_unchanged(self):
        lines = run_ibci('str s = ""\n' + eq("s", '""'))
        assert lines == ["True"]

    def test_raw_single_line_unchanged(self):
        # IBCI 源: str s = r"\n"（raw → 字面反斜杠+n）；期望字面量 "\\n" 同值
        lines = run_ibci(
            'str s = r"\\n"\n'
            + 'print((s) == "\\\\n")\n'
        )
        assert lines == ["True"]

    def test_in_string_backslash_newline_join_top(self):
        # 既有缺陷修复面：此前声明收尾换行被残留 continuation_mode 吞掉
        # → PAR_EXPECTED_TOKEN；现正常编译运行（拼接语义）。
        lines = run_ibci('str s = "abc\\\n   def"\n' + eq("s", '"abc   def"'))
        assert lines == ["True"]

    def test_in_string_backslash_newline_join_func(self):
        lines = run_ibci(
            'func f() -> str:\n    return "a\\\nb"\n' + eq("f()", '"ab"')
        )
        assert lines == ["True"]

    def test_top_level_continuation_unchanged(self):
        lines = run_ibci("x = 1 + \\\n2\nprint((str)x)\n")
        assert lines == ["3"]


class TestUnterminatedTripleString:
    def test_eof_error(self):
        _, errors = compile_or_errors('str s = """abc\n')
        assert "LEX_UNTERMINATED_STRING" in errors

    def test_eof_after_single_line_prefix(self):
        # 三引号未闭合后即使后续有引号也不误判闭合
        _, errors = compile_or_errors('str s = """abc\ndef\n')
        assert "LEX_UNTERMINATED_STRING" in errors

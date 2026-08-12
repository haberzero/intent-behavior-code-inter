"""
tests/compiler/semantic/test_scope_global.py
============================================

``global`` 关键字回归测试（PT-DEBT-25，2026-08-12）。

背景：``global counter`` 声明的函数内读写此前运行时
``RUN_UNDEFINED_VARIABLE: .../bump:counter``——symbol_resolution_pass 未消费
global 声明（缺 visit_IbGlobalStmt + prescan 未排除 global 名），函数内赋值目标
被预声明为局部符号（局部 UID），运行时 global 路由（define_variable_at_global /
_assign_name_target 的 is_global_symbol_uid 分支）因收不到模块级 UID 而永不触发。

修复：visit_IbGlobalStmt 把名称解析/占位到模块根作用域并共享符号引用；
_prescan_body_locals 排除 global_names（与 nonlocal 同构）。
"""
import pytest

from core.engine import IBCIEngine

from tests.conftest import _default_root, run_ibci, compile_or_errors


class TestGlobalStatement:
    """global 关键字在函数内的写访问语义。"""

    def test_global_write_in_function(self):
        code = """
int counter = 0
func bump() -> void:
    global counter
    counter = counter + 1

bump()
print("counter=" + (str)counter)
"""
        lines = run_ibci(code)
        assert lines == ["counter=1"]

    def test_global_write_then_set(self):
        code = """
int counter = 0
func bump() -> void:
    global counter
    counter = counter + 1

func setter(int v) -> void:
    global counter
    counter = v

bump()
setter(99)
print("counter2=" + (str)counter)
"""
        lines = run_ibci(code)
        assert lines == ["counter2=99"]

    def test_global_multi_names(self):
        code = """
func init_all() -> void:
    global a, b
    a = 10
    b = 20

init_all()
print((str)a + "," + (str)b)
"""
        lines = run_ibci(code)
        assert lines == ["10,20"]

    def test_global_declaration_before_definition(self):
        """global 声明之后才定义全局变量（Python 语义，02_variables §2.6）。"""
        code = """
func init_all() -> void:
    global a
    a = 10

init_all()
print((str)a)
"""
        lines = run_ibci(code)
        assert lines == ["10"]

    def test_global_read_only_and_aug_assign(self):
        code = """
int total = 0
func accumulate(int n) -> void:
    global total
    total = total + n

func read_only() -> int:
    global total
    return total

accumulate(5)
accumulate(7)
print((str)read_only())
"""
        lines = run_ibci(code)
        assert lines == ["12"]

    def test_global_binding_uses_module_uid(self):
        """编译期绑定：函数内对 global 名的引用/赋值必须绑定模块级 UID
        （scope_<module>:name），而非函数局部 UID（scope_<module>/func:name）。"""
        from core.compiler.semantic.analyzer import SemanticAnalyzer
        from core.compiler.diagnostics.issue_tracker import IssueTracker
        from core.compiler.lexer.lexer import Lexer
        from core.compiler.parser.parser import Parser
        from core.kernel.factory import create_default_registry
        from core.kernel.symbols import Symbol

        code = (
            "int counter = 0\n"
            "func bump() -> void:\n"
            "    global counter\n"
            "    counter = counter + 1\n"
        )
        tracker = IssueTracker()
        lexer = Lexer(code, tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, tracker)
        ast_node = parser.parse()

        analyzer = SemanticAnalyzer(tracker, registry=create_default_registry(), module_name="test")
        result = analyzer.analyze(ast_node, raise_on_error=False)
        assert result.node_to_symbol, "node_to_symbol side table must be populated"

        found = False
        for sym in result.node_to_symbol.values():
            if isinstance(sym, Symbol) and sym.name == "counter":
                found = True
                uid = sym.uid or ""
                assert "/bump:" not in uid, f"counter bound to local UID: {uid}"
                assert uid.endswith(":counter"), f"unexpected UID: {uid}"
        assert found, "no counter symbol bound in node_to_symbol"

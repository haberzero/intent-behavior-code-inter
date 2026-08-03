"""
tests/compiler/test_concurrency_syntax.py
==========================================

PT-MT-2 编译器地基测试：spawn/join/cancel/chan/signal/slot 语法与语义。

锁定：
- 新关键字（spawn/join/cancel/chan/signal/slot/task）的 lexer 识别
- 新 AST 节点（IbSpawnStmt/IbJoinStmt/IbCancelStmt/IbChannelExpr/
  IbSignalExpr/IbSlotExpr）的 parser 产出
- 类型注解（task/chan/signal/slot）的解析
- 语义校验正/负样本（spawn 可调用、join/cancel 目标 task 类型）
- 序列化 round-trip（新节点类型在 artifact 中存活）
"""
import pytest

from tests.conftest import run_ibci, compile_or_errors, compile_ibci

from core.compiler.lexer.lexer import Lexer
from core.compiler.common.tokens import TokenType


def assert_compiles(code: str):
    artifact, errors = compile_or_errors(code)
    assert artifact is not None
    assert not errors, f"Expected no compiler errors, got: {errors}"


def assert_error_codes(code: str, *expected_codes: str):
    _, errors = compile_or_errors(code)
    for code_val in expected_codes:
        assert code_val in errors, f"Expected error {code_val!r} but got: {errors}"


# ────────────────────────────────────────────────────── lexer ──

class TestLexer:
    def test_concurrency_keywords_produce_tokens(self):
        tokens = Lexer("spawn task join cancel chan signal slot").tokenize()
        types = [t.type for t in tokens]
        assert TokenType.SPAWN in types
        assert TokenType.TASK in types
        assert TokenType.JOIN in types
        assert TokenType.CANCEL in types
        assert TokenType.CHAN in types
        assert TokenType.SIGNAL in types
        assert TokenType.SLOT in types


# ────────────────────────────────────────────────────── parser ──

class TestParser:
    def _module_body(self, code):
        from core.compiler.parser.parser import Parser
        from core.compiler.lexer.lexer import Lexer
        tokens = Lexer(code).tokenize()
        module = Parser(tokens).parse()
        return module.body

    def test_spawn_parse(self):
        body = self._module_body("spawn foo()\n")
        assert any(type(s).__name__ == "IbSpawnStmt" for s in body)

    def test_join_parse(self):
        body = self._module_body("join t\n")
        assert any(type(s).__name__ == "IbJoinStmt" for s in body)

    def test_cancel_parse(self):
        body = self._module_body("cancel t\n")
        assert any(type(s).__name__ == "IbCancelStmt" for s in body)

    def test_chan_signal_slot_expr_in_artifact(self):
        artifact = compile_ibci("""
chan c = chan(str, "stream")
signal s = signal("cancel")
slot st = slot("score", 0)
""")
        from core.compiler.serialization.serializer import FlatSerializer
        d = FlatSerializer().serialize_artifact(artifact)
        nodes = d["modules"][artifact.entry_module]["pools"]["nodes"]
        types = {v["_type"] for v in nodes.values()}
        assert "IbChannelExpr" in types
        assert "IbSignalExpr" in types
        assert "IbSlotExpr" in types


# ────────────────────────────────────────────────────── type annotation ──

class TestTypeAnnotations:
    def test_task_type_declaration(self):
        assert_compiles("""
func compute(str x) -> int:
    return 1
task t = spawn compute("x")
""")

    def test_chan_type_declaration(self):
        assert_compiles("chan c = chan(str, \"stream\")\n")

    def test_signal_type_declaration(self):
        assert_compiles("signal s = signal(\"cancel\")\n")

    def test_slot_type_declaration(self):
        assert_compiles("slot st = slot(\"score\", 0)\n")


# ────────────────────────────────────────────────────── semantic ──

class TestSemanticPositive:
    def test_spawn_function(self):
        assert_compiles("""
func compute(str x) -> int:
    return 1
task t = spawn compute("x")
""")

    def test_spawn_plain_function_reference(self):
        assert_compiles("""
func compute(str x) -> int:
    return 1
task t = spawn compute
""")

    def test_spawn_lambda(self):
        assert_compiles("""
task t = spawn lambda(int x) -> int: x + 1
""")

    def test_join_task(self):
        assert_compiles("""
func compute(str x) -> int:
    return 1
task t = spawn compute("x")
any r = join t
""")

    def test_cancel_task(self):
        assert_compiles("""
func compute(str x) -> int:
    return 1
task t = spawn compute("x")
cancel t
""")


class TestSemanticNegative:
    def test_spawn_non_callable(self):
        assert_error_codes("""
int x = 5
task t = spawn x
""", "SEM_TYPE_MISMATCH")

    def test_join_non_task(self):
        assert_error_codes("""
int x = 5
any r = join x
""", "SEM_TYPE_MISMATCH")

    def test_cancel_non_task(self):
        assert_error_codes("""
int x = 5
cancel x
""", "SEM_TYPE_MISMATCH")


# ────────────────────────────────────────────────────── serialization ──

class TestSerialization:
    def test_new_node_types_survive_artifact(self):
        artifact = compile_ibci("""
func compute(str x) -> int:
    return 1
task t = spawn compute("x")
int r = join t
cancel t
chan c = chan(str, "stream")
signal s = signal("cancel")
slot st = slot("score", 0)
""")
        from core.compiler.serialization.serializer import FlatSerializer
        d = FlatSerializer().serialize_artifact(artifact)
        nodes = d["modules"][artifact.entry_module]["pools"]["nodes"]
        types = {v["_type"] for v in nodes.values()}
        assert {"IbSpawnStmt", "IbJoinStmt", "IbCancelStmt",
                "IbChannelExpr", "IbSignalExpr", "IbSlotExpr"} <= types

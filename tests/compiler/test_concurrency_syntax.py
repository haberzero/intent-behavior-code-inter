"""
tests/compiler/test_concurrency_syntax.py
==========================================

并发/通信语法测试（chan/slot）：编译器地基。

锁定：
- 新关键字（chan/slot）的 lexer 识别
- 新 AST 节点（IbChannelExpr/IbSlotExpr）的 parser 产出
- 类型注解（chan/slot）的解析
- 序列化 round-trip（节点类型在 artifact 中存活）

spawn/join/cancel/task 已按线程对象模型方向修正删除；
signal 已移除（零投递机制 + 与 VM 控制流 Signal 撞名）。
其新测试见 test_thread_model.py / test_thread_result.py / test_vm_instance.py。
"""
import pytest

from tests.conftest import run_ibci, compile_or_errors, compile_ibci

from core.compiler.lexer.lexer import Lexer
from core.compiler.common.tokens import TokenType


def assert_compiles(code: str):
    artifact, errors = compile_or_errors(code)
    assert artifact is not None
    assert not errors, f"Expected no compiler errors, got: {errors}"


# ────────────────────────────────────────────────────── lexer ──

class TestLexer:
    def test_comm_keywords_produce_tokens(self):
        tokens = Lexer("chan slot").tokenize()
        types = [t.type for t in tokens]
        assert TokenType.CHAN in types
        assert TokenType.SLOT in types

    def test_signal_keyword_removed(self):
        """signal 关键字已从 lexer 移除（作为普通标识符 lex）。"""
        tokens = Lexer("signal").tokenize()
        types = [t.type for t in tokens]
        assert TokenType.IDENTIFIER in types
        assert TokenType.CHAN not in types
        assert TokenType.SLOT not in types


# ────────────────────────────────────────────────────── parser ──

class TestParser:
    def test_chan_slot_expr_in_artifact(self):
        artifact = compile_ibci("""
chan c = chan(str, "stream")
slot st = slot("score", 0)
""")
        from core.compiler.serialization.serializer import FlatSerializer
        d = FlatSerializer().serialize_artifact(artifact)
        nodes = d["modules"][artifact.entry_module]["pools"]["nodes"]
        types = {v["_type"] for v in nodes.values()}
        assert "IbChannelExpr" in types
        assert "IbSlotExpr" in types


# ────────────────────────────────────────────────────── type annotation ──

class TestTypeAnnotations:
    def test_chan_type_declaration(self):
        assert_compiles("chan c = chan(str, \"stream\")\n")

    def test_slot_type_declaration(self):
        assert_compiles("slot st = slot(\"score\", 0)\n")


# ────────────────────────────────────────────────────── serialization ──

class TestSerialization:
    def test_comm_node_types_survive_artifact(self):
        artifact = compile_ibci("""
chan c = chan(str, "stream")
slot st = slot("score", 0)
""")
        from core.compiler.serialization.serializer import FlatSerializer
        d = FlatSerializer().serialize_artifact(artifact)
        nodes = d["modules"][artifact.entry_module]["pools"]["nodes"]
        types = {v["_type"] for v in nodes.values()}
        assert {"IbChannelExpr", "IbSlotExpr"} <= types

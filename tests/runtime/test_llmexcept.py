"""
tests/runtime/test_llmexcept.py
================================

llmexcept 子系统综合测试（合并自 2 个历史文件）：

* LLMExceptFrame 数据结构 — error_history 跨 retry 保留、max_depth 限制
  （原 ``test_llm_except_frame_enhancements.py``）。
* ``str + llm_uncertain`` 隐式拼接禁止 — 编译期 / 运行期 / 公理三路径
  （原 ``test_uncertain_str_concat_prohibition.py``）。

注：``IbLLMExceptionalStmt`` CPS handler 的注册 / 帧生命周期 / 主路径切换
等测试在 Step 4 合并到了 ``tests/runtime/test_vm_executor.py``。

详见 docs/TESTS_REORGANIZATION_TASK.md Step 7。
"""
import pytest

from core.engine import IBCIEngine
from core.runtime.interpreter.llm_except_frame import LLMExceptFrame, LLMExceptFrameStack


# ---------------------------------------------------------------------------
# 共享 helper（统一来源）
# ---------------------------------------------------------------------------

ROOT_DIR = "."


def ai_setup() -> str:
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def make_engine(code: str, output_lines=None):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    cb = (lambda t: output_lines.append(str(t))) if output_lines is not None else (lambda t: None)
    engine.run_string(code, output_callback=cb, silent=True)
    return engine


################################################################################
# MERGED: LLMExceptFrame enhancements (error history / depth limit)
# Source: tests/runtime/test_llm_except_frame_enhancements.py
################################################################################

class TestLlmExceptErrorHistory:
    def test_error_history_is_preserved_across_retry_reset(self):
        frame = LLMExceptFrame(target_uid="u1", node_type="IbExprStmt")

        frame.set_error(ValueError("first error"), "r1")
        frame.reset_for_retry()
        frame.set_error(RuntimeError("second error"), "r2")

        assert frame.last_error is not None
        assert str(frame.last_error) == "second error"
        assert len(frame.error_history) == 2
        assert frame.error_history[0]["error_type"] == "ValueError"
        assert frame.error_history[0]["error_message"] == "first error"
        assert frame.error_history[1]["error_type"] == "RuntimeError"
        assert frame.error_history[1]["response"] == "r2"

    def test_get_retry_info_contains_error_history(self):
        frame = LLMExceptFrame(target_uid="u2", node_type="IbExprStmt")
        frame.set_error(ValueError("boom"))
        info = frame.get_retry_info()

        assert info["error_history_count"] == 1
        assert info["error_history"][0]["error_type"] == "ValueError"
        assert info["error_history"][0]["error_message"] == "boom"


class TestLlmExceptDepthLimit:
    def test_llm_except_frame_stack_enforces_max_depth(self):
        stack = LLMExceptFrameStack(max_depth=2)
        stack.push(LLMExceptFrame(target_uid="a", node_type="IbExprStmt"))
        stack.push(LLMExceptFrame(target_uid="b", node_type="IbExprStmt"))

        with pytest.raises(RuntimeError, match="max depth 2 exceeded"):
            stack.push(LLMExceptFrame(target_uid="c", node_type="IbExprStmt"))

    def test_runtime_context_enforces_llmexcept_depth_limit(self):
        engine = IBCIEngine(root_dir=".", auto_sniff=False)
        engine.run_string("pass\n", silent=True)
        ctx = engine.interpreter.runtime_context
        ctx._llm_except_max_depth = 2

        ctx.push_llm_except_frame(LLMExceptFrame(target_uid="a", node_type="IbExprStmt"))
        ctx.push_llm_except_frame(LLMExceptFrame(target_uid="b", node_type="IbExprStmt"))

        with pytest.raises(RuntimeError, match="max depth 2 exceeded"):
            ctx.push_llm_except_frame(LLMExceptFrame(target_uid="c", node_type="IbExprStmt"))


################################################################################
# MERGED: NS-4 — str + llm_uncertain implicit concat is forbidden
# Source: tests/runtime/test_uncertain_str_concat_prohibition.py
################################################################################

# ===========================================================================
# 1. llmexcept body 内 `str + uncertain` 应抛 LLMParseError
# ===========================================================================

class TestUncertainConcatRaisesInLlmexceptBody:
    def test_concat_in_llmexcept_body_caught_by_try_except(self):
        """在 llmexcept body 内做 `str + uncertain` 必须可被 try/except LLMParseError 捕获。"""
        lines = []
        # MOCK:REPAIR 第一次返回 uncertain，触发 llmexcept body；body 内尝试
        # `"got: " + x` 现在应抛 LLMParseError，被外层 try/except 捕获。
        code = ai_setup() + """
try:
    str x = @~ MOCK:REPAIR concat_in_body ~
    llmexcept:
        print("got: " + x)
        retry
except LLMParseError as e:
    print("parse_caught")
print("after")
"""
        engine = make_engine(code, lines)
        assert "parse_caught" in lines
        assert "after" in lines
        # 关键反例：旧行为会输出 "got: uncertain"，新行为不应出现
        assert not any("got: uncertain" in line for line in lines)


# ===========================================================================
# 2. `(str)uncertain_var` 显式转换仍可用
# ===========================================================================

class TestExplicitCastStillWorks:
    def test_explicit_cast_uncertain_to_str_returns_uncertain_text(self):
        """`(str)uncertain_var` 显式转换是用户明确意图，必须保留为 \"uncertain\" 文本。"""
        lines = []
        code = ai_setup() + """
try:
    str x = @~ MOCK:REPAIR explicit_cast ~
    llmexcept:
        str s = (str)x
        print("cast: " + s)
        retry
except LLMParseError as e:
    print("should_not_caught")
print("done")
"""
        engine = make_engine(code, lines)
        # (str)uncertain → "uncertain"，参与拼接得到 "cast: uncertain"
        assert "cast: uncertain" in lines
        assert "done" in lines
        assert "should_not_caught" not in lines


# ===========================================================================
# 3. 公理层：StrAxiom.resolve_operation_type_name 不再放行
# ===========================================================================

class TestStrAxiomNoLongerAllowsUncertain:
    def test_str_axiom_rejects_uncertain_for_plus(self):
        """直接询问 StrAxiom：`str + llm_uncertain` 应返回 None（与 SEM_003 一致）。"""
        from core.kernel.axioms.primitives import StrAxiom
        axiom = StrAxiom()
        # 旧行为：返回 "str"；NS-4 收紧后：返回 None
        assert axiom.resolve_operation_type_name("+", "llm_uncertain") is None
        # 反例确认：str + str 仍正确
        assert axiom.resolve_operation_type_name("+", "str") == "str"

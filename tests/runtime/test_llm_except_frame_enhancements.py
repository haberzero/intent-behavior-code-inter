import pytest

from core.engine import IBCIEngine
from core.runtime.interpreter.llm_except_frame import LLMExceptFrame, LLMExceptFrameStack


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

        try:
            stack.push(LLMExceptFrame(target_uid="c", node_type="IbExprStmt"))
            pytest.fail("Expected RuntimeError for frame stack overflow")
        except RuntimeError as e:
            assert "max depth 2 exceeded" in str(e)

    def test_runtime_context_enforces_llmexcept_depth_limit(self):
        engine = IBCIEngine(root_dir=".", auto_sniff=False)
        engine.run_string("pass\n", silent=True)
        ctx = engine.interpreter.runtime_context
        ctx._llm_except_max_depth = 2

        ctx.push_llm_except_frame(LLMExceptFrame(target_uid="a", node_type="IbExprStmt"))
        ctx.push_llm_except_frame(LLMExceptFrame(target_uid="b", node_type="IbExprStmt"))

        try:
            ctx.push_llm_except_frame(LLMExceptFrame(target_uid="c", node_type="IbExprStmt"))
            pytest.fail("Expected RuntimeError for runtime-context llmexcept depth overflow")
        except RuntimeError as e:
            assert "max depth 2 exceeded" in str(e)

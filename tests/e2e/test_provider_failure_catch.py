"""
tests/e2e/test_provider_failure_catch.py
========================================

真实 LLM provider 层失败（网络/超时/断连）的异常投递行为。

机制：provider 失败经 worker 线程 + Future 回传时，异常投递与值对称——Waitable
挂起点记录 ``pending_exception`` 并重投递给挂起该 Waitable 的任务帧，其
try/except 优先处理；未捕获则经弹栈通道沿 CPS 栈上抛。

契约：真实 provider 失败可被 try/except 捕获（MOCK 路径本就正常）。
"""
import pytest

from core.engine import IBCIEngine
from core.runtime.capability_registry import CapabilityRegistry

from tests.conftest import _default_root


class _FailingProvider:
    """每次调用都抛异常的真实 provider（模拟超时/断连）。"""

    def __call__(self, sys_prompt, user_prompt, target_model=""):
        raise RuntimeError("provider timeout")

    def get_current_call_info(self):
        return {}

    def get_return_type_prompt(self, type_name):
        return None

    def get_retry(self):
        return 3

    def is_auto_intent_injection_enabled(self):
        return True


def _run_with_failing_provider(code: str):
    eng = IBCIEngine(root_dir=_default_root(), auto_sniff=False)
    eng.capability_registry.register(
        CapabilityRegistry.CAP_LLM_PROVIDER, _FailingProvider(), plugin_id="test"
    )
    lines = []
    eng.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


class TestProviderFailureCatch:
    """真实 provider 失败（超时/断连）必须被 try/except 捕获，不得逃逸崩溃。"""

    def test_behavior_expr_caught_by_llm_call_error(self):
        code = """
try:
    str r = @~ 请写一段话 ~
    print((str)r.len())
    print("unexpected_success")
except LLMCallError as e:
    print("caught_llmcall")
    print(e.message)
except LLMError as e:
    print("wrong_branch")
except Exception as e:
    print("caught_gen")
print("after_catch")
"""
        lines = _run_with_failing_provider(code)
        assert "caught_llmcall" in lines
        assert "after_catch" in lines
        assert "unexpected_success" not in lines

    def test_behavior_expr_caught_by_base_exception(self):
        code = """
try:
    str r = @~ 请写一段话 ~
    print((str)r.len())
    print("unexpected_success")
except Exception as e:
    print("caught_gen")
print("after_catch")
"""
        lines = _run_with_failing_provider(code)
        assert "caught_gen" in lines
        assert "after_catch" in lines

    def test_llm_function_caught_by_llm_error(self):
        code = """
llm 写作文(str topic) -> str:
__sys__
你是作家。
__user__
写一篇关于 $topic 的作文。
llmend

try:
    str r = 写作文("秋天")
    print("unexpected_success")
except LLMError as e:
    print("caught_llm")
print("after_catch")
"""
        lines = _run_with_failing_provider(code)
        assert "caught_llm" in lines
        assert "after_catch" in lines

    def test_llmexcept_provider_failure_caught_by_outer_try(self):
        """provider 层失败 → LLMCallError 直接抛出（跳过 llmexcept retry，见
        10_robustness §10.3/04 §4.7）→ 外层 try/except 捕获。"""
        code = """
try:
    int n = @~ 返回一个数字 ~
    llmexcept:
        retry "请只返回数字"
    print("unexpected_success")
except LLMCallError as e:
    print("caught_call_error")
except LLMError as e:
    print("caught_llm")
except Exception as e:
    print("caught_gen")
print("after_catch")
"""
        lines = _run_with_failing_provider(code)
        assert "after_catch" in lines
        assert "unexpected_success" not in lines
        assert any(x in lines for x in ("caught_call_error", "caught_llm", "caught_gen"))

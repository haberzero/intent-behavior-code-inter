"""
tests/runtime/test_llm_result_future.py
========================================

``LLMResult`` / ``LLMFuture`` 生命周期与语义测试。

锁定并发 dispatch 基础设施的取值语义：
- ``LLMResult.is_success``：仅当 success 且非 uncertain 为真
- ``success_result`` / ``uncertain_result`` / ``error_result`` 三工厂语义
- ``LLMFuture.is_done``：反映底层 ``concurrent.futures.Future`` 完成态

（生产取值路径：VM 全走 CPS ``resolve_future_cps`` / Waitable ``try_result``，
无同步阻塞取回 API；本文件仅锁定 ``LLMResult``/``LLMFuture`` 的状态与工厂语义。）

这些类为叶子模块（executor 无关），可独立单测 —— 是语义锁定的最小、稳健载体。
"""
from concurrent.futures import Future

from core.runtime.shared.llm_result import LLMResult, LLMFuture


_VALUE = object()


# ---------------------------------------------------------------------------
# LLMResult
# ---------------------------------------------------------------------------


class TestLLMResult:
    def test_is_success_requires_success_and_not_uncertain(self):
        assert LLMResult(success=True, is_uncertain=False).is_success is True
        assert LLMResult(success=True, is_uncertain=True).is_success is False
        assert LLMResult(success=False, is_uncertain=False).is_success is False

    def test_success_result_factory(self):
        r = LLMResult.success_result(value=_VALUE, raw_response="raw")
        assert r.success is True
        assert r.is_uncertain is False
        assert r.value is _VALUE
        assert r.raw_response == "raw"

    def test_uncertain_result_factory(self):
        r = LLMResult.uncertain_result(raw_response="r", retry_hint="h")
        assert r.success is True
        assert r.is_uncertain is True
        assert r.value is None
        assert r.retry_hint == "h"

    def test_error_result_factory(self):
        r = LLMResult.error_result("bad")
        assert r.success is False
        assert r.is_uncertain is False
        assert r.error_message == "bad"


# ---------------------------------------------------------------------------
# LLMFuture
# ---------------------------------------------------------------------------


class TestLLMFuture:
    def test_is_done_reflects_underlying_future(self):
        f = Future()
        lf = LLMFuture("n", f)
        assert lf.is_done is False
        f.set_result(LLMResult.success_result(value=_VALUE))
        assert lf.is_done is True
"""
tests/runtime/test_llm_result_future.py
========================================

PT-SYNC-2: ``LLMResult`` / ``LLMFuture`` 生命周期与语义测试。

锁定并行 dispatch 基础设施的取值语义：
- ``LLMResult.is_success``：仅当 success 且非 uncertain 为真
- ``success_result`` / ``uncertain_result`` / ``error_result`` 三工厂语义
- ``LLMFuture.is_done``：反映底层 ``concurrent.futures.Future`` 完成态
- ``LLMFuture.get()``：blocking；成功返回值 / 不确定返 IbLLMCallResult /
  值为空返 registry.get_none() / 后台异常重新抛出

这些类为叶子模块（executor 无关），可独立单测 —— 是 PT-SYNC-2 语义锁定的
最小、稳健载体。
"""
from concurrent.futures import Future
import threading

import pytest

from core.runtime.shared.llm_result import LLMResult, LLMFuture
from core.runtime.objects.kernel import IbLLMCallResult


_NONE_MARKER = object()


class _FakeResultType:
    """占位 llm_call_result 类（IbValue 经 getattr(ib_class,'spec') 容忍无 spec）。"""


class _Registry:
    def get_class(self, name):
        assert name == "llm_call_result"
        return _FakeResultType

    def get_none(self):
        return _NONE_MARKER


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
    @staticmethod
    def _future_with(result):
        f = Future()
        f.set_result(result)
        return LLMFuture(node_uid="n", future=f)

    def test_is_done_reflects_underlying_future(self):
        f = Future()
        lf = LLMFuture("n", f)
        assert lf.is_done is False
        f.set_result(LLMResult.success_result(value=_VALUE))
        assert lf.is_done is True

    def test_get_returns_success_value(self):
        lf = self._future_with(LLMResult.success_result(value=_VALUE))
        assert lf.get(_Registry()) is _VALUE

    def test_get_uncertain_returns_llm_call_result(self):
        lf = self._future_with(
            LLMResult.uncertain_result(raw_response="r", retry_hint="h")
        )
        got = lf.get(_Registry())
        assert isinstance(got, IbLLMCallResult)
        assert got.is_certain is False
        assert got.raw_response == "r"
        assert got.retry_hint == "h"

    def test_get_none_value_returns_registry_none(self):
        lf = self._future_with(LLMResult.success_result(value=None))
        assert lf.get(_Registry()) is _NONE_MARKER

    def test_get_propagates_worker_exception(self):
        f = Future()
        f.set_exception(RuntimeError("boom"))
        lf = LLMFuture("n", f)
        with pytest.raises(RuntimeError):
            lf.get(_Registry())

    def test_get_blocks_until_worker_completes(self):
        f = Future()
        lf = LLMFuture("n", f)

        def _setter():
            import time

            time.sleep(0.05)
            f.set_result(LLMResult.success_result(value=_VALUE))

        t = threading.Thread(target=_setter)
        t.start()
        try:
            assert lf.get(_Registry()) is _VALUE
        finally:
            t.join()
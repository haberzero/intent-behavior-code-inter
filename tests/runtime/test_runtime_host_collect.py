"""
tests/runtime/test_runtime_host_collect.py
===========================================

``HostService.collect`` 委托契约 + ``HostAwaitable`` 协议测试。

新契约：``HostService.collect`` 返回 ``HostAwaitable``（可等待句柄，非直接 dict）：
- 无 orchestrator 时抛 ``RuntimeError``（守护分支）
- 有 orchestrator 时返回 ``HostAwaitable``，其 ``is_done`` 委托 ``is_spawn_done``，
  ``result()`` 委托 ``request_collect`` 取回子环境变量字典
- ``HostAwaitable`` 结构性满足 ``Waitable`` 协议（``is_done`` 属性 + ``result()``）
- orchestrator 抛出的异常在 ``result()`` 时向上传播

完整的 spawn→collect 端到端流程由 ``tests/e2e/test_e2e_multi_interpreter.py`` 覆盖。
"""
import pytest

from core.runtime.host.service import HostService
from core.runtime.host.awaitable import HostAwaitable
from core.runtime.shared.waitable import Waitable


class _FakeOrchestrator:
    """最小 orchestrator 桩：实现 request_collect / is_spawn_done。"""

    def __init__(self, result=None, error=None, done=True):
        self.result = result
        self.error = error
        self.done = done
        self.collected_handles = []

    def request_collect(self, handle):
        self.collected_handles.append(handle)
        if self.error is not None:
            raise self.error
        return self.result

    def is_spawn_done(self, handle):
        return self.done


def _make_service(orchestrator=None):
    """构造 HostService，仅注入 orchestrator（collect 只依赖它）。"""
    service = HostService(
        registry=None,
        execution_context=None,
        interop=None,
        setup_context_callback=None,
        get_current_module_callback=None,
    )
    service.orchestrator = orchestrator
    return service


class TestHostServiceCollect:
    def test_without_orchestrator_raises_runtime_error(self):
        """无 orchestrator 时 collect 必须抛 RuntimeError（守护分支）。"""
        service = _make_service(orchestrator=None)
        with pytest.raises(RuntimeError, match="Orchestrator not available"):
            service.collect("any_handle")

    def test_collect_returns_host_awaitable(self):
        """有 orchestrator 时 collect 返回 HostAwaitable（非直接 dict）。"""
        orch = _FakeOrchestrator(result={"count": 7})
        service = _make_service(orchestrator=orch)

        result = service.collect("h1")

        assert isinstance(result, HostAwaitable)
        assert isinstance(result, Waitable)  # 结构性满足 Waitable 协议

    def test_host_awaitable_handle_unchanged(self):
        """HostAwaitable.handle 原样保留传入句柄。"""
        orch = _FakeOrchestrator(result={})
        service = _make_service(orchestrator=orch)

        awaitable = service.collect("spawn_task_abc_123")
        assert awaitable.handle == "spawn_task_abc_123"

    def test_host_awaitable_result_delegates_to_request_collect(self):
        """result() 委托 request_collect 取回 dict，并消费 handle。"""
        orch = _FakeOrchestrator(result={"name": "child"})
        service = _make_service(orchestrator=orch)

        awaitable = service.collect("h1")
        assert awaitable.result() == {"name": "child"}
        assert orch.collected_handles == ["h1"]

    def test_host_awaitable_is_done_delegates_to_is_spawn_done(self):
        """is_done 委托 is_spawn_done（非破坏性，不消费 handle）。"""
        orch = _FakeOrchestrator(result={}, done=False)
        service = _make_service(orchestrator=orch)

        awaitable = service.collect("h1")
        assert awaitable.is_done is False
        assert orch.collected_handles == []  # is_done 不消费 handle

    def test_propagates_orchestrator_exception_on_result(self):
        """orchestrator 抛异常时，result() 不吞错，原样向上传播。"""
        orch = _FakeOrchestrator(error=RuntimeError("handle already collected"))
        service = _make_service(orchestrator=orch)

        awaitable = service.collect("duplicate_handle")
        with pytest.raises(RuntimeError, match="already collected"):
            awaitable.result()
"""
tests/runtime/test_runtime_host_collect.py
===========================================

HostService.collect 委托契约测试（area 4，最后一项）。

``HostService.collect`` 是编排者委托的薄包装（``core/runtime/host/service.py``）：
- 无 orchestrator 时抛 ``RuntimeError``（守护分支）
- 有 orchestrator 时委托 ``orchestrator.request_collect(handle)`` 并原样返回结果
- handle 字符串原样透传，不做变换
- orchestrator 抛出的异常向上传播

完整的 spawn→collect 端到端流程由 ``tests/e2e/test_e2e_multi_interpreter.py`` 覆盖；
此处补齐 HostService.collect 这个薄包装自身的守护/委托分支单测。
"""
import pytest

from core.runtime.host.service import HostService


class _FakeOrchestrator:
    """最小 orchestrator 桩：仅实现 request_collect，记录调用。"""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.collected_handles = []

    def request_collect(self, handle):
        self.collected_handles.append(handle)
        if self.error is not None:
            raise self.error
        return self.result


def _make_service(orchestrator=None):
    """构造 HostService，仅注入 orchestrator（collect 只依赖它）。

    orchestrator 经公开 property 注入（与生产路径 set_orchestrator 同步一致）。
    """
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

    def test_delegates_to_orchestrator_and_returns_result(self):
        """有 orchestrator 时委托 request_collect 并原样返回其结果。"""
        expected = {"count": 7, "name": "child"}
        orch = _FakeOrchestrator(result=expected)
        service = _make_service(orchestrator=orch)

        result = service.collect("h1")

        assert result == expected
        assert orch.collected_handles == ["h1"]

    def test_handle_passed_through_unchanged(self):
        """handle 字符串原样透传给 orchestrator，不做路径/格式变换。"""
        orch = _FakeOrchestrator(result={})
        service = _make_service(orchestrator=orch)

        service.collect("spawn_task_abc_123")
        assert orch.collected_handles == ["spawn_task_abc_123"]

    def test_propagates_orchestrator_exception(self):
        """orchestrator 抛异常时，collect 不吞错，原样向上传播。"""
        orch = _FakeOrchestrator(error=RuntimeError("handle already collected"))
        service = _make_service(orchestrator=orch)

        with pytest.raises(RuntimeError, match="already collected"):
            service.collect("duplicate_handle")

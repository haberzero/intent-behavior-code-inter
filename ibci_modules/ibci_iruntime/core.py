"""
ibci_iruntime/core.py

IBIRuntime 内核内省模块插件实现。

提供：
- ``snapshot()``    —— 运行时快照聚合（见 ``core.runtime.observability.snapshot``）
- ``subscribe()``   —— 订阅状态变更事件流（返回 pubsub 订阅端点 subscriber）

通过 KernelRegistry 稳定钩子（get_execution_context）访问当前 EC/VM 执行器，
与 idbg/isys 的懒获取模式一致。
"""
from typing import Any, Optional, TYPE_CHECKING

from core.runtime.frame import get_current_execution_context
from core.runtime.observability.snapshot import snapshot as _snapshot_aggregate
from core.runtime.observability.events import EventBus
from core.runtime.observability.config import ConfigStore, DEFAULT_CONFIG
from core.runtime.shared.comm.channel import ChannelCore


class IRuntimeLib:
    """IBCI 运行时内省模块（snapshot / subscribe）。"""

    def __init__(self):
        pass

    def setup(self, capabilities) -> None:
        # 事件总线统一挂在 runtime_context（rc.get_event_bus()），无模块级总线。
        pass

    # ------------------------------------------------------------------
    # 内省
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """获取当前运行时快照（tasks/channels/slots/vms/vars/llm）。"""
        ec = get_current_execution_context()
        if ec is None:
            raise RuntimeError("runtime.snapshot: no execution context available")
        executor = ec.vm_executor
        if executor is None:
            raise RuntimeError(
                "runtime.snapshot: vm_executor not available "
                "(interpreter not yet prepared)"
            )
        return _snapshot_aggregate(executor)

    def subscribe(self) -> Any:
        """订阅运行时状态变更事件流。

        返回一个 pubsub 订阅端点（``subscriber``，IbSubscriber），事件 dict 逐个
        推入其独立队列；``close()`` = 干净退订（与 ``c.subscribe()`` 同一惯用法，
        消 monkeypatch）。事件总线为引擎级共享 pubsub 通道（registry 承载）。
        """
        from core.runtime.objects.kernel import IbSubscriber

        ec = get_current_execution_context()
        if ec is None:
            raise RuntimeError("runtime.subscribe: no execution context available")
        registry = ec.registry
        rc = ec.runtime_context

        event_bus = self._get_event_bus(rc)
        view = event_bus.subscribe()

        # 构造语言层 IbSubscriber（包装 pubsub 订阅者视图）
        sub_cls = registry.get_class("subscriber")
        subscriber = IbSubscriber._create_blank(sub_cls)
        subscriber.view = view
        return subscriber

    # ------------------------------------------------------------------
    # 控制层
    # ------------------------------------------------------------------

    def configure(self, *args, **kwargs) -> "Any":
        """统一启停接口：``runtime.configure(parallel=, stream=, observability=, debug=)``。

        粒度链式覆盖（设计 §五.2）：
        - 全局（默认）：``runtime.configure(parallel=False)``
        - 单实例：``runtime.configure(instance="child", observability=False)``
        - 单调用：``runtime.configure(task=<handle>, stream=False)``

        变更经 ``config_change`` 事件广播（observability 开启时）。
        返回配置后的生效值 dict。
        """
        ec = get_current_execution_context()
        if ec is None:
            raise RuntimeError("runtime.configure: no runtime context available")
        rc = ec.runtime_context

        store = self._get_config_store(rc)

        # 解析作用域定位参数（instance=/task=），其余为键值配置
        instance_id = kwargs.pop("instance", None)
        call_key = kwargs.pop("task", None)

        # 位置参数支持 dict（configure({"parallel": False})）
        if args and isinstance(args[0], dict):
            for k, v in args[0].items():
                self._apply_config(store, k, v, instance_id, call_key)
            kwargs = {}

        changed: Dict[str, bool] = {}
        for key, value in kwargs.items():
            if key not in DEFAULT_CONFIG:
                continue
            self._apply_config(store, key, value, instance_id, call_key)
            changed[key] = bool(value)

        # 广播 config_change 事件（observability 开启时）
        if changed and store.get("observability", instance_id, call_key):
            bus = self._get_event_bus(rc)
            bus.emit({"type": "configured", "data": {"changes": changed}})

        effective = {k: store.get(k, instance_id, call_key) for k in DEFAULT_CONFIG}
        return effective

    def get_config(self) -> dict:
        """读取当前生效配置（全局视角）。"""
        ec = get_current_execution_context()
        if ec is None:
            # 无活跃执行上下文时返回默认配置（读默认值的合理空态，非静默异常）
            return dict(DEFAULT_CONFIG)
        store = self._get_config_store(ec.runtime_context)
        return {k: store.get(k) for k in DEFAULT_CONFIG}

    @staticmethod
    def _apply_config(store: ConfigStore, key: str, value: Any, instance_id: Optional[str], call_key: Optional[str]) -> None:
        """按作用域应用单条配置（后者优先：instance > call > global）。"""
        if instance_id is not None:
            store.set_instance(str(instance_id), key, bool(value))
        elif call_key is not None:
            store.set_call(str(call_key), key, bool(value))
        else:
            store.set_global(key, bool(value))

    @staticmethod
    def _get_config_store(rc: Any) -> ConfigStore:
        """获取（或惰性创建）runtime_context 关联的配置存储（公开访问器）。"""
        return rc.get_config_store()

    # ------------------------------------------------------------------
    # 内部：事件总线访问（挂在 runtime_context 上，与 CommRegistry 同级）
    # ------------------------------------------------------------------

    @staticmethod
    def _get_event_bus(rc: Any) -> EventBus:
        """获取（或惰性创建）runtime_context 关联的事件总线（公开访问器）。"""
        return rc.get_event_bus()

    # ------------------------------------------------------------------
    # 内部：供运行时事件源 emit（协调器/VM/CommRegistry 接入点）
    # ------------------------------------------------------------------

    def emit_event(self, event_type: str, data: Optional[dict] = None) -> None:
        """向事件总线广播一个事件（供运行时事件源调用）。

        观测尽力而为：无活跃 EC 或事件总线未注入（独立 registry）时跳过，
        不阻断调用方（与 ``emit_runtime_event`` 同一 fail-open 语义）。
        """
        ec = get_current_execution_context()
        rc = getattr(ec, "runtime_context", None) if ec is not None else None
        if rc is None:
            return
        bus = rc.peek_event_bus()
        if bus is None:
            return
        bus.emit({"type": event_type, "data": data or {}})


def create_implementation():
    return IRuntimeLib()

"""
core.runtime.vm.handlers.comm — 并发/通信 AST 节点的 CPS handler。

覆盖（运行时多线程主线 PT-MT-*）：
- ``IbChannelExpr``  → 构造 ``IbChannel``（语言层 Channel 值对象）
- ``IbSignalExpr``   → 构造 ``IbSignal``（控制流信号值对象）
- ``IbSlotExpr``     → 构造 ``IbSlot``（共享状态槽值对象）
- ``_get_coordinator`` → 获取线程协调器（thread 构造共享）
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from core.runtime.objects.kernel import IbChannel, IbSignal, IbSlot, IbClass, IbUserFunction, IbValue
from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.signal import SignalCore
from core.runtime.shared.comm.slot import SlotCore
from core.runtime.shared.comm.registry import CommRegistry


def _get_comm_registry(executor) -> CommRegistry:
    """获取（或惰性创建）执行器关联的通信注册表。

    注册表挂在 execution_context 上（runtime_context 侧），供广播枚举 / 定向
    查找 / 内省。多个 VM 实例各持一份（per-task 隔离）。
    """
    rc = executor.runtime_context
    reg = getattr(rc, "_comm_registry", None)
    if reg is None:
        reg = CommRegistry()
        try:
            rc._comm_registry = reg
        except Exception:
            pass
    return reg


def _get_coordinator(executor) -> Any:
    """获取（或惰性创建）执行器关联的 RuntimeCoordinator。

    挂在 runtime_context 上（与 CommRegistry 同级）。thread 构造共享。
    """
    from core.runtime.coordinator import RuntimeCoordinator

    rc = executor.runtime_context
    coord = getattr(rc, "_runtime_coordinator", None)
    if coord is None:
        interpreter = getattr(executor, "_interpreter", None)
        coord = RuntimeCoordinator(interpreter)
        try:
            rc._runtime_coordinator = coord
        except Exception:
            pass
    return coord


def _emit_event(executor, event_type: str, data: Optional[dict] = None) -> None:
    """向 runtime_context 上的事件总线广播事件（PT-MT-4 内省事件流）。

    受控制层 observability 开关约束（PT-MT-5）：关闭时跳过事件记录。
    无订阅者时为空操作；事件总线失败不阻断执行（可观测性层尽力而为）。
    """
    rc = executor.runtime_context
    store = getattr(rc, "_comm_config_store", None)
    if store is not None:
        try:
            if not store.get("observability"):
                return
        except Exception:
            pass
    bus = getattr(rc, "_comm_event_bus", None)
    if bus is None:
        return
    try:
        bus.emit({"type": event_type, "data": data or {}})
    except Exception:
        pass


def vm_handle_IbChannelExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``chan(T, mode=..., buffer=...)`` 构造 Channel 值对象。"""
    if False:
        yield  # 保持生成器身份（VM CPS 契约：handler 必须为 generator）
    mode = node_data.get("mode", "message")
    buffer = node_data.get("buffer", 0)
    name = node_data.get("name")
    core = ChannelCore(mode=mode, buffer=buffer, name=name)
    cls = executor.registry.get_class("chan")
    obj = IbChannel(ib_class=cls, core=core)
    if name:
        _get_comm_registry(executor).register(name, obj, "chan")
    _emit_event(executor, "chan_created", {"name": name, "mode": mode})
    return obj


def vm_handle_IbSignalExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``signal(kind, target=..., payload=...)`` 构造 Signal 值对象。"""
    kind = node_data.get("kind", "cancel")
    target = None
    if node_data.get("target"):
        target = yield node_data["target"]
    payload = None
    if node_data.get("payload"):
        payload = yield node_data["payload"]
    core = SignalCore(kind=kind, target=target, payload=payload)
    cls = executor.registry.get_class("signal")
    return IbSignal(ib_class=cls, core=core)


def vm_handle_IbSlotExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``slot(name, value)`` 构造 Slot 值对象。"""
    name = node_data.get("name", "")
    value = None
    if node_data.get("value"):
        value = yield node_data["value"]
    core = SlotCore(name=name, initial_value=value)
    cls = executor.registry.get_class("slot")
    obj = IbSlot(ib_class=cls, core=core)
    if name:
        _get_comm_registry(executor).register(name, obj, "slot")
    _emit_event(executor, "slot_updated", {"name": name, "value": value})
    return obj

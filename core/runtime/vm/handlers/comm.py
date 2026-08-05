"""
core.runtime.vm.handlers.comm — 并发/通信 AST 节点的 CPS handler。

覆盖：
- ``IbChannelExpr``  → 构造 ``IbChannel``（语言层 Channel 值对象）
- ``IbSlotExpr``     → 构造 ``IbSlot``（共享状态槽值对象）

线程协调器访问器（``get_runtime_coordinator``）已移入线程领域模块
``core/runtime/coordinator.py``（不再寄居通信模块）。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from core.runtime.objects.kernel import IbChannel, IbSlot
from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.slot import SlotCore
from core.runtime.shared.comm.registry import CommRegistry


def _get_comm_registry(executor) -> CommRegistry:
    """获取（或惰性创建）执行器关联的通信注册表。

    注册表挂在 execution_context 上（runtime_context 侧），供广播枚举 / 定向
    查找 / 内省。多个 VM 实例各持一份（per-task 隔离）。
    """
    rc = executor.runtime_context
    reg = rc._comm_registry
    if reg is None:
        reg = CommRegistry()
        # fail-fast：runtime_context 为 RuntimeContextImpl（无 __slots__），
        # setattr 恒成功；若失败（如无 runtime_context）说明构造路径有误，必须显式暴露。
        rc._comm_registry = reg
    return reg


def _emit_event(executor, event_type: str, data: Optional[dict] = None) -> None:
    """向 runtime_context 上的事件总线广播事件（内省事件流）。

    受控制层 observability 开关约束：关闭时跳过事件记录。
    无订阅者时为空操作；事件总线失败不阻断执行（可观测性层尽力而为）。
    """
    rc = executor.runtime_context
    store = rc._comm_config_store
    if store is not None:
        try:
            if not store.get("observability"):
                return
        except Exception:
            pass
    bus = rc._comm_event_bus
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
    # 经 _create_blank 统一构造协议创建实例（与 thread instantiate 入口同构）
    obj = IbChannel._create_blank(cls)
    obj.core = core
    if name:
        _get_comm_registry(executor).register(name, obj, "chan")
    _emit_event(executor, "chan_created", {"name": name, "mode": mode})
    return obj


def vm_handle_IbSlotExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``slot(name, value)`` 构造 Slot 值对象。"""
    name = node_data.get("name", "")
    value = None
    if node_data.get("value"):
        value = yield node_data["value"]
    core = SlotCore(name=name, initial_value=value)
    cls = executor.registry.get_class("slot")
    # 经 _create_blank 统一构造协议创建实例（与 thread instantiate 入口同构）
    obj = IbSlot._create_blank(cls)
    obj.core = core
    if name:
        _get_comm_registry(executor).register(name, obj, "slot")
    _emit_event(executor, "slot_updated", {"name": name, "value": value})
    return obj

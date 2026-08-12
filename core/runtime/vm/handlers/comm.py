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
from core.runtime.observability.events import emit_runtime_event


def _get_comm_registry(executor) -> CommRegistry:
    """获取（或惰性创建）执行器关联的通信注册表。

    注册表挂在 execution_context 上（runtime_context 侧，经公开访问器惰性
    创建），供广播枚举 / 定向查找 / 内省。多个 VM 实例各持一份（per-task 隔离）。
    """
    return executor.runtime_context.get_comm_registry()


def _emit_event(executor, event_type: str, data: Optional[dict] = None) -> None:
    """经统一发射入口向 runtime_context 事件总线广播事件（见 emit_runtime_event）。"""
    emit_runtime_event(executor.runtime_context, event_type, data)


def vm_handle_IbChannelExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``chan(T, mode=..., buffer=...)`` 构造 Channel 值对象。"""
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

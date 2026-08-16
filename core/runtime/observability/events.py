"""
core.runtime.observability.events — 事件流（事件总线 + 统一发射入口）。

``runtime.subscribe()`` 返回一个 pubsub 订阅端点（``subscriber``），运行时事件
推入其中。事件总线（``EventBus``）**复用 ``ChannelCore`` pubsub 模式**——机制
同构：``emit`` = ``send`` 扇出到全部订阅者缓冲；``subscribe()``
返回订阅者端点（``close`` = 干净退订），与用户通道 ``c.subscribe()`` 同一惯用法，
无自定义 sink 注册表、无 monkeypatch 退订。事件类型是数据，不是分发条件。

事件类型清单：llm_dispatched / llm_resolved /
chan_created / slot_updated / configured / kernel_diagnostic。
``kernel_diagnostic`` 为诊断面事件（异常/降级/策略），经
``core.runtime.observability.diagnostics.kernel_diagnostic`` 发射。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.buffer import CommClosedError


# ------------------------------------------------------------------ #
# 事件总线（复用 ChannelCore pubsub，引擎级单实例）                    #
# ------------------------------------------------------------------ #

class EventBus:
    """事件总线：pubsub 通道（线程安全，无订阅者零成本）。

    - ``emit(event)`` = ``send(event)``，扇出到全部订阅者缓冲（无订阅者为空操作）；
    - ``subscribe()`` 返回 ``_SubscriberView``（``close`` = 干净退订）；
    - 与用户通道 ``c.subscribe()`` 同一惯用法（机制同构）。
    """

    def __init__(self):
        self._channel = ChannelCore(mode="pubsub", name="runtime_events")

    def emit(self, event: Dict[str, Any]) -> None:
        try:
            self._channel.send(event)
        except CommClosedError:
            pass  # 总线已关闭：忽略（可观测性层尽力而为）

    def subscribe(self) -> Any:
        """订阅事件流，返回 pubsub 订阅者端点（``_SubscriberView``）。"""
        return self._channel.subscribe()

    @property
    def subscriber_count(self) -> int:
        return self._channel.subscriber_count


def emit_runtime_event(rc: Any, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
    """统一事件发射入口（observability 门控 + 事件总线广播，尽力而为）。

    经 runtime_context 公开访问器取配置存储与事件总线：
    - 受控制层 ``observability`` 开关约束（关闭时跳过）；
    - 无订阅者为空操作；
    - 事件记录失败不阻断执行（可观测性层尽力而为）；
    - 仅读取存在性（``peek_*``），不因事件记录而创建存储/总线。

    供 VM handlers（chan/slot）、LLM 执行器（llm_dispatched/llm_resolved）等
    内核事件源统一调用，消除各点各自内联的发射逻辑。
    """
    try:
        store = rc.peek_config_store()
        if store is not None and not store.get("observability"):
            return
    except Exception:
        return
    bus = rc.peek_event_bus()
    if bus is None:
        return
    try:
        bus.emit({"type": event_type, "data": data or {}})
    except Exception:
        pass

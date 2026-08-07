"""
core.runtime.observability.events — 事件流（EventSource 协议 + 事件总线）。

``runtime.subscribe()`` 返回一个 mode=stream 的 Channel，运行时状态变更事件
推入其中。事件源（协调器/VM/CommRegistry）统一实现 ``EventSource`` 协议，
经事件总线把事件 ``send`` 到订阅者 Channel（协议驱动，禁止在运行流程里写
``if 事件类型`` 硬编码分发——事件类型是数据，不是分发条件）。

事件类型（设计 §四.2）：task_started / task_done / task_cancelled /
chan_created / chan_closed / slot_updated / llm_dispatched / llm_resolved /
vm_spawned / vm_terminated / configured。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.buffer import CommClosedError


# ------------------------------------------------------------------ #
# EventSource 协议                                                    #
# ------------------------------------------------------------------ #

class EventSource(Protocol):
    """事件源协议：可被事件总线订阅/退订。"""

    def attach(self, sink: "EventSink") -> None: ...
    def detach(self, sink: "EventSink") -> None: ...


class EventSink(Protocol):
    """事件接收协议：收到事件 dict。"""

    def emit(self, event: Dict[str, Any]) -> None: ...


# ------------------------------------------------------------------ #
# 事件                                                                 #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class RuntimeEvent:
    """运行时事件（不可变值对象）。

    ``type`` 为事件类型字符串；``data`` 为事件负载。
    """

    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "data": self.data}


# ------------------------------------------------------------------ #
# 事件总线                                                            #
# ------------------------------------------------------------------ #

class EventBus:
    """事件总线：维护订阅者（EventSink）集合，广播事件。线程安全。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._sinks: List[EventSink] = []

    def attach(self, sink: EventSink) -> None:
        with self._lock:
            if sink not in self._sinks:
                self._sinks.append(sink)

    def detach(self, sink: EventSink) -> None:
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    def emit(self, event: Dict[str, Any]) -> None:
        """广播事件到所有订阅者（快照当前订阅者集合，锁外分发避免持锁回调）。"""
        with self._lock:
            sinks = list(self._sinks)
        for sink in sinks:
            try:
                sink.emit(event)
            except Exception:
                # 单个订阅者失败不应拖垮事件总线；异常吞掉并继续（可观测性层）。
                continue

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._sinks)


class ChannelSink:
    """把事件推入 mode=stream Channel 的 EventSink（runtime.subscribe 的载体）。"""

    def __init__(self, channel: ChannelCore):
        self._channel = channel

    @property
    def channel(self) -> ChannelCore:
        return self._channel

    def emit(self, event: Dict[str, Any]) -> None:
        try:
            self._channel.send(event)
        except CommClosedError:
            # Channel 已关闭 → 订阅者已退订，忽略
            pass

    def close(self) -> None:
        self._channel.close()


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
        store = rc.peek_comm_config_store()
        if store is not None and not store.get("observability"):
            return
    except Exception:
        return
    bus = rc.peek_comm_event_bus()
    if bus is None:
        return
    try:
        bus.emit({"type": event_type, "data": data or {}})
    except Exception:
        pass

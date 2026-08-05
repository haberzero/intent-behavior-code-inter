"""
core.runtime.shared.comm.channel — Channel 数据流核心。

mode:
- stream:  有序 FIFO 流（与 CommBuffer 一致），生产-消费
- message: 离散消息队列（与 CommBuffer 一致），点对点排队
- pubsub:  扇出（同一消息投递所有订阅者）；内部每个订阅者一个 CommBuffer

多生产者 / 多消费者安全。语言层 ``IbChannel`` 在 ``core/runtime/objects/``
包装本核心并向 IBCI 代码暴露 send/recv/close 等方法。
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .buffer import CommBuffer, CommClosedError


class ChannelCore:
    """Channel 数据流核心（纯通信原语，线程安全）。

    - ``send`` / ``send_nowait``：生产者投递数据。
    - ``recv`` / ``recv_nowait``：消费者取数据。
    - pubsub 模式：``subscribe()`` 返回订阅者专属队列视图；``send`` 扇出到
      所有订阅者队列（每个订阅者独立消费，互不竞争）。
    - ``close``：关闭；所有订阅者队列一并关闭。
    """

    def __init__(self, mode: str = "message", buffer: int = 0, name: Optional[str] = None):
        if mode not in ("stream", "message", "pubsub"):
            raise ValueError(f"Invalid channel mode: {mode!r} (expect stream/message/pubsub)")
        self._mode = mode
        self._name = name
        self._lock = threading.Lock()
        if mode == "pubsub":
            # 订阅者注册表：id -> CommBuffer（锁内读写）
            self._subscribers: Dict[int, CommBuffer] = {}
            self._next_sub_id: int = 0
            self._primary: Optional[CommBuffer] = None  # 非 pubsub 模式使用
        else:
            self._primary = CommBuffer(buffer)
            self._subscribers = None  # type: ignore[assignment]

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def name(self) -> Optional[str]:
        return self._name

    # ------------------------------------------------------------------ #
    # 生产者                                                            #
    # ------------------------------------------------------------------ #

    def send(self, item: Any) -> None:
        """阻塞发送（模式无关）。已关闭抛 ``CommClosedError``。

        R1-D3 修复：pubsub fan-out 对订阅者快照逐 buffer ``send``，若某订阅者
        在快照后并发 ``close()``（buffer 已关、尚未从 ``_subscribers`` 移除），
        ``CommClosedError`` 会从该订阅者泄漏给生产者——修复为捕获并跳过单个
        已关闭订阅者（与 ``send_nowait`` 对已关订阅者返回 False 的语义对齐），
        消息仍投递给其余存活订阅者。通道整体关闭仍抛 ``CommClosedError``。
        """
        if self._mode == "pubsub":
            with self._lock:
                if self._closed_flag():
                    raise CommClosedError()
                subscribers = list(self._subscribers.values())
            for sub in subscribers:
                try:
                    sub.send(item)
                except CommClosedError:
                    continue
            return
        if self._primary is None:
            raise CommClosedError()
        self._primary.send(item)

    def send_nowait(self, item: Any) -> bool:
        """非阻塞发送。False = 满/已关闭。pubsub 下任一订阅者满即 False。

        G7 语义修正：pubsub 无订阅者时返回 ``False``（消息未投递给任何人，
        与 message/stream 模式 "False=拒绝" 契约对齐——不再把"被零人接收"
        报告为投递成功）。

        N>1 订阅者语义边界（R1 复核确认，D2）：多订阅者且部分满时返回
        ``False``，但消息已投递给先序的未满订阅者——``False`` 表示"未全量
        投递"而非"整条被拒"。调用方须据此解读（对广播结果敏感的路径应在
        投递前先确认所有订阅者未满）。
        """
        if self._mode == "pubsub":
            with self._lock:
                if self._closed_flag():
                    return False
                subscribers = list(self._subscribers.values())
            if not subscribers:
                return False
            ok = True
            for sub in subscribers:
                if not sub.send_nowait(item):
                    ok = False
            return ok
        if self._primary is None:
            return False
        return self._primary.send_nowait(item)

    # ------------------------------------------------------------------ #
    # 消费者                                                            #
    # ------------------------------------------------------------------ #

    def recv(self) -> Any:
        """阻塞接收。已关闭且空抛 ``CommClosedError``。

        G7：pubsub 通道是广播器（无主缓冲），消费须经 ``subscribe()`` 取得
        订阅者端点——直接 recv 属用法错误，明确报错而非误导性的 CommClosedError。
        """
        if self._mode == "pubsub":
            raise ValueError(
                "recv() is invalid for pubsub channels: use subscribe() "
                "to obtain a subscriber consumer endpoint"
            )
        if self._primary is None:
            raise CommClosedError()
        return self._primary.recv()

    def recv_nowait(self):
        """非阻塞接收，返回 ``(ok, item)``。pubsub 通道同 recv 用法约束。"""
        if self._mode == "pubsub":
            raise ValueError(
                "recv_nowait() is invalid for pubsub channels: use subscribe() "
                "to obtain a subscriber consumer endpoint"
            )
        if self._primary is None:
            return False, None
        return self._primary.recv_nowait()

    def subscribe(self, size: int = 0) -> "_SubscriberView":
        """pubsub 模式：返回订阅者专属队列视图（fan-out）。

        ``size``：订阅者队列容量（G7——``可配置`` 落地；0=无界，>0 有界，
        满时 ``send_nowait`` 返回 False）。订阅者队列无失效/驱逐机制，
        有界模式由消费方及时 ``recv`` 防积压；无界模式是广播信箱的设计选择，
        调用方须自行保证消费速率。

        非 pubsub 模式调用抛 ``ValueError``（subscribe 是 pubsub 专用）。
        """
        if self._mode != "pubsub":
            raise ValueError(
                f"subscribe() is only valid for pubsub channels, got mode={self._mode!r}"
            )
        with self._lock:
            if self._closed_flag():
                raise CommClosedError()
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            sub = CommBuffer(size)
            self._subscribers[sub_id] = sub
            return _SubscriberView(self, sub, sub_id)

    def unsubscribe(self, sub_id: int) -> None:
        """移除订阅者（内部供 _SubscriberView 调用）。"""
        with self._lock:
            self._subscribers.pop(sub_id, None)

    # ------------------------------------------------------------------ #
    # 生命周期 / 内省                                                   #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """关闭通道：主缓冲与所有订阅者缓冲一并关闭。幂等。

        R1-D4 修复：pubsub 下关闭全部订阅者 buffer 后**一并清空**
        ``_subscribers``——此前仅关 buffer 不移出注册表，导致
        ``snapshot()["subscriber_count"]`` 在通道关闭后仍计入已关闭订阅者
        （内省与"已关"状态不一致）。清空后 subscriber_count 如实反映 0。
        """
        with self._lock:
            if self._closed_flag():
                return
            self._closed = True  # type: ignore[attr-defined]
            if self._mode == "pubsub":
                for sub in self._subscribers.values():
                    sub.close()
                self._subscribers.clear()
            elif self._primary is not None:
                self._primary.close()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed_flag()

    def _closed_flag(self) -> bool:
        """锁内调用的 closed 判断（两种模式统一）。"""
        if self._mode == "pubsub":
            return getattr(self, "_closed", False)
        return self._primary is None or self._primary.closed

    def snapshot(self) -> dict:
        """内省快照。"""
        with self._lock:
            if self._mode == "pubsub":
                return {
                    "mode": self._mode,
                    "name": self._name,
                    "subscriber_count": len(self._subscribers),
                    "closed": getattr(self, "_closed", False),
                }
            return {
                "mode": self._mode,
                "name": self._name,
                **self._primary.snapshot(),
            }


class _SubscriberView:
    """pubsub 订阅者专属队列视图（包装单个 CommBuffer）。

    经 ``recv`` / ``recv_nowait`` / ``close`` 暴露订阅者侧消费语义。
    """

    def __init__(self, channel: ChannelCore, buffer: CommBuffer, sub_id: int):
        self._channel = channel
        self._buffer = buffer
        self._sub_id = sub_id

    def recv(self) -> Any:
        return self._buffer.recv()

    def recv_nowait(self):
        return self._buffer.recv_nowait()

    def close(self) -> None:
        self._buffer.close()
        self._channel.unsubscribe(self._sub_id)

    @property
    def closed(self) -> bool:
        return self._buffer.closed

    def snapshot(self) -> dict:
        return self._buffer.snapshot()

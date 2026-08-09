"""
core.runtime.shared.comm.buffer — 线程安全有界缓冲（统一内核地基）。

多生产者 / 多消费者安全（threading.Condition 保护）；有界（maxsize）：
满时 send 阻塞或返回 False（send_nowait）；空时 recv 阻塞或返回
(False, None)（recv_nowait）。close() 后 send 抛 ClosedError、recv 排空
剩余后抛 ClosedError。
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Optional


class CommClosedError(RuntimeError):
    """通信对象已关闭后仍执行 send/recv 的失败。"""

    def __init__(self, what: str = "communication object"):
        super().__init__(f"{what} is closed")


class CommBuffer:
    """线程安全有界缓冲（统一内核）。

    - 多生产者/多消费者安全（单一 ``threading.Condition`` 保护内部队列）。
    - 有界（maxsize）：满时 ``send`` 阻塞或 ``send_nowait`` 返回 False。
    - 空时 ``recv`` 阻塞或 ``recv_nowait`` 返回 ``(False, None)``。
    - ``close()``：置 closed 并唤醒所有等待者；``send`` 抛 ``CommClosedError``；
      ``recv`` 排空剩余后抛 ``CommClosedError``。

    正确性要点：单一锁保护 ``_queue`` + ``_closed``，所有
    读改写原子；不持锁调用外部代码（send/recv 只操作内部队列，不回调用户代码），
    避免死锁。
    """

    def __init__(self, maxsize: int = 0):
        if maxsize < 0:
            raise ValueError(f"maxsize must be >= 0, got {maxsize}")
        self._maxsize = maxsize
        self._queue: deque = deque()
        self._closed = False
        self._cond = threading.Condition(threading.Lock())
        # R2 通知式唤醒回调表：recv waitable 经 register_wake 注册，
        # send/close 时触发（通知调度器即时唤醒，与 Condition 平行）。
        self._wake_callbacks: list = []
        # send waitable 经 register_send_wake 注册，
        # recv/close 腾出空间时触发（与 recv 唤醒对称，消除满通道真阻塞）。
        self._send_wake_callbacks: list = []

    # ------------------------------------------------------------------ #
    # R2 通知式唤醒（调度器即时唤醒，与 Condition 平行）                  #
    # ------------------------------------------------------------------ #

    def register_wake(self, event) -> None:
        """把完成通知注册到 ``event``：send/close 时设置（可跨线程）。

        供 ``ChannelRecvWaitable`` 委托——调度器等待通道 recv 时注册，数据
        到达或通道关闭即唤醒，消除 ~1ms 轮询延迟。
        """
        with self._cond:
            if self._queue or self._closed:
                event.set()
                return
            self._wake_callbacks.append(event)

    def register_send_wake(self, event) -> None:
        """把发送完成通知注册到 ``event``：recv/close 腾出空间时设置（可跨线程）。

        供 ``ChannelSendWaitable`` 委托——调度器等待满通道 send 时注册，
        消费者取走数据腾出空间（或通道关闭）即唤醒，消除满通道真阻塞。
        """
        with self._cond:
            if self._maxsize == 0 or len(self._queue) < self._maxsize or self._closed:
                event.set()
                return
            self._send_wake_callbacks.append(event)

    def _notify_wake(self) -> None:
        """触发全部完成通知（send 有新数据 / close 置关闭态时调用）。

        调用方须已持有 ``_cond``（与 ``_cond.notify()`` 同模式）；事件集合
        清空后回调可安全触发（``threading.Event.set`` 无锁需求）。
        """
        if not self._wake_callbacks:
            return
        callbacks, self._wake_callbacks = self._wake_callbacks, []
        for ev in callbacks:
            ev.set()

    def _notify_send_wake(self) -> None:
        """触发全部发送完成通知（recv 腾出空间 / close 置关闭态时调用）。

        与 ``_notify_wake`` 平行（调用方须已持有 ``_cond``）；唤醒等待
        满通道 send 的调度器。
        """
        if not self._send_wake_callbacks:
            return
        callbacks, self._send_wake_callbacks = self._send_wake_callbacks, []
        for ev in callbacks:
            ev.set()

    # ------------------------------------------------------------------ #
    # 生产者                                                            #
    # ------------------------------------------------------------------ #

    def send(self, item: Any) -> None:
        """阻塞发送。已关闭则抛 ``CommClosedError``。"""
        with self._cond:
            if self._closed:
                raise CommClosedError()
            while self._maxsize and len(self._queue) >= self._maxsize:
                self._cond.wait()
                if self._closed:
                    raise CommClosedError()
            self._queue.append(item)
            self._cond.notify()  # 唤醒一个等待 recv 的消费者
            self._notify_wake()  # R2：通知调度器即时唤醒（新数据到达）

    def send_nowait(self, item: Any) -> bool:
        """非阻塞发送。返回 False 表示满或已关闭（不抛）。"""
        with self._cond:
            if self._closed:
                return False
            if self._maxsize and len(self._queue) >= self._maxsize:
                return False
            self._queue.append(item)
            self._cond.notify()
            self._notify_wake()  # R2：通知调度器即时唤醒（新数据到达）
            return True

    def send_waitable(self, item: Any) -> "ChannelSendWaitable":
        """返回发送 Waitable（满时挂起，统一执行地基 · 阻塞即挂起）。

        与 ``recv_waitable`` 对称：调度器任务经 ``try_result`` 非阻塞投递
        （满则 ``(False, None)`` 重轮询），宿主/线程体经 ``result()`` 阻塞投递。
        已关闭则抛 ``CommClosedError``。
        """
        from .send_waitable import ChannelSendWaitable

        with self._cond:
            if self._closed:
                raise CommClosedError()
        return ChannelSendWaitable(self, item)

    # ------------------------------------------------------------------ #
    # 消费者                                                            #
    # ------------------------------------------------------------------ #

    def recv(self) -> Any:
        """阻塞接收。已关闭且队列空则抛 ``CommClosedError``。"""
        with self._cond:
            while not self._queue:
                if self._closed:
                    raise CommClosedError()
                self._cond.wait()
            item = self._queue.popleft()
            self._cond.notify()  # 唤醒等待 send 的生产者
            self._notify_send_wake()  # B1：腾出空间，唤醒满通道 send 的调度器
            return item

    def recv_nowait(self):
        """非阻塞接收。返回 ``(ok, item)``；空或已关闭返回 ``(False, None)``。"""
        with self._cond:
            if not self._queue:
                return False, None
            item = self._queue.popleft()
            self._cond.notify()
            self._notify_send_wake()  # B1：腾出空间，唤醒满通道 send 的调度器
            return True, item

    def peek_nowait(self) -> Any:
        """非破坏性窥视队首（不消费）。空或已关闭返回 None。

        用于内省（snapshot）；不保证与后续 recv 的一致性（队首可能被并发消费）。
        """
        with self._cond:
            if not self._queue:
                return None
            return self._queue[0]

    # ------------------------------------------------------------------ #
    # 生命周期 / 内省                                                   #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """关闭缓冲：唤醒所有阻塞的 send/recv。幂等。"""
        with self._cond:
            if self._closed:
                return
            self._closed = True
            self._cond.notify_all()
            self._notify_wake()  # R2：通知调度器即时唤醒（通道已关闭）
            self._notify_send_wake()  # B1：满通道 send 也被唤醒（关闭即终态）

    @property
    def closed(self) -> bool:
        with self._cond:
            return self._closed

    @property
    def qsize(self) -> int:
        with self._cond:
            return len(self._queue)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def snapshot(self) -> dict:
        """内省快照（无锁一致性：单锁内取切片）。"""
        with self._cond:
            return {
                "qsize": len(self._queue),
                "maxsize": self._maxsize,
                "closed": self._closed,
            }

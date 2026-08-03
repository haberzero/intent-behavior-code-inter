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

    正确性要点（设计 §8.1 C1）：单一锁保护 ``_queue`` + ``_closed``，所有
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

    def send_nowait(self, item: Any) -> bool:
        """非阻塞发送。返回 False 表示满或已关闭（不抛）。"""
        with self._cond:
            if self._closed:
                return False
            if self._maxsize and len(self._queue) >= self._maxsize:
                return False
            self._queue.append(item)
            self._cond.notify()
            return True

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
            return item

    def recv_nowait(self):
        """非阻塞接收。返回 ``(ok, item)``；空或已关闭返回 ``(False, None)``。"""
        with self._cond:
            if not self._queue:
                return False, None
            item = self._queue.popleft()
            self._cond.notify()
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

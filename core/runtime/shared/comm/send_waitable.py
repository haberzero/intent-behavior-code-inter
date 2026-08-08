"""
core.runtime.shared.comm.send_waitable — 通信发送的 Waitable 投影。

把 ``CommBuffer`` 的阻塞 send 以 :class:`core.runtime.shared.waitable.Waitable`
协议暴露：调度器任务经 ``try_result()`` 非阻塞投递（或探测空间就绪），
宿主/线程体经 ``result()`` 阻塞投递。与 ``ChannelRecvWaitable`` 对称
（统一执行地基 · 阻塞即挂起）——有界满通道的生产侧不再同步阻塞线程，
而是挂起纳入统一调度地基，消除"唯一消费者同调度器时死锁"。
"""

from __future__ import annotations

from typing import Any, Tuple

from core.runtime.shared.comm.buffer import CommBuffer, CommClosedError


class ChannelSendWaitable:
    """``CommBuffer`` 的发送 Waitable（单生产投递）。

    - ``is_done``：缓冲有空间 或 通道已关闭（非阻塞探测）。
    - ``try_result()``：非阻塞投递一项 → ``(True, None)``；满 → ``(False, None)``；
      已关闭 → 抛 ``CommClosedError``（终态错误，调度器 throw 进任务）。
    - ``result()``：阻塞投递一项（复用 CommBuffer 语义；已关闭抛 CommClosedError）。

    投递契约：本 waitable 持有**待投递项**（构造时确定），``try_result``
    成功即消费该项（投递一次）；未就绪重试不重复投递。
    """

    def __init__(self, buffer: CommBuffer, item: Any):
        self._buffer = buffer
        self._item = item

    @property
    def is_done(self) -> bool:
        return self._buffer.maxsize == 0 or self._buffer.qsize < self._buffer.maxsize or self._buffer.closed

    def try_result(self) -> Tuple[bool, Any]:
        if self._buffer.send_nowait(self._item):
            return (True, None)
        if self._buffer.closed:
            raise CommClosedError()
        return (False, None)

    def result(self) -> Any:
        return self._buffer.send(self._item)

    def register_wake(self, event) -> None:
        """完成通知钩子（R2）：委托 ``CommBuffer``——recv/close 腾出空间时设置 ``event``。"""
        self._buffer.register_send_wake(event)
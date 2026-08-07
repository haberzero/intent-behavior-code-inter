"""
core.runtime.shared.comm.recv_waitable — 通信接收的 Waitable 投影。

把 ``CommBuffer`` 的阻塞 recv 以 :class:`core.runtime.shared.waitable.Waitable`
协议暴露：调度器任务经 ``try_result()`` 非阻塞取项（或探测终态关闭），
宿主/线程体经 ``result()`` 阻塞取项。与 LLM/host/stream waitable 同一抽象
（统一执行地基 · 阻塞即挂起）。
"""

from __future__ import annotations

from typing import Any, Tuple

from core.runtime.shared.comm.buffer import CommBuffer, CommClosedError


class ChannelRecvWaitable:
    """``CommBuffer`` 的接收 Waitable（单消费者）。

    - ``is_done``：队列有数据 或 通道已关闭（非阻塞探测）。
    - ``try_result()``：非阻塞取走一项 → ``(True, item)``；未就绪 → ``(False, None)``；
      已关闭且空 → 抛 ``CommClosedError``（终态错误，调度器 throw 进任务）。
    - ``result()``：阻塞取走一项（复用 CommBuffer 语义；空且关闭抛 CommClosedError）。

    消费契约：同一缓冲的 recv 为**单消费者**（stream/message 通道文档化契约；
    pubsub 每个订阅者端点独占自己缓冲）——try_result 的"取走"无竞争；多任务并发
    recv 同一 stream/message 属契约外用法，先到先得、后者重等（try_result 返回
    ``(False, None)`` 不阻塞调度器）。
    """

    def __init__(self, buffer: CommBuffer):
        self._buffer = buffer

    @property
    def is_done(self) -> bool:
        return self._buffer.qsize > 0 or self._buffer.closed

    def try_result(self) -> Tuple[bool, Any]:
        ok, item = self._buffer.recv_nowait()
        if ok:
            return (True, item)
        if self._buffer.closed:
            raise CommClosedError()
        return (False, None)

    def result(self) -> Any:
        return self._buffer.recv()

    def register_wake(self, event) -> None:
        """完成通知钩子（R2）：委托 ``CommBuffer``——send/close 时设置 ``event``。"""
        self._buffer.register_wake(event)

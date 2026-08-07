"""
core.runtime.objects.stream — 流式句柄（IbStreamHandle）。

``IbStreamHandle`` 把 provider 的增量迭代器接入统一 Waitable 协议与
stream Channel：后台线程消费迭代器，逐块 ``send`` 到 Channel，
渲染线程（或 VM）``recv`` 逐块渲染。

- ``is_done``：迭代器已耗尽（完整文本已推入）。
- ``result()``：返回完整拼接文本。
- ``channel``：stream Channel（消费增量）。

线程模型：增量生产（provider 迭代）在后台线程；Channel 本身线程安全
（CommBuffer），消费方任意线程 recv。
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Iterable, Optional

from core.runtime.shared.comm.channel import ChannelCore


class IbStreamHandle:
    """流式增量句柄（Waitable 协议 + stream Channel）。

    ``producer`` 为返回增量迭代器的可调用对象（每次调用新建迭代器）。
    构造时即启动后台线程消费迭代器并推入 Channel；``is_done`` 为 True 时
    完整文本已推入，``result()`` 返回拼接结果。
    """

    def __init__(
        self,
        producer: Callable[[], Iterable[str]],
        channel: Optional[ChannelCore] = None,
    ):
        self._channel = channel if channel is not None else ChannelCore(mode="stream")
        self._producer = producer
        self._done = False
        self._error: Optional[BaseException] = None
        self._full_text: str = ""
        self._lock = threading.Lock()
        # R2 通知式唤醒：注册的完成事件（消费线程 finally 时 set）
        self._wake_events: list = []
        self._thread = threading.Thread(target=self._consume, daemon=True, name="ibci-stream")
        self._thread.start()

    def _consume(self) -> None:
        """后台线程：消费迭代器，逐块推入 Channel。"""
        try:
            for piece in self._producer():
                if piece is None:
                    continue
                self._channel.send(str(piece))
                with self._lock:
                    self._full_text += str(piece)
        except Exception as e:
            self._error = e
        finally:
            with self._lock:
                self._done = True
                wake_events = list(self._wake_events)
            self._channel.close()
            for ev in wake_events:
                ev.set()

    # ------------------------------------------------------------------ #
    # Waitable 协议                                                      #
    # ------------------------------------------------------------------ #

    @property
    def is_done(self) -> bool:
        with self._lock:
            return self._done

    def register_wake(self, event) -> None:
        """完成通知钩子（R2）：流耗尽（``_done`` 置位）时设置 ``event``。"""
        with self._lock:
            if self._done:
                event.set()
                return
            self._wake_events.append(event)

    def try_result(self):
        """非阻塞取回 ``(ok, str)``（调度器专用；不阻塞）。

        ``ok=False`` 表示流未耗尽（调度器重新轮询）；``ok=True`` 消费一次，
        返回完整拼接文本。生产异常在 ``ok=True`` 分支重抛（终态错误）。
        """
        if not self.is_done:
            return (False, None)
        return (True, self.result())

    def result(self) -> str:
        """阻塞等待完整文本并返回；生产异常时重抛。

        Waitable 契约：``result()`` 必须返回完成值（阻塞语义由调用方决定——
        宿主/线程体直接 ``waitable.result()`` 不轮询 ``is_done``，故此处需等待
        线程完成）。
        """
        self._thread.join(timeout=120)
        with self._lock:
            if self._error is not None:
                raise self._error
            return self._full_text

    # ------------------------------------------------------------------ #
    # Channel 消费                                                       #
    # ------------------------------------------------------------------ #

    @property
    def channel(self) -> ChannelCore:
        return self._channel

    def recv_nowait(self):
        """非阻塞消费一个增量块，返回 ``(ok, chunk)``。"""
        return self._channel.recv_nowait()

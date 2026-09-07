"""
core.runtime.objects.stream — 流式句柄（IbStreamHandle）。

``IbStreamHandle`` 把 provider 的增量迭代器接入统一 Waitable 协议与
stream Channel：后台线程消费迭代器，逐块 ``send`` 到 Channel，
渲染线程（或 VM）``recv`` 逐块渲染。

- ``is_done``：迭代器已耗尽或已截断（完整/截断文本已推入）。
- ``result()``：返回拼接文本（cancel 后为截断前缀）。
- ``cancel()``：协作式截断——置取消标志，消费线程在下一协作点退出并
  干净关闭生成器；终态无 error，``result()`` 返回截断前缀。
- ``channel``：stream Channel（消费增量）。

线程模型：增量生产（provider 迭代）在后台 daemon 线程；Channel 本身线程安全
（CommBuffer），消费方任意线程 recv。

**生成器单写者**：CPython 禁止对运行中生成器跨线程 ``gen.close()``
（``ValueError: generator already executing``）——故 ``cancel()`` 只置标志，
消费线程是生成器的唯一操作者（挂起点/退出点检查标志、in-thread 关闭生成器）。
provider 生成器经 ``finally`` 关闭 HTTP 流（资源闭环）。

退出安全：daemon 线程在解释器终结时不被等待——若消费线程此刻在 C 扩展内
（流式解析/socket），C 扩展状态释放竞态可致 SIGSEGV。故 live 句柄登记于模块
注册表，``atexit`` 钩子在解释器存活期对每个 live 句柄 ``cancel()`` + 有界
``join``，确保消费线程在终结危险区之前干净退出（超时仍退出，永不阻塞进程
退出）。
"""

from __future__ import annotations

import atexit
import threading
import types
from typing import Any, Callable, Iterable, Optional

from core.runtime.shared.comm.channel import ChannelCore

# 退出 drain 的每流有界等待（秒）：LLM 挂死场景下不阻塞进程退出。
_ATEXIT_JOIN_TIMEOUT = 2.0

# live 句柄注册表（强引用：被放弃的句柄无用户可达引用，弱引用即失效，
# 退出兜底必须能看见它们）。线程经 _consume 闭包天然持有句柄，条目不产生
# 额外泄漏——流终结/cancel 即移除。
_LIVE_HANDLES: set = set()
_LIVE_LOCK = threading.Lock()


def _drain_live_streams() -> None:
    """进程退出兜底：cancel + 有界 join 全部 live 流句柄（atexit 注册）。

    atexit 在解释器仍存活期运行：cancel 置标志后消费线程经协作点退出
    （C 扩展未释放），有界 join 收口；超时仍退出（daemon 语义：永不阻塞
    进程退出）。
    """
    with _LIVE_LOCK:
        handles = list(_LIVE_HANDLES)
    for h in handles:
        h.cancel()
        h._thread.join(timeout=_ATEXIT_JOIN_TIMEOUT)


class IbStreamHandle:
    """流式增量句柄（Waitable 协议 + stream Channel + 协作式 cancel）。

    ``producer`` 为返回增量迭代器的可调用对象（每次调用新建迭代器）。
    构造时即启动后台线程消费迭代器并推入 Channel；``is_done`` 为 True 时
    文本已就绪，``result()`` 返回拼接结果（cancel 后为截断前缀）。

    **producer 契约：必须返回生成器（generator）**——协作式截断的退出路径
    需 in-thread ``close()`` 触发 provider 生成器 ``finally``（关 HTTP 流）；
    非生成器迭代器无该协议，阻塞型迭代器被放弃时悬挂（见模块 docstring
    退出安全）。消费入口 fail-fast 校验（违约 → 生产异常路径，``result()``
    重抛）。
    """

    def __init__(
        self,
        producer: Callable[[], Iterable[str]],
        channel: Optional[ChannelCore] = None,
    ):
        self._channel = channel if channel is not None else ChannelCore(mode="stream")
        self._producer = producer
        self._done = False
        self._cancelled = False
        self._error: Optional[BaseException] = None
        self._full_text: str = ""
        self._lock = threading.Lock()
        # 通知式唤醒：注册的完成事件（消费线程 finally 时 set）
        self._wake_events: list = []
        # live 登记先于线程启动：快速流可能在 __init__ 返回前即消费完毕，
        # 后登记则 finally 的 discard 先于 add 执行 → 句柄永久残留（注册表泄漏）。
        with _LIVE_LOCK:
            _LIVE_HANDLES.add(self)
        self._thread = threading.Thread(target=self._consume, daemon=True, name="ibci-stream")
        self._thread.start()

    def _consume(self) -> None:
        """后台线程：消费迭代器，逐块推入 Channel。

        取消协作点（消费线程 = 生成器唯一操作者）：
        - 消费前：_cancelled 已置 → 直接终止（不启动 HTTP 流）；
        - 消费循环中：每块复查 _cancelled → break；
        - 退出路径（finally）：in-thread ``gen.close()`` ——此刻线程不在生成器
          体内（挂起点/循环代码），close 合法；触发 provider 生成器 finally
          关 HTTP 流（资源闭环）。自然耗尽/异常退出时 close 为无害 no-op。
        """
        gen = None
        started = False
        try:
            if self._cancelled:
                return
            gen = self._producer()
            if not isinstance(gen, types.GeneratorType):
                # 契约 fail-fast：非生成器无 in-thread 关闭协议（gen.close()），
                # 阻塞型迭代器被放弃时悬挂 → 退出竞态。立即暴露，不静默容忍。
                raise TypeError(
                    "IbStreamHandle: producer must return a generator "
                    f"(cooperative cancellation contract), got {type(gen).__name__}"
                )
            started = True
            for piece in gen:
                with self._lock:
                    cancelled = self._cancelled
                if cancelled:
                    break
                if piece is None:
                    continue
                self._channel.send(str(piece))
                with self._lock:
                    self._full_text += str(piece)
        except Exception as e:
            self._error = e
        finally:
            if started:
                gen.close()  # in-thread：合法（线程不在生成器体内）
            with self._lock:
                self._done = True
                wake_events = list(self._wake_events)
            self._channel.close()
            with _LIVE_LOCK:
                _LIVE_HANDLES.discard(self)
            for ev in wake_events:
                ev.set()

    # ------------------------------------------------------------------ #
    # 生命周期（cancel）                                                  #
    # ------------------------------------------------------------------ #

    def cancel(self) -> None:
        """协作式截断（幂等）：置取消标志，消费线程在下一协作点干净退出。

        置标志线程**不直接触碰生成器**（CPython 对运行中生成器跨线程
        ``close()`` 抛 ``ValueError: generator already executing``）——
        生成器单写者原则。终态语义 = 截断：``is_done`` 置位、无 error、
        ``result()`` 返回截断前缀文本。已终结的句柄调用无副作用。
        """
        with self._lock:
            self._cancelled = True

    # ------------------------------------------------------------------ #
    # Waitable 协议                                                      #
    # ------------------------------------------------------------------ #

    @property
    def is_done(self) -> bool:
        with self._lock:
            return self._done

    def register_wake(self, event) -> None:
        """完成通知钩子：流耗尽/截断（``_done`` 置位）时设置 ``event``。"""
        with self._lock:
            if self._done:
                event.set()
                return
            self._wake_events.append(event)

    def try_result(self):
        """非阻塞取回 ``(ok, str)``（调度器专用；不阻塞）。

        ``ok=False`` 表示流未就绪（调度器重新轮询）；``ok=True`` 消费一次，
        返回拼接文本（截断后为前缀）。生产异常在 ``ok=True`` 分支重抛（终态错误）。
        """
        if not self.is_done:
            return (False, None)
        return (True, self.result())

    def result(self) -> str:
        """阻塞等待文本并返回（耗尽 = 全文；截断 = 前缀）；生产异常时重抛。

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


atexit.register(_drain_live_streams)

__all__ = ["IbStreamHandle"]

"""宿主子任务的可等待句柄（``HostAwaitable``）与接收模式（``ReceiveMode``）。

``HostAwaitable`` 是宿主异步与 VM 协作式调度的**统一接点**：由 ``collect`` /
``run_isolated`` 返回，结构性满足 :class:`core.runtime.shared.waitable.Waitable`
协议（``is_done`` 属性 + ``result()``），经 ``box()`` 透传、``vm_handle_IbCall``
``yield`` 挂起后，由调度器在 ``is_done`` 就绪时经 ``result()`` 取回子环境导出的
变量字典。

``ReceiveMode`` 定义宿主子任务结果的接收模式。当前仅 ``COLLECT``（等待完整结果
并提取字典）有实现；``STREAM``（流式接收）依赖多模态子系统，已封存，标注 deferred。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ReceiveMode(Enum):
    """宿主子任务结果的接收模式。

    - ``COLLECT``：等待子任务完整执行，经 ``result()`` 提取子环境导出的变量字典。
    - ``STREAM``：流式接收（逐块结果）。依赖多模态子系统，已封存，当前不实现。
    """

    COLLECT = "collect"
    STREAM = "stream"


class HostAwaitable:
    """宿主子任务的可等待句柄（``Waitable`` 协议）。

    持有 orchestrator 引用与 spawn handle；``is_done`` 非破坏性轮询子线程是否
    完成，``result()`` 经 ``request_collect`` 取回子环境变量字典（消费 handle）。

    参数：
        orchestrator: 内核协调器（负责子引擎的 spawn/collect 生命周期）。
        handle: ``spawn_isolated`` 返回的句柄字符串。
        mode: 接收模式，默认 ``ReceiveMode.COLLECT``（当前唯一实现）。
    """

    def __init__(self, orchestrator: Any, handle: str, mode: ReceiveMode = ReceiveMode.COLLECT):
        self._orchestrator = orchestrator
        self._handle = handle
        self._mode = mode

    @property
    def handle(self) -> str:
        return self._handle

    @property
    def mode(self) -> ReceiveMode:
        return self._mode

    @property
    def is_done(self) -> bool:
        """子任务是否已执行完成（非破坏性检查，不消费 handle）。"""
        return self._orchestrator.is_spawn_done(self._handle)

    def try_result(self):
        """非阻塞取回 ``(ok, dict)``（调度器专用；不阻塞）。

        ``ok=False`` 表示子任务未完成（调度器重新轮询）；``ok=True`` 消费一次
        handle（经 ``request_collect`` 取回子环境变量字典）。
        """
        if not self.is_done:
            return (False, None)
        return (True, self.result())

    def register_wake(self, event) -> None:
        """完成通知钩子（R2）：子线程完成时设置 ``event``。

        经 orchestrator 的 spawn 完成钩子注册；handle 已不存在/已完成时
        立即设置（竞态下注册晚于完成）。
        """
        if not self._orchestrator.register_spawn_wake(self._handle, event):
            # handle 已被消费：子任务已完成，立即唤醒
            event.set()

    def result(self) -> Any:
        """等待并取回子环境导出的变量字典（消费 handle）。"""
        if self._mode is ReceiveMode.STREAM:
            raise NotImplementedError(
                "ReceiveMode.STREAM 未实现（依赖多模态子系统，已封存）。"
            )
        return self._orchestrator.request_collect(self._handle)
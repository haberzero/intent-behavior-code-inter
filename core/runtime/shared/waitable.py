"""可等待对象协议（``Waitable``）—— 运行时共享叶子模块。

本模块位于 ``core/runtime/shared/`` —— 运行时各子包（vm / host / interpreter）
共享的叶子模块，避免 vm ↔ host 与 vm ↔ bootstrapper 的循环导入。

``Waitable`` 是 IBCI 异步/并发模型的**统一抽象**：任何可被调度器等待的操作
（LLM future、宿主子任务、未来语言级 awaitable）都满足本协议——调度器据此
询问 ``is_done`` 是否就绪，就绪后经 ``result()`` 取完成值。

结构性协议（``runtime_checkable``）：只要对象同时具备 ``is_done`` 属性与
``result()`` 方法即视为 ``Waitable``，无需显式继承。现有 ``LLMFuture`` 与
宿主 ``HostAwaitable`` 均按此结构匹配，可直接被 ``TaskScheduler`` 等待。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Waitable(Protocol):
    """可等待对象协议：调度器据此询问是否就绪并取完成结果。

    ``is_done`` 为属性，``result()`` 返回完成值（阻塞语义由调用方决定——
    调度器只在 ``is_done`` 为真的轮询间隙调用 ``result()``）。
    """

    @property
    def is_done(self) -> bool: ...

    def result(self) -> Any: ...
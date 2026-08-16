"""可等待对象协议（``Waitable``）—— 运行时共享叶子模块。

本模块位于 ``core/runtime/shared/`` —— 运行时各子包（vm / host / interpreter）
共享的叶子模块，避免 vm ↔ host 与 vm ↔ bootstrapper 的循环导入。

``Waitable`` 是 IBCI 异步/并发模型的**统一抽象**：任何可被调度器等待的操作
（LLM future、宿主子任务、流句柄、线程完成、通信 recv）都满足本协议——调度器
据此询问 ``is_done`` 是否就绪，就绪后经 ``try_result()`` 非阻塞取回（调度器
专用），宿主/线程体经 ``result()`` 阻塞取回。

结构性协议（``runtime_checkable``）：对象同时具备 ``is_done`` 属性、
``try_result()`` 方法与 ``result()`` 方法即视为 ``Waitable``，无需显式继承。
现有 ``LLMFuture`` / ``HostAwaitable`` / ``IbStreamHandle`` / ``SpawnedTask``
均按此结构匹配。

``try_result()`` 语义（调度器专用，**永不阻塞**）：
- 返回 ``(ok, value)``：``ok=True`` 表示值已可取走（消费一次）；``ok=False``
  表示尚未就绪（调度器重新轮询）。
- 可抛异常表示**终态错误**（如通道已关闭空队列、Future 失败）——调度器将该
  异常 ``throw`` 进任务，经 CPS 传播让 try-except / llmexcept 处理。
- 对"未就绪"重复调用是安全的（不消费）；对"已就绪"只应调用一次（消费）。

``result()`` 语义（宿主/线程体专用，**可阻塞**）：阻塞取回完成值；消费一次。
调度器**不得**调用 ``result()``——部分 waitable（HostAwaitable）的 ``result()``
是消耗性的，二次消费会报错。

``register_wake(event)`` 语义（R2 通知式唤醒，**可选优化钩子**）：
- 把完成通知注册到 ``event``（``threading.Event``）；本 waitable 完成时设置
  该事件，使调度器能被**即时唤醒**（而非 ~1ms 轮询）。
- 结构性协议允许缺失：实现者可不提供（此时调度器退回首轮询 + 安全超时兜底）。
  缺失即"无通知能力"，不是协议决策点（调度决策仍经 ``try_result``）。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CPSDrivable(Protocol):
    """可帧内 CPS 驱动协议：Waitable 的可选扩展能力。

    支持在**当前 VM 帧栈**内协作驱动（而非 yield 挂起后由调度器轮询
    ``try_result``）的 Waitable 实现本协议。``cps_drive`` 是生成器：
    调用方（``vm_handle_IbCall``）对其 ``yield from``，使内部用户代码
    （如 ``slot.update(fn)`` 的 fn 求值）嵌入外层调度循环统一驱动，
    ``try_result`` 不新建嵌套 TaskScheduler。

    结构性协议：实现者提供 ``cps_drive`` 方法即满足；缺失的 Waitable
    走既有调度器轮询路径，非决策分派（与 ``register_wake`` 可选钩子同构）。
    """

    def cps_drive(self, executor) -> Any:
        """帧内协作驱动本 waitable 到完成（生成器，调用方 ``yield from``）。"""
        ...


@runtime_checkable
class Waitable(Protocol):
    """可等待对象协议：调度器据此询问是否就绪并取回完成结果。

    ``is_done`` 为属性；``try_result()`` 非阻塞取（调度器）；``result()``
    阻塞取（宿主/线程体）；``register_wake()`` 可选完成通知钩子（调度器
    即时唤醒优化）。
    """

    @property
    def is_done(self) -> bool: ...

    def try_result(self) -> tuple:
        """非阻塞取回 ``(ok, value)``；终态错误可抛异常。调度器专用。"""
        ...

    def result(self) -> Any:
        """阻塞取回完成值（消费一次）。宿主/线程体专用。"""
        ...

    def register_wake(self, event) -> None:
        """把完成通知注册到 ``event``（可选优化；缺失时调度器退回首轮询）。

        ``event`` 为 ``threading.Event`` 兼容对象，应具有 ``set()`` 方法。
        本 waitable 完成时须设置该事件（可从任意线程调用）。
        """
        ...
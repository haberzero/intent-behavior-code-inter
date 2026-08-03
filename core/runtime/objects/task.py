"""
core.runtime.objects.task — IBCI 任务句柄值对象（IbTask）。

``IbTask`` 是 ``spawn`` 的返回值（task 类型），供 ``join`` / ``cancel`` 使用。

PT-MT-3 阶段执行模型：**协作式延迟任务**——``spawn`` 记录可调用 + 实参，
不立即执行（不引入后台线程共享 runtime_context 的并发竞争）；``join`` 时
在**当前 VM 线程**内求值到完成并返回结果；``cancel`` 在任务未启动时标记
取消。这是安全的真实实现（非 shim）：任务抽象完整、语义自洽，后台线程 /
轻量 VM 实例的并发执行（用户裁定"用户可见多线程"）在 PT-MT-7/8 落地
（届时升级执行路径，任务句柄接口不变）。

``IbTask`` 结构性满足 :class:`core.runtime.shared.waitable.Waitable` 协议
（``is_done`` 属性 + ``result()``），可被 VM 调度器 yield 挂起等待。
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from .kernel.base import IbObject
from .kernel.ib_class import IbClass
from .kernel.functions import IbNativeFunction


class IbTask(IbObject):
    """IBCI 语言层的任务句柄（``spawn`` 返回值）。"""

    __slots__ = ("_executor", "_callable", "_args", "_started", "_cancelled", "_result")

    def __init__(
        self,
        ib_class: IbClass,
        executor: Any,
        callable_obj: Any,
        args: Optional[List[Any]] = None,
    ):
        super().__init__(ib_class)
        self._executor = executor
        self._callable = callable_obj
        self._args = list(args or [])
        self._started = False
        self._cancelled = False
        self._result: Any = None

    # ------------------------------------------------------------------ #
    # Waitable 协议（供 join / VM 调度器）                               #
    # ------------------------------------------------------------------ #

    @property
    def is_done(self) -> bool:
        """任务是否已完成（已启动并产生结果，或已被取消）。"""
        return self._started or self._cancelled

    def result(self) -> Any:
        """取回任务结果；未完成则抛 RuntimeError。"""
        if not self.is_done:
            raise RuntimeError("IbTask: task is not done yet; call join() to run it to completion.")
        if self._cancelled:
            raise RuntimeError("IbTask: task was cancelled.")
        return self._result

    def as_waitable(self) -> "IbTask":
        """以 Waitable 身份返回自身（join 路径使用）。"""
        return self

    # ------------------------------------------------------------------ #
    # 任务语义                                                            #
    # ------------------------------------------------------------------ #

    def _invoke(self) -> Any:
        """执行任务体（当前 VM 线程内求值可调用对象）。"""
        callable_obj = self._callable
        receiver = self._executor.registry.get_none()
        if callable_obj is None:
            return self._executor.registry.get_none()
        return callable_obj.call(receiver, self._args)

    def join(self) -> Any:
        """等待任务完成并取回结果（延迟执行模型：join 触发求值）。"""
        if self._cancelled:
            raise RuntimeError("IbTask: task was cancelled.")
        if not self._started:
            self._started = True
            self._result = self._invoke()
        return self._result

    def cancel(self) -> None:
        """请求取消任务（协作式：仅未启动时可取消）。"""
        if not self._started:
            self._cancelled = True

    def to_native(self, memo=None) -> Any:
        return {
            "started": self._started,
            "cancelled": self._cancelled,
            "done": self.is_done,
        }

    def __repr__(self):
        state = "cancelled" if self._cancelled else ("done" if self.is_done else "pending")
        return f"<Task state={state}>"


def spawn_task_handle(executor: Any, callable_obj: Any, args: Optional[List[Any]] = None) -> IbTask:
    """构造任务句柄（PT-MT-3 协作式延迟任务）。

    ``executor`` 为 VMExecutor（提供 registry / runtime_context 供任务体求值）。
    """
    task_cls = executor.registry.get_class("task")
    return IbTask(ib_class=task_cls, executor=executor, callable_obj=callable_obj, args=args)

"""
core.runtime.objects.task — IBCI 任务句柄值对象（IbTask）。

``IbTask`` 是 ``spawn`` 的返回值（task 类型），供 ``join`` / ``cancel`` 使用。

PT-MT-7 执行模型：**后台线程 + 任务本地执行上下文**（经 ``RuntimeCoordinator``
驱动 ``SpawnedTask``）。任务在独立线程运行，拥有隔离的 runtime_context /
作用域/意图（并发正确性 C4），共享只读 node_pool/registry（C5）。

``IbTask`` 结构性满足 :class:`core.runtime.shared.waitable.Waitable` 协议
（``is_done`` 属性 + ``result()``），可被 VM 调度器 yield 挂起等待。
"""

from __future__ import annotations

from typing import Any, List, Optional

from .kernel.base import IbObject
from .kernel.ib_class import IbClass


class IbTask(IbObject):
    """IBCI 语言层的任务句柄（``spawn`` 返回值）。"""

    __slots__ = ("_coordinator", "_spawned", "_executor", "_callable", "_args")

    def __init__(
        self,
        ib_class: IbClass,
        executor: Any,
        coordinator: Any,
        callable_obj: Any,
        args: Optional[List[Any]] = None,
    ):
        super().__init__(ib_class)
        self._executor = executor
        self._coordinator = coordinator
        self._callable = callable_obj
        self._args = list(args or [])
        self._spawned = None  # SpawnedTask（惰性启动）

    # ------------------------------------------------------------------ #
    # 启动 / 等待                                                        #
    # ------------------------------------------------------------------ #

    def _ensure_started(self):
        """惰性启动 SpawnedTask（join 首次触发）。"""
        if self._spawned is None:
            self._spawned = self._coordinator.spawn(self._callable, self._args)
        return self._spawned

    @property
    def is_done(self) -> bool:
        """任务是否已完成（SpawnedTask 的 Future done）。"""
        if self._spawned is None:
            return False
        return self._spawned.is_done

    def result(self) -> Any:
        """取回任务结果；未完成则阻塞等待。"""
        return self._ensure_started().result()

    def join(self) -> Any:
        """等待任务完成并取回结果。"""
        return self._ensure_started().join()

    def cancel(self) -> None:
        """请求取消任务（协作式）。"""
        if self._spawned is not None:
            self._spawned.cancel()

    def to_native(self, memo=None) -> Any:
        if self._spawned is None:
            return {"started": False, "done": False}
        return self._spawned.to_dict()

    def __repr__(self):
        state = "pending"
        if self._spawned is not None:
            state = "done" if self._spawned.is_done else "running"
        return f"<Task state={state}>"

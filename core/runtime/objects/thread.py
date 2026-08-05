"""
core.runtime.objects.thread — IBCI 线程对象模型值对象（IbThread）。

``thread`` 是线程对象模型方向修正（任务 C）的一等对象：``thread[T]`` 泛型
类型 + 构造函数 ``thread(callable=..., args=...)`` + 句柄方法
（start/join/cancel/is_done）+ 生命周期状态机。

内部复用 ``RuntimeCoordinator`` + ``SpawnedTask``（后台线程 + 任务本地执行
上下文）实现真正的并发执行；``IbThread`` 作为语言层句柄包装之。

生命周期状态机：idle → running → done / cancelled / failed。
- ``idle``     ：已构造，未启动（``start()`` 前）
- ``running``  ：已 ``start()``，后台线程运行中
- ``done``     ：正常完成，结果值已产生
- ``cancelled``：协作式取消
- ``failed``   ：任务内异常

方法与 async 彻底分离：``IbThread`` 不满足 ``Waitable``（await 只服务异步），
线程生命周期经句柄方法管理。

实例状态承载（阶段 2 统一值对象机制，D2）：实例经 ``_create_blank`` 创建为
真实 ``IbThread``，状态存于 ``__slots__``（``_coordinator``/``_spawned``/
``_callable``/``_args``/``_state``），不再经普通 IbObject 的 ``fields`` 绕路。
句柄方法为真实例方法；eager 启动内聚于 ``_ensure_started`` 实例方法。

状态常量单一权威源：``ThreadStatus``（G2）同时供 thread 与 thread_result 使用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.issue import InterpreterError

from .ib_type_mapping import register_ib_type
from .kernel.base import IbObject
from .kernel.ib_class import IbClass


class ThreadStatus:
    """线程 / 线程结果生命周期状态常量（单一权威源，G2）。

    thread 使用全部 5 态；thread_result 使用子集 3 态（done/cancelled/failed）。
    序列化字符串与枚举 ``.value`` 同源，禁止裸字符串散落。
    """

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


@register_ib_type("thread")
class IbThread(IbObject):
    """IBCI 语言层的 thread 值对象（句柄 + 生命周期状态机）。

    方法表面（start/join/cancel/is_done）由 ``ThreadAxiom`` 声明，经
    ``primitive_initializer`` 的 axiom-driven auto-bind 自动绑定到语言层。
    实例状态存于 ``__slots__``；构造经 ``instantiate`` 的 ``_create_blank``
    钩子创建真实 ``IbThread`` 实例。
    """

    __slots__ = ("_coordinator", "_spawned", "_callable", "_args", "_state")

    @classmethod
    def _create_blank(cls, ib_class: IbClass) -> "IbThread":
        """类型化空实例（阶段 2，D1）：使 ``thread(...)`` 构造真实 IbThread。"""
        return cls(ib_class)

    def __init__(self, ib_class: IbClass):
        super().__init__(ib_class)
        self._coordinator: Any = None
        self._spawned: Any = None
        self._callable: Any = None
        self._args: List[Any] = []
        self._state: str = ThreadStatus.IDLE

    def _ensure_started(self) -> None:
        """启动后台线程（eager：首次调用即启动；幂等）。"""
        if self._spawned is not None:
            return
        self._spawned = self._coordinator.spawn(self._callable, self._args)
        self._state = ThreadStatus.RUNNING

    # ------------------------------------------------------------------ #
    # 生命周期状态机（句柄方法，操作实例槽位）                            #
    # ------------------------------------------------------------------ #

    def start(self) -> "IbObject":
        """启动线程（幂等；已启动则直接返回自身）。"""
        self._ensure_started()
        return self

    def is_done(self) -> "IbObject":
        """返回是否已完成（done/cancelled/failed 均视为结束）。"""
        return self.ib_class.registry.box(self._state in (
            ThreadStatus.DONE,
            ThreadStatus.CANCELLED,
            ThreadStatus.FAILED,
        ))

    def join(self) -> Any:
        """阻塞等待线程完成并返回 ``thread_result[T]`` 容器。

        成功 → status=done、value=T、error=null；
        失败/取消 → status=failed/cancelled、error=err、value=null。
        值化失败（不靠抛异常打断控制流），用户经 ``thread_result`` 方法取值。
        """
        from .thread_result import IbThreadResult

        if self._spawned is None:
            raise InterpreterError("join() called on a thread that was never started")
        result_cls = self.ib_class.registry.get_class("thread_result")
        try:
            value = self._spawned.join()
            self._state = ThreadStatus.DONE
            return IbThreadResult(
                ib_class=result_cls,
                value=value,
                error=None,
                status=ThreadStatus.DONE,
            )
        except BaseException as e:
            # 线程失败/取消：把底层异常映射为 IBCI err 对象存入容器（值化失败）。
            # 协作式取消（TaskCancelled）→ TaskCancelled；其他 → TaskFailed。
            from core.runtime.exceptions import ThrownException
            from core.runtime.coordinator import TaskCancelled as _CoordTaskCancelled

            if isinstance(e, ThrownException):
                # 用户代码主动 raise：错误值本身就是 IBCI 异常对象。
                err_obj = e.value
            elif isinstance(e, _CoordTaskCancelled):
                err_obj = self.ib_class.registry.make_task_cancelled(str(e))
            else:
                err_obj = self.ib_class.registry.make_task_failed(str(e))
            state = (
                ThreadStatus.CANCELLED
                if isinstance(e, _CoordTaskCancelled)
                else ThreadStatus.FAILED
            )
            status = state
            self._state = state
            return IbThreadResult(
                ib_class=result_cls,
                value=None,
                error=err_obj,
                status=status,
            )

    def cancel(self) -> "IbObject":
        """请求取消线程（协作式）；返回 err 指示操作状态。

        - 成功发出取消请求 → ``TaskCancelled`` err
        - 线程未启动或已结束 → ``None``（无效/已结束）
        """
        if self._spawned is None:
            return self.ib_class.registry.get_none()
        self._spawned.cancel()
        self._state = ThreadStatus.CANCELLED
        return self.ib_class.registry.make_task_cancelled()

    # ------------------------------------------------------------------ #
    # 值协议 / 内省                                                       #
    # ------------------------------------------------------------------ #

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        if self._spawned is None:
            return {"state": self._state, "done": False}
        return {"state": self._state, "done": bool(self._spawned.is_done)}

    def __transient_state__(self) -> Dict[str, Any]:
        """瞬态序列化协议（L6）：纯状态存根，不递归 coordinator（防引用环）。"""
        if self._spawned is None:
            return {"state": self._state, "done": False}
        return {"state": self._state, "done": bool(self._spawned.is_done)}

    def __repr__(self):
        return f"<Thread state={self._state}>"

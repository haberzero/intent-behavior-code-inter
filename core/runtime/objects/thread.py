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

实例状态经 ``fields`` 承载（与 ``intent_context`` 值对象模式一致）：实例由
``instantiate`` 创建为普通 ``IbObject``，``__init__`` 经 ``_init_fields`` 在
``fields`` 初始化线程状态，句柄方法经 axiom 自动绑定操作 ``fields``。
所有句柄方法自包含（仅操作 ``fields``），不依赖实例私有 helper ——
因为实例是普通 ``IbObject``，axiom 自动绑定只将公开方法绑定到类。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.issue import InterpreterError

from .ib_type_mapping import register_ib_type
from .kernel.base import IbObject
from .kernel.ib_class import IbClass


class _ThreadState:
    """线程生命周期状态常量（内部枚举，避免魔法字符串）。"""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


# fields 键名（单一权威源，避免魔法字符串散落）。
# 实例为普通 IbObject，状态存于其 fields；句柄方法经 axiom 自动绑定读取这些键。
_FIELD_COORDINATOR = "_coordinator"
_FIELD_SPAWNED = "_spawned"
_FIELD_CALLABLE = "_callable"
_FIELD_ARGS = "_args"
_FIELD_STATE = "_state"

# 供 primitive_initializer 的 __init__ 构造使用（导入键名常量）。
_FIELDS = (
    _FIELD_COORDINATOR,
    _FIELD_SPAWNED,
    _FIELD_CALLABLE,
    _FIELD_ARGS,
    _FIELD_STATE,
)


@register_ib_type("thread")
class IbThread(IbObject):
    """IBCI 语言层的 thread 值对象（句柄 + 生命周期状态机）。

    方法表面（start/join/cancel/is_done）由 ``ThreadAxiom`` 声明，经
    ``primitive_initializer`` 的 axiom-driven auto-bind 自动绑定到语言层。
    实例状态存于 ``self.fields``（构造经 ``instantiate`` 创建普通 IbObject）。
    """

    @staticmethod
    def _init_fields(instance: IbObject, coordinator: Any, callable_obj: Any,
                     args: Optional[List[Any]] = None) -> None:
        """初始化线程状态到实例 fields，并 eager 启动（构造经 __init__ 调用）。"""
        instance.fields[_FIELD_COORDINATOR] = coordinator
        instance.fields[_FIELD_CALLABLE] = callable_obj
        instance.fields[_FIELD_ARGS] = list(args or [])
        instance.fields[_FIELD_SPAWNED] = None
        instance.fields[_FIELD_STATE] = _ThreadState.IDLE
        _ensure_started(instance)

    # ------------------------------------------------------------------ #
    # 生命周期状态机（句柄方法，自包含操作 fields）                        #
    # ------------------------------------------------------------------ #

    def start(self) -> "IbObject":
        """启动线程（幂等；已启动则直接返回自身）。"""
        _ensure_started(self)
        return self

    def is_done(self) -> "IbObject":
        """返回是否已完成（done/cancelled/failed 均视为结束）。"""
        return self.ib_class.registry.box(self.fields.get(_FIELD_STATE) in (
            _ThreadState.DONE,
            _ThreadState.CANCELLED,
            _ThreadState.FAILED,
        ))

    def join(self) -> Any:
        """阻塞等待线程完成并返回结果值。

        线程失败/取消时抛对应 IBCI 异常（任务 D 落地精确 err 类型；
        当前阶段先以既有 ``TaskCancelled``/``TaskFailed`` 语义透传）。
        """
        spawned = self.fields.get(_FIELD_SPAWNED)
        if spawned is None:
            raise InterpreterError("join() called on a thread that was never started")
        result = spawned.join()
        self.fields[_FIELD_STATE] = _ThreadState.DONE
        return result

    def cancel(self) -> "IbObject":
        """请求取消线程（协作式）；返回操作状态（任务 D 落地为 err 类型）。

        当前阶段返回 IBCI bool 表示是否成功发出取消请求。
        """
        spawned = self.fields.get(_FIELD_SPAWNED)
        if spawned is None:
            return self.ib_class.registry.box(False)
        spawned.cancel()
        self.fields[_FIELD_STATE] = _ThreadState.CANCELLED
        return self.ib_class.registry.box(True)

    # ------------------------------------------------------------------ #
    # 值协议 / 内省                                                       #
    # ------------------------------------------------------------------ #

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        spawned = self.fields.get(_FIELD_SPAWNED)
        if spawned is None:
            return {"state": self.fields.get(_FIELD_STATE), "done": False}
        return {"state": self.fields.get(_FIELD_STATE), "done": self.is_done()}

    def __repr__(self):
        return f"<Thread state={self.fields.get(_FIELD_STATE)}>"


def _ensure_started(instance: IbObject) -> None:
    """启动后台线程（eager：首次调用即启动；幂等）。

    独立函数（非 IbThread 方法）以便 ``_init_fields`` 与 ``start`` 复用，
    且不依赖实例私有 helper（实例为普通 IbObject）。
    """
    if instance.fields.get(_FIELD_SPAWNED) is not None:
        return
    spawned = instance.fields[_FIELD_COORDINATOR].spawn(
        instance.fields[_FIELD_CALLABLE], instance.fields[_FIELD_ARGS]
    )
    instance.fields[_FIELD_SPAWNED] = spawned
    instance.fields[_FIELD_STATE] = _ThreadState.RUNNING
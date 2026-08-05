"""
core.runtime.objects.thread_result — IBCI 线程结果容器值对象（IbThreadResult）。

``thread_result[T]`` 是 ``t.join()`` 的返回值容器。携带成功值 / 错误对象 /
状态，值化失败（不靠抛异常打断控制流）。

状态：done / cancelled / failed（``ThreadStatus`` 单一权威源）。
- 成功：``status=done``、``value=T``、``error=null``
- 失败：``status=failed/cancelled``、``error=err``、``value=null``

值对象身份：继承 ``IbValue``，``payload`` 承载成功值（单一承载），
``_error``/``_status`` 存槽位；``type_ref`` 经 spec 生效，``thread_result[int]``
泛型身份在序列化/快照中保留。

方法（Rust 风格）：
- ``unwrap()``     → Optional[T]（失败返回 Optional 空，不抛）
- ``unwrap_or(v)`` → T（失败返回默认值）
- ``expect()``     → T（失败抛 IBCI 异常，fail-fast）
- ``is_error()`` / ``is_success()`` → bool
- ``value`` / ``error`` / ``status`` 内省成员

方法表面由 ``ThreadResultAxiom`` 声明，经 ``primitive_initializer`` 的
axiom-driven auto-bind 自动绑定到语言层。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.issue import InterpreterError

from .ib_type_mapping import register_ib_type
from .kernel.base import IbValue, IbObject
from .kernel.ib_class import IbClass
from .primitives.optional import IbOptional
from .thread import ThreadStatus


@register_ib_type("thread_result")
class IbThreadResult(IbValue):
    """IBCI 语言层的 thread_result[T] 值对象（线程结果容器）。

    继承 ``IbValue``：``payload`` 为成功值承载；``_status``/``_error`` 存槽位。
    ``value()`` 语言方法遮蔽 ``IbValue.value`` 属性（payload 别名），内部一律
    经 ``self.payload`` 访问承载值。
    """

    __slots__ = ("_error", "_status")

    def __init__(
        self,
        ib_class: IbClass,
        value: Any = None,
        error: Any = None,
        status: str = ThreadStatus.DONE,
    ):
        super().__init__(ib_class, payload=value)
        self._error = error
        self._status = status

    # ------------------------------------------------------------------ #
    # 内省成员（value/error/status）                                        #
    # ------------------------------------------------------------------ #

    def value(self) -> Any:
        """返回成功值（失败时为 None/null）。"""
        if self._status == ThreadStatus.DONE:
            return self.payload
        return self.ib_class.registry.get_none()

    def error(self) -> Any:
        """返回错误对象（成功时为 None/null）。"""
        if self._status == ThreadStatus.DONE:
            return self.ib_class.registry.get_none()
        return self._error if self._error is not None else self.ib_class.registry.get_none()

    def status(self) -> Any:
        """返回状态字符串（done/cancelled/failed）。"""
        return self.ib_class.registry.box(self._status)

    # ------------------------------------------------------------------ #
    # 内省方法                                                            #
    # ------------------------------------------------------------------ #

    def is_error(self) -> Any:
        """是否失败（failed/cancelled）。"""
        return self.ib_class.registry.box(self._status != ThreadStatus.DONE)

    def is_success(self) -> Any:
        """是否成功（done）。"""
        return self.ib_class.registry.box(self._status == ThreadStatus.DONE)

    # ------------------------------------------------------------------ #
    # 取值方法（Rust 对齐）                                                 #
    # ------------------------------------------------------------------ #

    def unwrap(self) -> Any:
        """返回 Optional[T]——失败返回 Optional 空（非裸 None）。

        对齐 OptionalAxiom 先例，避免类型撒谎。
        """
        optional_cls = self.ib_class.registry.get_class("Optional")
        if self._status == ThreadStatus.DONE:
            return IbOptional(ib_class=optional_cls, inner=self.payload, is_some=True)
        return IbOptional(ib_class=optional_cls, inner=None, is_some=False)

    def unwrap_or(self, default: Any) -> Any:
        """失败返回默认值（最常用，推荐）。"""
        if self._status == ThreadStatus.DONE:
            return self.payload
        return default

    def expect(self) -> Any:
        """直接返回 T；失败抛对应 IBCI 异常（fail-fast，Rust 对齐）。

        失败时以 ``ThrownException`` 抛出容器内错误对象，语言层 try/except
        可捕获；容器内错误是 IBCI 异常对象（TaskCancelled/TaskFailed 等）。
        """
        if self._status == ThreadStatus.DONE:
            return self.payload
        err = self._error
        from core.runtime.exceptions import ThrownException

        if isinstance(err, ThrownException):
            raise err
        if isinstance(err, BaseException):
            raise err
        raise ThrownException(err) if err is not None else InterpreterError(
            f"thread_result.expect() called on a failed result (status={self._status!r})"
        )

    # ------------------------------------------------------------------ #
    # 值协议                                                            #
    # ------------------------------------------------------------------ #

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        if self._status == ThreadStatus.DONE:
            return self.payload.to_native(memo) if isinstance(self.payload, IbObject) else self.payload
        return None

    def __to_prompt__(self) -> str:
        if self._status == ThreadStatus.DONE:
            return str(self.payload.__to_prompt__()) if hasattr(self.payload, "__to_prompt__") else str(self.payload)
        return f"<thread_result {self._status}>"

    def __repr__(self):
        return f"<ThreadResult status={self._status} value={self.payload!r}>"

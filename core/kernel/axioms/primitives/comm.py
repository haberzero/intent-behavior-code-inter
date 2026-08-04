"""
core/kernel/axioms/primitives/comm.py

Concurrency / communication axioms: task, chan, signal, slot.

These axioms are deliberately minimal — they establish type identity and
the method surface (send/recv/get/set etc.) so the semantic layer can type
check ``chan.send(...)`` / ``slot.get()`` etc. Runtime behaviour is provided
by the ``IbChannel`` / ``IbSignal`` / ``IbSlot`` / ``IbTask`` objects in
``core/runtime/objects/`` (registered at interpreter bootstrap), consistent
with the "axioms declare, runtime implements" convention used across IBCI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec


class TaskAxiom(BaseAxiom):
    """公理：task 类型（spawn 的任务句柄，join/cancel 载体）。

    无值运算能力；主要作为类型标识。运行时 IbTask 提供 is_done/result
    等（供 Waitable 协议 / 内省）。
    """

    @property
    def name(self) -> str:
        return "task"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "task"


class ThreadAxiom(BaseAxiom):
    """公理：thread 类型（线程对象模型方向修正，任务 C 落地）。

    ``thread[T]`` 泛型：返回值类型经 value_type 承载（``t.join()`` 返回 T）。
    提供句柄方法表面（start/join/cancel/is_done）供语义层类型检查——
    运行时实现由 ``IbThread`` 值对象提供（任务 C）。

    ``has_call_cap``：``thread(...)`` 是构造函数调用（创建线程句柄），
    语义层据此允许 ``thread(...)`` 表达式。
    """

    has_call_cap = True

    @property
    def name(self) -> str:
        return "thread"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "start": _m("start", ret="thread"),
            "join": _m("join", ret="any"),
            "cancel": _m("cancel", ret="any"),
            "is_done": _m("is_done", ret="bool"),
        }

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        # thread(...) 构造函数返回 thread 类型（具体泛型由声明上下文确定）。
        return "thread"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "thread" or other_name.startswith("thread[")


class ThreadResultAxiom(BaseAxiom):
    """公理：thread_result 类型（线程结果容器，join 的返回值）。

    ``thread_result[T]`` 泛型：成功值类型经 value_type 承载。提供容器方法
    表面供语义层类型检查——运行时实现由 ``IbThreadResult`` 值对象提供。

    方法：
    - ``unwrap()``     → Optional[T]（失败返回 Optional 空，不抛）
    - ``unwrap_or(v)`` → T（失败返回默认值）
    - ``expect()``     → T（失败抛错，fail-fast，Rust 对齐）
    - ``is_error()`` / ``is_success()`` → bool
    - ``value`` / ``error`` / ``status`` 内省成员
    """

    @property
    def name(self) -> str:
        return "thread_result"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "unwrap": _m("unwrap", ret="any"),
            "unwrap_or": _m("unwrap_or", params=["any"], ret="any"),
            "expect": _m("expect", ret="any"),
            "is_error": _m("is_error", ret="bool"),
            "is_success": _m("is_success", ret="bool"),
            "value": _m("value", ret="any"),
            "error": _m("error", ret="any"),
            "status": _m("status", ret="str"),
        }

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "thread_result" or other_name.startswith("thread_result[")


class ChannelAxiom(BaseAxiom):
    """公理：chan 类型（数据流通道）。

    ``chan[T]`` 泛型：元素类型经 value_type 承载。提供 send/recv/close
    等方法表面供语义层类型检查。
    """

    @property
    def name(self) -> str:
        return "chan"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "send": _m("send", params=["any"], ret="void", mutating=True),
            "recv": _m("recv", ret="any"),
            "recv_nonblocking": _m("recv_nonblocking", ret="any"),
            "close": _m("close", ret="void", mutating=True),
        }

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "chan" or other_name.startswith("chan[")


class SignalAxiom(BaseAxiom):
    """公理：signal 类型（控制流信号，抢占式、一次性）。"""

    @property
    def name(self) -> str:
        return "signal"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "signal"


class SlotAxiom(BaseAxiom):
    """公理：slot 类型（共享状态槽，具名原子读写）。

    ``slot[T]`` 泛型：值类型经 value_type 承载。提供 get/set/update。
    """

    @property
    def name(self) -> str:
        return "slot"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "get": _m("get", ret="any"),
            "set": _m("set", params=["any"], ret="void", mutating=True),
            "update": _m("update", params=["any"], ret="void", mutating=True),
        }

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "slot" or other_name.startswith("slot[")

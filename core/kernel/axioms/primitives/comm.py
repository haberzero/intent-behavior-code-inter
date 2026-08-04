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
    """

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

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "thread" or other_name.startswith("thread[")


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

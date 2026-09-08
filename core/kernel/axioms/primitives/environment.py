"""
core/kernel/axioms/primitives/environment.py

EnvironmentAxiom —— 一等环境对象（``environment``）的公理定义。

B3：可快照/嵌套的作用域化键值环境。语义面（frames 栈、内帧遮蔽、
fork 快照、use 替换）由 EnvironmentState 承载；公理声明类型身份与
方法契约（含 get_current/use 静态面——类型名调用形态，与
intent_context 先例同构）。
"""
from __future__ import annotations

from core.kernel.axioms.primitives.base import BaseAxiom, _m


class EnvironmentAxiom(BaseAxiom):
    """
    公理：environment 类型。

    * is_dynamic() = False — environment 是具体类型。
    * 无 capability — 环境对象不是可调用对象。
    * is_compatible 仅接受 "environment" 自身。
    * get_parent_axiom_name() = "Object"。
    """

    @property
    def name(self) -> str:
        return "environment"

    def get_method_specs(self):
        return {
            # 静态面（类型名调用：environment.get_current() / environment.use(env)）
            "get_current": _m("get_current", ret="environment"),
            "use": _m("use", params=["environment"], ret="void"),
            # 实例面
            "get": _m("get", params=["str"], ret="any"),
            "set": _m("set", params=["str", "any"], ret="void", mutating=True),
            "pop": _m("pop", params=["str"], ret="any", mutating=True),
            "clear": _m("clear", ret="void", mutating=True),
            "fork": _m("fork", ret="environment"),
            "len": _m("len", ret="int"),
            "contains": _m("contains", params=["str"], ret="bool"),
            "keys": _m("keys", ret="list"),
        }

    def is_class(self) -> bool:
        return True

    def is_dynamic(self) -> bool:
        return False

    def get_parent_axiom_name(self) -> str:
        return "Object"

    def is_compatible(self, other) -> bool:
        return getattr(other, "head", None) == "environment" or \
            getattr(other, "name", None) == "environment"

    def can_convert_from(self, source_name: str) -> bool:
        return source_name in ("environment", "str")

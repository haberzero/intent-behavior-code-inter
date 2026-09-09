"""
core/kernel/axioms/primitives/memory.py

MemoryAxiom —— 层级记忆基底类型的公理声明。

memory = 一等内置值类型（Round4 记忆层）：
- 分层（working_set/session/knowledge/long_term）+ 生命周期 + 完整性；
- 无运算符面（记忆操作 = 显式方法调用）；
- 值语义：容器可变（引用），条目值冻结（深克隆快照）。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef


class MemoryAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "memory"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "encode":       _m("encode",       params=["str", "any", "str", "str"], ret="void"),
            "retrieve":     _m("retrieve",     params=["str"], ret="any"),
            "promote":      _m("promote",      params=["str", "str"], ret="void", mutating=True),
            "demote":       _m("demote",       params=["str", "str"], ret="void", mutating=True),
            "tier":         _m("tier",         params=["str"], ret="str"),
            "tier_size":    _m("tier_size",    params=["str"], ret="int"),
            "tier_keys":    _m("tier_keys",    params=["str"], ret="list"),
            "set_capacity": _m("set_capacity", params=["str", "any"], ret="void", mutating=True),
            "content_hash": _m("content_hash", params=["str"], ret="str"),
            "verify":       _m("verify",       params=["str"], ret="bool"),
            "consolidate":  _m("consolidate",  params=["dict"], ret="int", mutating=True),
            "prune":        _m("prune",        params=["dict"], ret="int", mutating=True),
            "recall":       _m("recall",       params=["str", "str", "int"], ret="list"),
            "keys":         _m("keys",         ret="list"),
            "len":          _m("len",          ret="int"),
            "export":       _m("export",       ret="dict"),
            "snapshot":     _m("snapshot",     ret="dict"),
            "cast_to":      _m("cast_to",      params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("memory", "str")

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "memory"

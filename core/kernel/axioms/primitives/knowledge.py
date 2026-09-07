"""
core/kernel/axioms/primitives/knowledge.py

KnowledgeAxiom —— 已验证知识注册表类型的公理声明。

knowledge = 一等内置值类型（语言自动机的知识层/D 纸带）：
- 容器约定与 dict 同构（keys/len）+ 铁律额外项（store/get/amend/history）；
- 无运算符面（知识操作 = 显式方法调用，无算术/比较语义）；
- 值语义要点：知识库可变（引用语义容器），条目值冻结（深克隆快照）。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef


class KnowledgeAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "knowledge"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "store":    _m("store",    params=["str", "any", "any"], ret="void"),
            "get":      _m("get",      params=["str"], ret="any"),
            "amend":    _m("amend",    params=["str", "any", "str"], ret="void", mutating=True),
            "history":  _m("history",  params=["str"], ret="list"),
            "keys":     _m("keys",     ret="list"),
            "len":      _m("len",      ret="int"),
            "cast_to":  _m("cast_to",  params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        # 知识面无运算符语义（操作 = 显式方法调用）
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("knowledge", "str")

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "knowledge"

"""
core/kernel/axioms/intent.py

IntentAxiom: 将 IbIntent 对象本身的行为约束纳入公理体系。

IbIntent 是 IbObject 的子类。本公理为类型系统提供 Intent 对象的属性
访问静态约束，并为运行时 vtable 提供形式化的方法声明。

设计：
- is_class() = True  — Intent 是类类型（有实例），不是原始值类型
- 无任何 capability —— Intent 对象不可调用、不可迭代、不可下标、不可运算
- get_method_specs() — 暴露 Intent 的公共读取接口
- is_compatible("Intent") → True

方法槽位：
  get_content() → str   返回意图内容字符串
  get_tag()     → str   返回意图标签（无标签时返回空字符串）
  get_mode()    → str   返回意图模式字符串 ("+", "!", "-")
"""
from __future__ import annotations

from typing import Dict, Optional
from core.kernel.spec.type_ref import TypeRef


def _m(name: str, params: Optional[list] = None, ret: str = "void"):
    from core.kernel.spec.member import MethodMemberSpec
    return MethodMemberSpec(
        name=name,
        kind="method",
        return_type=TypeRef.of(ret),
        param_types=[TypeRef.of(p) for p in (params or [])],
    )


class IntentAxiom:
    """
    公理：Intent 类型（运行时意图对象）。

    * is_class() = True
    * 无任何 capability
    * is_compatible 仅接受 "Intent" 自身
    * get_parent_axiom_name() = "Object"
    """

    # All capability flags default to False (matches BaseAxiom contract).
    has_call_cap = False
    has_iter_cap = False
    has_subscript_cap = False
    has_operator_cap = False
    has_converter_cap = False
    has_parser_cap = False
    has_from_prompt_cap = False
    has_output_hint_cap = False
    has_llm_call_cap = False

    @property
    def name(self) -> str:
        return "Intent"

    def get_method_specs(self):
        return {
            "get_content": _m("get_content", ret="str"),
            "get_tag":     _m("get_tag",     ret="str"),
            "get_mode":    _m("get_mode",    ret="str"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

    # ---- TypeAxiom required no-op defaults (no capabilities declared) ---- #
    def resolve_return_type_name(self, arg_type_names): return None
    def get_element_type_name(self) -> str: return "any"
    def resolve_item_type_name(self, key_type_name): return None
    def resolve_operation_type_name(self, op, other_name): return None
    def can_convert_from(self, source_type_name): return False
    def parse_value(self, raw_value): return raw_value
    def from_prompt(self, raw_response, spec=None): return (False, "Intent does not support from_prompt")
    def __outputhint_prompt__(self, spec=None) -> str: return ""

    def is_dynamic(self) -> bool:
        return False

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "Intent"

    def is_class(self) -> bool:
        return True

    def is_module(self) -> bool:
        return False

    def can_return_from_isolated(self) -> bool:
        return False

    def get_parent_axiom_name(self) -> Optional[str]:
        return "Object"

    def get_diff_hint(self, other_name: str) -> Optional[str]:
        return None

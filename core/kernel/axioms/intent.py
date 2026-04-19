"""
core/kernel/axioms/intent.py

IntentAxiom: 将 IbIntent 对象本身的行为约束纳入公理体系。

IntentAxiom 是 Intent 类型作为一等公民进入公理体系的关键步骤。
IbIntent 已经是 IbObject 的子类，但此前没有对应的公理定义，
因此类型系统无法对 Intent 对象的属性访问做静态检查，
运行时 vtable 也缺乏形式化的方法声明。

设计：
- is_class() = True  — Intent 是类类型（有实例），不是原始值类型
- 无 CallCapability  — Intent 对象不可直接调用
- 无 IterCapability  — Intent 对象不可迭代
- get_method_specs() — 暴露 Intent 的公共读取接口
- is_compatible("Intent") → True

方法槽位：
  get_content() → str   返回意图内容字符串
  get_tag()     → str   返回意图标签（无标签时返回空字符串）
  get_mode()    → str   返回意图模式字符串 ("+", "!", "-")
"""
from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.protocols import TypeAxiom
from core.kernel.spec.member import MethodMemberSpec


def _m(name: str, params: Optional[list] = None, ret: str = "void") -> MethodMemberSpec:
    return MethodMemberSpec(
        name=name,
        kind="method",
        param_type_names=params or [],
        return_type_name=ret,
    )


class IntentAxiom(TypeAxiom):
    """
    公理：Intent 类型（运行时意图对象）。

    * is_class() = True   — Intent 是具体的类类型，有实例，有 vtable
    * 无 CallCapability   — Intent 对象不可调用
    * is_compatible 仅接受 "Intent" 自身
    * get_parent_axiom_name() = "Object"
    """

    @property
    def name(self) -> str:
        return "Intent"

    def get_call_capability(self):
        return None

    def get_iter_capability(self):
        return None

    def get_subscript_capability(self):
        return None

    def get_operator_capability(self):
        return None

    def get_converter_capability(self):
        return None

    def get_parser_capability(self):
        return None

    def get_from_prompt_capability(self):
        return None

    def get_llmoutput_hint_capability(self):
        return None

    def get_writable_trait(self):
        return None

    def get_llm_call_capability(self):
        return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "get_content": _m("get_content", ret="str"),
            "get_tag":     _m("get_tag",     ret="str"),
            "get_mode":    _m("get_mode",    ret="str"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

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

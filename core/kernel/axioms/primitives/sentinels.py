"""
core/kernel/axioms/primitives/sentinels.py

Sentinel / special-value axioms: void, dynamic (any/auto/fn), None,
Optional, slice, llm_uncertain, llm_call_result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec


# ------------------------------------------------------------------ #
# void                                                                #
# ------------------------------------------------------------------ #

class VoidAxiom(BaseAxiom):
    """
    公理：void 类型（函数无返回值的类型标注）。

    void 不是 any 的别名，也不是 None 的别名——它是一个独立的一等公民类型，
    用于标注"此函数不返回任何值"的语义约束。
    * is_dynamic() = False —— void 是具体类型。
    * 无任何能力（不可调用、不可迭代、不可下标、不可运算）。
    * is_compatible 仅接受 "void" 自身。
    """

    @property
    def name(self) -> str:
        return "void"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "void"


# ------------------------------------------------------------------ #
# Dynamic (any / auto / fn)                                            #
# ------------------------------------------------------------------ #

class DynamicAxiom(BaseAxiom):
    """Top-type axiom: accepts and returns anything."""

    has_call_cap = True
    has_iter_cap = True
    has_subscript_cap = True
    has_operator_cap = True
    has_parser_cap = True

    def __init__(self, type_name: str):
        self._name = type_name

    @property
    def name(self) -> str:
        return self._name

    def is_dynamic(self) -> bool:
        return True

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "any"

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        return "any"

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        return "any"

    def parse_value(self, raw_value: str) -> Any:
        return raw_value.strip()

    def is_compatible(self, other_name: str) -> bool:
        return True


# ------------------------------------------------------------------ #
# None                                                                #
# ------------------------------------------------------------------ #

class NoneAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "None"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "cast_to": _m("cast_to", params=["any"], ret="any"),
            "to_bool": _m("to_bool", ret="bool"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "None"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "None"


# ------------------------------------------------------------------ #
# Optional                                                            #
# ------------------------------------------------------------------ #

class OptionalAxiom(BaseAxiom):
    @property
    def name(self) -> str:
        return "Optional"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "unwrap": _m("unwrap", ret="any"),
            "or_else": _m("or_else", params=["any"], ret="any"),
            "is_some": _m("is_some", ret="bool"),
            "to_bool": _m("to_bool", ret="bool"),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
            "__to_prompt__": _m("__to_prompt__", ret="str"),
        }

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "Optional" or other_name.startswith("Optional[")


# ------------------------------------------------------------------ #
# slice                                                               #
# ------------------------------------------------------------------ #

class SliceAxiom(BaseAxiom):
    @property
    def name(self) -> str:
        return "slice"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "slice"


# ------------------------------------------------------------------ #
# LLMUncertain                                                        #
# ------------------------------------------------------------------ #

class LLMUncertainAxiom(BaseAxiom):
    """
    公理：llm_uncertain 类型。

    [内部机制 — IBCI 用户不可见]

    语义（内核层）：
    - llmexcept 保护帧内，LLM 调用无法产生确定结果时，目标变量被赋值为此类型的单例
      （IbLLMUncertain 哨兵）。这是 VM 内部的快照/重试通信令牌，不应泄漏到用户代码。
    - llmexcept 块外：uncertain 状态不会出现（infra 失败 → LLMCallError；内容失败
      → LLMParseError/LLMRetryExhaustedError），对外完全不可见。
    - 布尔上下文中为假（is_truthy → False）。
    - 可以赋值给任何类型的变量（is_compatible 宽松策略）。
    - __to_prompt__ 返回 "uncertain"；cast_to str 返回 "uncertain"。
    - 支持 == 和 != 运算符。

    NOTE [未来演进路线 — 低优先级 PENDING]:
    - 用户自定义 UncertainResult；零参数 is_uncertain()。
    """

    has_operator_cap = True
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "llm_uncertain"

    def get_operators(self) -> Dict[str, str]:
        return {"==": "__eq__", "!=": "__ne__"}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if op in ("==", "!="):
            return "bool"
        return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "__to_prompt__": _m("__to_prompt__", ret="str"),
            "to_bool":       _m("to_bool",       ret="bool"),
            "cast_to":       _m("cast_to", params=["any"], ret="any"),
            "__eq__":        _m("__eq__",  params=["any"], ret="bool"),
            "__ne__":        _m("__ne__",  params=["any"], ret="bool"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        # 显式类型转换方向：只允许 llm_uncertain → llm_uncertain（同类转换）。
        return source_type_name == "llm_uncertain"

    def is_compatible(self, other_name: str) -> bool:
        # 赋值方向：llm_uncertain 值可被赋给任何类型的变量（宽松策略）。
        return True

    def can_return_from_isolated(self) -> bool:
        return True


# ------------------------------------------------------------------ #
# llm_call_result                                                      #
# ------------------------------------------------------------------ #

class LlmCallResultAxiom(BaseAxiom):
    """
    LLM 调用结果的类型公理。

    IbLLMCallResult 是 llmexcept 保护块的结果容器类型。

    Capabilities：
    - 无 operator / converter / parser capability（不参与常规类型运算）
    - 不可被用户变量声明（内核内部类型）
    """

    @property
    def name(self) -> str:
        return "llm_call_result"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "llm_call_result"

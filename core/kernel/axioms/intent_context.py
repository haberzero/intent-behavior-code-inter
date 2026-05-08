"""
core/kernel/axioms/intent_context.py

IntentContextAxiom: 意图上下文类型的公理定义。

IbIntentContext 是将意图栈从 RuntimeContextImpl 的私有字段群提升为
公理体系中独立一等公民类型的关键步骤。

方法槽位：
- fork()   → 返回当前上下文的不可变值快照（dispatch 时刻绑定）
- resolve()→ 返回当前有效意图字符串列表（供 LLMExecutor 组装提示词）
- push()   → 压入意图（@+ 语义，只修改当前帧，不影响父帧）
- pop()    → 弹出栈顶意图
- merge()  → 将 fork 快照内容合并回当前上下文（retry 恢复路径）
"""
from __future__ import annotations

from typing import Dict, List, Optional
from core.kernel.spec.type_ref import TypeRef


def _m(name: str, params: Optional[List[str]] = None, ret: str = "void"):
    from core.kernel.spec.member import MethodMemberSpec
    return MethodMemberSpec(
        name=name,
        kind="method",
        return_type=TypeRef.of(ret), param_types=[TypeRef.of(p) for p in params or []])


class IntentContextAxiom:
    """
    公理：intent_context 类型。

    * is_dynamic() = False — intent_context 是具体类型，不是 any 妥协。
    * 无任何 capability — 意图上下文不是可调用对象。
    * is_compatible 仅接受 "intent_context" 自身。
    * get_parent_axiom_name() = "Object"。
    """

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
        return "intent_context"

    def get_method_specs(self):
        return {
            "fork": _m("fork", ret="intent_context"),
            "resolve": _m("resolve", ret="any"),
            "push": _m("push", params=["any"], ret="void"),
            "pop": _m("pop", ret="any"),
            "merge": _m("merge", params=["intent_context"], ret="void"),
            "clear": _m("clear", ret="void"),
            "clear_inherited": _m("clear_inherited", ret="void"),
            "use": _m("use", params=["intent_context"], ret="void"),
            "get_current": _m("get_current", ret="intent_context"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

    # ---- No-op defaults for capability methods --------------------- #
    def resolve_return_type_name(self, arg_type_names): return None
    def get_element_type_name(self) -> str: return "any"
    def resolve_item_type_name(self, key_type_name): return None
    def resolve_operation_type_name(self, op, other_name): return None
    def can_convert_from(self, source_type_name): return False
    def parse_value(self, raw_value): return raw_value
    def from_prompt(self, raw_response, spec=None): return (False, "intent_context does not support from_prompt")
    def __outputhint_prompt__(self, spec=None) -> str: return ""

    def is_dynamic(self) -> bool:
        return False

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "intent_context"

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

"""
core/kernel/axioms/intent_context.py

IntentContextAxiom: 意图上下文类型的公理定义。

IbIntentContext 是将意图栈从 RuntimeContextImpl 的私有字段群提升为
公理体系中独立一等公民类型的关键步骤。

Capability 槽位：
- fork()   → 返回当前上下文的不可变值快照（dispatch 时刻绑定）
- resolve()→ 返回当前有效意图字符串列表（供 LLMExecutor 组装提示词）
- push()   → 压入意图（@+ 语义，只修改当前帧，不影响父帧）
- pop()    → 弹出栈顶意图
- merge()  → 将 fork 快照内容合并回当前上下文（retry 恢复路径）
"""
from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from core.kernel.axioms.protocols import TypeAxiom, CallCapability
from core.kernel.spec.member import MethodMemberSpec

if TYPE_CHECKING:
    from core.kernel.axioms.registry import AxiomRegistry


def _m(name: str, params: Optional[List[str]] = None, ret: str = "void") -> MethodMemberSpec:
    return MethodMemberSpec(
        name=name,
        kind="method",
        param_type_names=params or [],
        return_type_name=ret,
    )


class IntentContextAxiom(TypeAxiom):
    """
    公理：intent_context 类型。

    * is_dynamic() = False — intent_context 是具体类型，不是 any 妥协。
    * 无 CallCapability — 意图上下文不是可调用对象。
    * is_compatible 仅接受 "intent_context" 自身。
    * get_parent_axiom_name() = "Object"。
    """

    @property
    def name(self) -> str:
        return "intent_context"

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

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "fork": _m("fork", ret="intent_context"),
            "resolve": _m("resolve", ret="any"),
            "push": _m("push", params=["any"], ret="void"),
            "pop": _m("pop", ret="any"),
            "merge": _m("merge", params=["intent_context"], ret="void"),
            "clear": _m("clear", ret="void"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

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

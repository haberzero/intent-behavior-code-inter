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

from core.kernel.axioms.primitives.base import BaseAxiom, _m


class IntentContextAxiom(BaseAxiom):
    """
    公理：intent_context 类型。

    * is_dynamic() = False — intent_context 是具体类型，不是 any 妥协。
    * 无任何 capability — 意图上下文不是可调用对象。
    * is_compatible 仅接受 "intent_context" 自身。
    * get_parent_axiom_name() = "Object"。
    """

    @property
    def name(self) -> str:
        return "intent_context"

    def get_method_specs(self):
        return {
            "fork": _m("fork", ret="intent_context"),
            "resolve": _m("resolve", ret="any"),
            "push": _m("push", params=["any"], ret="void", mutating=True),
            "pop": _m("pop", ret="any", mutating=True),
            "merge": _m("merge", params=["intent_context"], ret="void", mutating=True),
            "combine": _m("combine", params=["intent_context"], ret="void", mutating=True),
            "clear": _m("clear", ret="void", mutating=True),
            "clear_inherited": _m("clear_inherited", ret="void", mutating=True),
            "use": _m("use", params=["intent_context"], ret="void", mutating=True),
            "get_current": _m("get_current", ret="intent_context"),
            "__to_prompt__": _m("__to_prompt__", ret="str"),
        }

    def is_class(self) -> bool:
        return True

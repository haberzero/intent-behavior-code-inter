"""
core/runtime/objects/intent_context.py

IbIntentContext: 意图上下文的运行时对象。

将意图栈从 RuntimeContextImpl 的私有字段群提升为公理化的独立类型。

核心设计原则：
- fork() 返回**值快照**（不是引用）——修改 fork 结果不影响原上下文
- push() 只修改当前实例，不影响 _parent_ref 指向的父上下文
- 与普通变量的传值/传引用语义完全对齐

为什么 fork() 是 LLM 流水线正确性的前提：
  dispatch 时必须绑定此时刻的完整意图上下文，而不是等到 resolve 时再读取
  （那时意图栈可能已因 @+ 操作而改变）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject, IbClass
    from core.runtime.interpreter.runtime_context import IntentNode
    from core.runtime.objects.intent import IbIntent, IntentMode


class IbIntentContext:
    """
    意图上下文运行时对象。

    内部结构（镜像 RuntimeContextImpl 当前实现，方便 Step 6c 迁移）：
    - _intent_top: Optional[IntentNode]     持久意图栈顶节点（不可变链表，结构共享）
    - _smear_queue: List[IbIntent]          一次性涂抹意图队列（@ 语义）
    - _override: Optional[IbIntent]         排他意图槽（@! 语义）
    - _global_intents: List[IbIntent]       全局意图列表（Engine 级，由外部注入）

    语义约束：
    - fork() 返回的是值快照，不是引用——修改 fork 结果不影响原上下文
    - push() 只修改当前 IbIntentContext 实例，不影响父上下文引用
    """

    def __init__(
        self,
        intent_top: Optional[Any] = None,
        smear_queue: Optional[List[Any]] = None,
        override: Optional[Any] = None,
        global_intents: Optional[List[Any]] = None,
    ) -> None:
        self._intent_top = intent_top
        self._smear_queue: List[Any] = smear_queue if smear_queue is not None else []
        self._override: Optional[Any] = override
        self._global_intents: List[Any] = global_intents if global_intents is not None else []

    # ------------------------------------------------------------------ #
    # Core capability: fork() — value snapshot                            #
    # ------------------------------------------------------------------ #

    def fork(self) -> "IbIntentContext":
        """
        返回当前意图上下文的值快照（不可变副本）。

        用途：
        1. LLM 流水线 dispatch 时刻：为 Future 绑定此刻的意图快照
        2. LLMExceptFrame.save_context()：安全地保存意图状态（不是裸引用）

        设计：_intent_top 是不可变链表（IntentNode），结构共享是安全的。
        _smear_queue 和 _override 需要浅拷贝（它们在消费后清除，不会被修改）。
        """
        return IbIntentContext(
            intent_top=self._intent_top,          # 不可变链表，结构共享安全
            smear_queue=list(self._smear_queue),  # 浅拷贝，避免消费影响快照
            override=self._override,              # Optional 标量，安全
            global_intents=list(self._global_intents),  # 浅拷贝
        )

    # ------------------------------------------------------------------ #
    # Intent stack operations (mirrors RuntimeContextImpl)                #
    # ------------------------------------------------------------------ #

    def push(self, intent: Any, parent_node: Optional[Any] = None) -> None:
        """
        压入持久意图（@+ 语义）。
        仅修改当前 IbIntentContext 实例，不影响父上下文。
        """
        from core.runtime.interpreter.runtime_context import IntentNode
        self._intent_top = IntentNode(intent, self._intent_top)

    def pop(self) -> Optional[Any]:
        """弹出栈顶意图。"""
        if self._intent_top is not None:
            intent = self._intent_top.intent
            self._intent_top = self._intent_top.parent
            return intent
        return None

    def add_smear(self, intent: Any) -> None:
        """添加一次性涂抹意图（@ 语义）。"""
        self._smear_queue.append(intent)

    def consume_smear(self) -> List[Any]:
        """消费并清除所有涂抹意图。"""
        result = list(self._smear_queue)
        self._smear_queue.clear()
        return result

    def set_override(self, intent: Any) -> None:
        """设置排他意图（@! 语义）。"""
        self._override = intent

    def consume_override(self) -> Optional[Any]:
        """消费并清除排他意图。"""
        intent = self._override
        self._override = None
        return intent

    def has_override(self) -> bool:
        return self._override is not None

    def get_active_intents(self) -> List[Any]:
        """获取持久意图栈的内容（展平为列表）。"""
        if self._intent_top is None:
            return []
        return self._intent_top.to_list()

    def merge(self, snapshot: "IbIntentContext") -> None:
        """
        将快照的意图状态合并回当前上下文（retry 恢复路径）。
        这是 LLMExceptFrame.restore_context() 的正确实现方式。
        """
        self._intent_top = snapshot._intent_top
        self._smear_queue = list(snapshot._smear_queue)
        self._override = snapshot._override

    def set_global_intents(self, intents: List[Any]) -> None:
        self._global_intents = list(intents)

    def get_global_intents(self) -> List[Any]:
        return list(self._global_intents)

    def get_intent_top(self) -> Optional[Any]:
        """返回持久意图栈顶节点（IntentNode 链表头）。供 intent_stack property 使用。"""
        return self._intent_top

    def set_intent_top(self, node: Optional[Any]) -> None:
        """直接设置栈顶节点（用于 intent_stack setter / restore_active_intents）。"""
        self._intent_top = node

    def remove(self, tag: Optional[str] = None, content: Optional[str] = None) -> bool:
        """
        从持久意图栈中物理移除匹配的意图（栈顶优先）。

        - tag   → 按标签移除（最近压入的匹配 tag 的意图）
        - content → 按内容移除
        返回是否成功移除。
        """
        if not self._intent_top:
            return False

        if tag and self._remove_by_tag(tag):
            return True
        if content and self._remove_by_content(content):
            return True
        return False

    def _remove_by_tag(self, tag: str) -> bool:
        """按标签移除意图（栈顶优先）。

        通过重建不含目标节点的新链表来实现移除，保证结构共享安全
        （旧代码通过原地修改 previous.parent 破坏共享结构的 Bug 已修复）。
        """
        from core.runtime.interpreter.runtime_context import IntentNode
        intents: List[Any] = []
        found = False
        current = self._intent_top
        while current:
            if not found and getattr(current.intent, 'tag', None) == tag:
                found = True  # 跳过该节点（不加入 intents）
            else:
                intents.append(current.intent)
            current = current.parent
        if not found:
            return False
        # intents 是从栈顶到栈底的顺序，重建时从栈底向上压入
        self._intent_top = None
        for intent in reversed(intents):
            self._intent_top = IntentNode(intent, self._intent_top)
        return True

    def _remove_by_content(self, content: str) -> bool:
        """按内容移除意图（栈顶优先）。

        通过重建不含目标节点的新链表来实现移除，保证结构共享安全
        （旧代码通过原地修改 previous.parent 破坏共享结构的 Bug 已修复）。
        """
        from core.runtime.interpreter.runtime_context import IntentNode
        intents: List[Any] = []
        found = False
        current = self._intent_top
        while current:
            if not found and hasattr(current.intent, 'content') and getattr(current.intent, 'content', None) == content:
                found = True  # 跳过该节点
            else:
                intents.append(current.intent)
            current = current.parent
        if not found:
            return False
        self._intent_top = None
        for intent in reversed(intents):
            self._intent_top = IntentNode(intent, self._intent_top)
        return True

    # ------------------------------------------------------------------ #
    # Convenience                                                          #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        stack_depth = 0
        node = self._intent_top
        while node:
            stack_depth += 1
            node = node.parent
        return (
            f"IbIntentContext("
            f"stack_depth={stack_depth}, "
            f"smear={len(self._smear_queue)}, "
            f"override={'yes' if self._override else 'no'})"
        )

from typing import List, Optional, TYPE_CHECKING
from core.runtime.objects.kernel import IbObject, IbClass
from core.kernel.intent_logic import IntentMode, IntentRole

if TYPE_CHECKING:
    from core.runtime.interpreter.runtime_context import RuntimeContextImpl
    from core.runtime.registry import Registry

class IbIntentStack(IbObject):
    """
    意图栈类：作为 IBCI 内置类，封装全局意图栈操作。

    实现 UTS 协议，可被 IBCI 代码直接操作。

    语法糖映射：
    - @ "content" → IntentStack.push(Intent(content, APPEND))
    - @+ "content" → IntentStack.push(Intent(content, APPEND))
    - @! "content" → IntentStack.push(Intent(content, OVERRIDE))
    - @- #tag → IntentStack.pop(tag=tag)
    - @- → IntentStack.pop() (移除栈顶意图)
    """
    __slots__ = ('_runtime_context',)

    def __init__(self, ib_class: IbClass, runtime_context: 'RuntimeContextImpl' = None):
        super().__init__(ib_class)
        self._runtime_context = runtime_context

    def set_runtime_context(self, runtime_context: 'RuntimeContextImpl'):
        """设置运行时上下文（由解释器在初始化时调用）"""
        self._runtime_context = runtime_context

    def push(self, intent_content: str, mode: str = "+", tag: Optional[str] = None) -> None:
        """
        压入意图到栈。

        IBCI 用法示例：
            IntentStack.push("用中文回复")
            IntentStack.push("用中文回复", "+", "language")
        """
        if self._runtime_context:
            self._runtime_context.push_intent(
                intent_content,
                mode=mode,
                tag=tag
            )

    def pop(self, tag: Optional[str] = None) -> Optional[IbObject]:
        """
        从栈中弹出意图。

        IBCI 用法示例：
            IntentStack.pop()
            IntentStack.pop("language")
        """
        if self._runtime_context:
            return self._runtime_context.pop_intent()
        return None

    def clear(self) -> None:
        """
        清空意图栈。

        IBCI 用法示例：
            IntentStack.clear()
        """
        if self._runtime_context:
            self._runtime_context.restore_active_intents([])

    def get_active(self) -> List[IbObject]:
        """
        获取当前活跃的意图列表。

        IBCI 用法示例：
            intents = IntentStack.get_active()
        """
        if self._runtime_context:
            return self._runtime_context.get_active_intents()
        return []

    def resolve(self, call_intent: Optional[str] = None) -> List[str]:
        """
        消解意图为 Prompt 字符串列表。

        IBCI 用法示例：
            prompts = IntentStack.resolve()
        """
        if self._runtime_context:
            return self._runtime_context.get_resolved_prompt_intents(
                execution_context=None,
                call_intent=None
            )
        return []

    def __iter__(self):
        """支持迭代协议"""
        intents = self.get_active()
        return iter(intents)

    def __len__(self) -> int:
        """支持长度协议"""
        return len(self.get_active())

    def __repr__(self):
        count = len(self.get_active()) if self._runtime_context else 0
        return f"<IntentStack size={count}>"

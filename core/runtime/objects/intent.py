from typing import List, Optional, Any, Union, Dict, TYPE_CHECKING
from core.runtime.interfaces import RuntimeContext
from core.runtime.objects.kernel import IbObject, IbClass
from core.domain.intent_logic import IntentMode, IntentRole, IntentProtocol

if TYPE_CHECKING:
    from core.runtime.interpreter.llm_executor import LLMExecutorImpl

class IbIntent(IbObject, IntentProtocol):
    """
    表示运行时的意图对象。
    封装了意图的内容、模式以及来源信息。
    现在是真正的 IbObject 子类 (Everything is an Object)。
    """
    __slots__ = ('content', 'segments', 'mode', 'tag', 'source_uid', 'role')
    
    def __init__(self, ib_class: IbClass, content: str = "", segments: List[Any] = None, 
                 mode: IntentMode = IntentMode.APPEND, tag: Optional[str] = None,
                 source_uid: Optional[str] = None, role: IntentRole = IntentRole.BLOCK):
        super().__init__(ib_class)
        self.content = content
        self.segments = segments if segments is not None else []
        self.mode = mode
        self.tag = tag
        self.source_uid = source_uid
        self.role = role

    def resolve_content(self, context: RuntimeContext, evaluator: Any = None) -> str:
        """
        解析意图内容。如果存在 segments，则进行动态评估。
        evaluator: 通常是 LLMExecutor 实例，用于调用 _evaluate_segments
        """
        if self.segments and evaluator:
            # 这里我们需要回调 evaluator 的 _evaluate_segments 方法
            if hasattr(evaluator, '_evaluate_segments'):
                return evaluator._evaluate_segments(self.segments, context).strip()
        
        return str(self.content).strip()

    @property
    def is_override(self) -> bool:
        return self.mode == IntentMode.OVERRIDE

    @property
    def is_remove(self) -> bool:
        return self.mode == IntentMode.REMOVE
    
    def __repr__(self):
        tag_str = f" tag={self.tag}" if self.tag else ""
        return f"<Intent mode={self.mode.name}{tag_str} role={self.role.value} content='{self.content[:20]}...'>"

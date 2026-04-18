from typing import List, Optional, Any, Union, Dict, TYPE_CHECKING, Mapping
from core.runtime.interfaces import RuntimeContext
from core.runtime.objects.kernel import IbObject, IbClass
from core.kernel.intent_logic import IntentMode, IntentRole

if TYPE_CHECKING:
    from core.runtime.interpreter.llm_executor import LLMExecutorImpl

class IbIntent(IbObject):
    """
    表示运行时的意图对象。
    封装了意图的内容、模式以及来源信息。
    现在是真正的 IbObject 子类 (Everything is an Object)。
    """
    __slots__ = ('content', 'segments', 'mode', 'tag', 'source_uid', 'role', 'pop_top')
    
    def __init__(self, ib_class: IbClass, content: str = "", segments: List[Any] = None, 
                 mode: IntentMode = IntentMode.APPEND, tag: Optional[str] = None,
                 source_uid: Optional[str] = None, role: IntentRole = IntentRole.BLOCK,
                 pop_top: bool = False):
        super().__init__(ib_class)
        self.content = content
        self.segments = segments if segments is not None else []
        self.mode = mode
        self.tag = tag
        self.source_uid = source_uid
        self.role = role
        self.pop_top = pop_top

    @staticmethod
    def from_node_data(node_uid: str, node_data: Mapping[str, Any], ib_class: IbClass, role: IntentRole = IntentRole.BLOCK) -> 'IbIntent':
        """
        从 AST 节点数据构造运行时意图对象。
        """
        return IbIntent(
            ib_class=ib_class,
            content=node_data.get('content', ''),
            segments=node_data.get('segments', []),
            mode=IntentMode.from_str(node_data.get('mode', '+')),
            tag=node_data.get('tag'),
            role=role,
            source_uid=node_uid,
            pop_top=node_data.get('pop_top', False)
        )

    def resolve_content(self, context: RuntimeContext, execution_context: Any = None) -> str:
        """
        解析意图内容。
        不再反向回调 LLMExecutor，而是直接利用 IExecutionContext 的 visit 能力进行自评估。
        """
        if self.segments and execution_context:
            content_parts = []
            for segment in self.segments:
                if isinstance(segment, str) and segment.startswith("node_"):
                    # 动态节点插值：通过执行上下文网关进行求值
                    val = execution_context.visit(segment)
                    if hasattr(val, '__to_prompt__'):
                        content_parts.append(val.__to_prompt__())
                    elif hasattr(val, 'to_native'):
                        content_parts.append(str(val.to_native()))
                    else:
                        content_parts.append(str(val))
                else:
                    content_parts.append(str(segment))
            return "".join(content_parts).strip()
        
        return str(self.content).strip()

    @property
    def is_override(self) -> bool:
        return self.mode == IntentMode.OVERRIDE

    @property
    def is_remove(self) -> bool:
        return self.mode == IntentMode.REMOVE
    
    @property
    def is_pop_top(self) -> bool:
        """判断是否为无参数的 @-（移除栈顶意图）"""
        return self.mode == IntentMode.REMOVE and self.pop_top
    
    def __repr__(self):
        tag_str = f" tag={self.tag}" if self.tag else ""
        return f"<Intent mode={self.mode.name}{tag_str} role={self.role.value} content='{self.content[:20]}...'>"

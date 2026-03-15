from typing import Any, Mapping, Optional, List, Dict, TYPE_CHECKING
from core.foundation.interfaces import IExecutionContext, IStackInspector

if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject

class ExecutionContextImpl(IExecutionContext, IStackInspector):
    """
    [IES 2.1 Decoupling] 运行时执行上下文的具体实现。
    它作为纯状态容器，持有 node_pool、栈和运行时上下文的引用。
    同时，它持有指向 Interpreter 逻辑的回调函数，以实现物理层面的逻辑与数据分离。
    """
    def __init__(self, 
                 registry: Any,
                 visit_callback: Any,
                 get_node_data_callback: Any,
                 get_side_table_callback: Any,
                 push_stack_callback: Any,
                 pop_stack_callback: Any,
                 get_instruction_count_callback: Any,
                 get_captured_intents_callback: Any):
        self._node_pool: Mapping[str, Any] = {}
        self._registry = registry
        self._runtime_context = None
        self._logical_stack = None # 由 Interpreter 初始化并注入
        
        # Logic Callbacks
        self._visit_callback = visit_callback
        self._get_node_data_callback = get_node_data_callback
        self._get_side_table_callback = get_side_table_callback
        self._push_stack_callback = push_stack_callback
        self._pop_stack_callback = pop_stack_callback
        self._get_instruction_count_callback = get_instruction_count_callback
        self._get_captured_intents_callback = get_captured_intents_callback

    @property
    def logical_stack(self) -> Any:
        return self._logical_stack

    @logical_stack.setter
    def logical_stack(self, value: Any):
        self._logical_stack = value

    @property
    def node_pool(self) -> Mapping[str, Any]:
        return self._node_pool

    @node_pool.setter
    def node_pool(self, value: Mapping[str, Any]):
        self._node_pool = value

    @property
    def stack_inspector(self) -> IStackInspector:
        return self

    @property
    def registry(self) -> Any:
        return self._registry

    @property
    def runtime_context(self) -> Any:
        return self._runtime_context

    @runtime_context.setter
    def runtime_context(self, value: Any):
        self._runtime_context = value

    def visit(self, node_uid: str) -> 'IbObject':
        return self._visit_callback(node_uid)

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]:
        return self._get_node_data_callback(node_uid)

    def get_side_table(self, table_name: str, key: str) -> Any:
        return self._get_side_table_callback(table_name, key)

    def push_stack(self, name: str, location: Optional[Any] = None, is_user_function: bool = False, **kwargs) -> None:
        self._push_stack_callback(name, location, is_user_function, **kwargs)

    def pop_stack(self) -> None:
        self._pop_stack_callback()

    # IStackInspector Implementation (Delegated to Data or Callback)
    def get_call_stack_depth(self) -> int:
        return self._logical_stack.depth if self._logical_stack else 0

    def get_active_intents(self) -> List[str]:
        return [i.content for i in self.runtime_context.get_active_intents()] if self.runtime_context else []

    def get_instruction_count(self) -> int:
        return self._get_instruction_count_callback()

    def get_captured_intents(self, obj: Any) -> List[str]:
        return self._get_captured_intents_callback(obj)

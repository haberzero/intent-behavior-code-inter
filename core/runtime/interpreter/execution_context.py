import os
from typing import Any, Mapping, Optional, List, Dict, TYPE_CHECKING, Callable
from core.runtime.interfaces import IExecutionContext, IStackInspector
from core.runtime.interpreter.ast_view import ReadOnlyNodePool
from core.runtime.interpreter.call_stack import LogicalCallStack, StackFrame

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
                 factory: Any,
                 visit_callback: Any,
                 get_node_data_callback: Any,
                 get_side_table_callback: Any,
                 push_stack_callback: Any,
                 pop_stack_callback: Any,
                 get_instruction_count_callback: Any,
                 get_captured_intents_callback: Any,
                 is_truthy_callback: Any,
                 resolve_type_from_symbol_callback: Any,
                 extract_name_id_callback: Any,
                 resolve_value_callback: Any,
                 visit_with_fallback_callback: Any,
                 module_manager: Any = None,
                 strict_mode: bool = False):
        self._node_pool: Mapping[str, Any] = {}
        self._symbol_pool: Mapping[str, Any] = {}
        self._scope_pool: Mapping[str, Any] = {}
        self._type_pool: Mapping[str, Any] = {}
        self._asset_pool: Mapping[str, str] = {}
        self._registry = registry
        self._factory = factory
        self._runtime_context = None
        self._logical_stack = None # 由 Interpreter 初始化并注入
        self._current_module_name = None # [IES 2.1]
        self._module_manager = module_manager
        self._strict_mode = strict_mode
        
        # Logic Callbacks
        self._visit_callback = visit_callback
        self._get_node_data_callback = get_node_data_callback
        self._get_side_table_callback = get_side_table_callback
        self._push_stack_callback = push_stack_callback
        self._pop_stack_callback = pop_stack_callback
        self._get_instruction_count_callback = get_instruction_count_callback
        self._get_captured_intents_callback = get_captured_intents_callback
        self._is_truthy_callback = is_truthy_callback
        self._resolve_type_from_symbol_callback = resolve_type_from_symbol_callback
        self._extract_name_id_callback = extract_name_id_callback
        self._resolve_value_callback = resolve_value_callback
        self._visit_with_fallback_callback = visit_with_fallback_callback

    @property
    def logical_stack(self) -> Any:
        return self._logical_stack

    @logical_stack.setter
    def logical_stack(self, value: Any):
        self._logical_stack = value

    @property
    def current_module_name(self) -> Optional[str]:
        return self._current_module_name

    @current_module_name.setter
    def current_module_name(self, value: Optional[str]):
        self._current_module_name = value

    @property
    def node_pool(self) -> Mapping[str, Any]:
        return self._node_pool

    @node_pool.setter
    def node_pool(self, value: Mapping[str, Any]):
        self._node_pool = value

    @property
    def symbol_pool(self) -> Mapping[str, Any]:
        return self._symbol_pool

    @symbol_pool.setter
    def symbol_pool(self, value: Mapping[str, Any]):
        self._symbol_pool = value

    @property
    def scope_pool(self) -> Mapping[str, Any]:
        return self._scope_pool

    @scope_pool.setter
    def scope_pool(self, value: Mapping[str, Any]):
        self._scope_pool = value

    @property
    def type_pool(self) -> Mapping[str, Any]:
        return self._type_pool

    @type_pool.setter
    def type_pool(self, value: Mapping[str, Any]):
        self._type_pool = value

    @property
    def asset_pool(self) -> Mapping[str, str]:
        return self._asset_pool

    @asset_pool.setter
    def asset_pool(self, value: Mapping[str, str]):
        self._asset_pool = value

    @property
    def stack_inspector(self) -> IStackInspector:
        return self

    @property
    def registry(self) -> Any:
        return self._registry

    @property
    def factory(self) -> Any:
        return self._factory

    @property
    def runtime_context(self) -> Any:
        return self._runtime_context

    @runtime_context.setter
    def runtime_context(self, value: Any):
        self._runtime_context = value

    @property
    def module_manager(self) -> Any:
        return self._module_manager

    @module_manager.setter
    def module_manager(self, value: Any):
        self._module_manager = value

    @property
    def strict_mode(self) -> bool:
        return self._strict_mode

    @strict_mode.setter
    def strict_mode(self, value: bool):
        self._strict_mode = value

    def visit(self, node_uid: str, module_name: Optional[str] = None) -> 'IbObject':
        return self._visit_callback(node_uid, module_name=module_name)

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]:
        return self._get_node_data_callback(node_uid)

    def get_side_table(self, table_name: str, key: str) -> Any:
        return self._get_side_table_callback(table_name, key)

    def push_stack(self, name: str, location: Optional[Any] = None, is_user_function: bool = False, **kwargs) -> None:
        self._push_stack_callback(name, location, is_user_function, **kwargs)

    def pop_stack(self) -> None:
        self._pop_stack_callback()

    def is_truthy(self, value: Any) -> bool:
        return self._is_truthy_callback(value)

    def resolve_type_from_symbol(self, sym_uid: str) -> Optional[Any]:
        return self._resolve_type_from_symbol_callback(sym_uid)

    def extract_name_id(self, node_uid: str) -> Optional[str]:
        return self._extract_name_id_callback(node_uid)

    def resolve_value(self, val: Any) -> Any:
        return self._resolve_value_callback(val)

    def visit_with_fallback(self, node_uid: str, node_type: str, node_data: Mapping[str, Any], action: Callable) -> 'IbObject':
        return self._visit_with_fallback_callback(node_uid, node_type, node_data, action)

    # IStackInspector Implementation (Delegated to Data or Callback)
    def get_call_stack_depth(self) -> int:
        return self._logical_stack.depth if self._logical_stack else 0

    def get_active_intents(self) -> List[str]:
        return [i.content for i in self.runtime_context.get_active_intents()] if self.runtime_context else []

    def get_instruction_count(self) -> int:
        return self._get_instruction_count_callback()

    def get_captured_intents(self, obj: Any) -> List[str]:
        return self._get_captured_intents_callback(obj)

    def get_current_script_path(self) -> Optional[str]:
        if self._logical_stack and self._logical_stack.frames:
            # 从调用栈中查找最近的一个具有 Location 的帧
            for frame in reversed(self._logical_stack.frames):
                if frame.location and frame.location.file_path:
                    return os.path.abspath(frame.location.file_path)
        return None

    def get_current_script_dir(self) -> Optional[str]:
        path = self.get_current_script_path()
        return os.path.dirname(path) if path else None

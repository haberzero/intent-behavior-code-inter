import os
from typing import Any, Mapping, Optional, List, Dict, TYPE_CHECKING, Callable
from core.runtime.interfaces import IExecutionContext, IStackInspector
from core.runtime.interpreter.ast_view import ReadOnlyNodePool
from core.runtime.interpreter.call_stack import LogicalCallStack, StackFrame
from core.runtime.path import IbPath

if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject

class ExecutionContextImpl:
    """
    运行时执行上下文的具体实现。
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
                 module_manager: Any = None,
                 strict_mode: bool = False,
                 entry_file: str = None,
                 entry_dir: str = None):
        self._node_pool: Mapping[str, Any] = {}
        self._symbol_pool: Mapping[str, Any] = {}
        self._scope_pool: Mapping[str, Any] = {}
        self._type_pool: Mapping[str, Any] = {}
        self._asset_pool: Mapping[str, str] = {}
        self._registry = registry
        self._factory = factory
        self._runtime_context = None
        self._logical_stack = None # 由 Interpreter 初始化并注入
        self._current_module_name = None
        self._module_manager = module_manager
        self._strict_mode = strict_mode
        self._entry_file = entry_file
        self._entry_dir = entry_dir
        # C13：VMExecutor 直接引用（由 Interpreter 在构造完成后注入）。
        # 替代 IbUserFunction.call() 中通过 self.context._interpreter._get_vm_executor()
        # 三级 getattr 的脆弱查找路径。M4 多 Interpreter 并发场景下，每个执行上下文
        # 必须通过此属性直接获得对应的 VMExecutor，避免静默 fallback。
        self._vm_executor: Optional[Any] = None
        
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
    def vm_executor(self) -> Any:
        """C13：当前 ExecutionContext 关联的 VMExecutor（由 Interpreter 注入）。

        当 IbUserFunction.call() 等代码需要驱动函数体语句的 CPS 执行时，应通过
        本属性获取 VMExecutor，而不是穿透到 ``self._interpreter`` 上调用
        ``_get_vm_executor()``。在 M4 多 Interpreter 并发场景下，每个 ExecutionContext
        关联其专属 VMExecutor，避免线程间相互查找的 race condition。

        若 Interpreter 尚未完成 VMExecutor 注入，返回 ``None``；调用方需要
        显式处理（不应静默降级到递归路径）。
        """
        return self._vm_executor

    @vm_executor.setter
    def vm_executor(self, value: Any) -> None:
        self._vm_executor = value

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

    def visit(self, node_uid: str, module_name: Optional[str] = None, bypass_protection: bool = False) -> 'IbObject':
        return self._visit_callback(node_uid, module_name=module_name, bypass_protection=bypass_protection)

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
        """
        获取当前脚本的绝对路径

        返回:
            Optional[str]: 脚本绝对路径（字符串格式），未找到则返回 None
        """
        if self._logical_stack and self._logical_stack.frames:
            for frame in reversed(self._logical_stack.frames):
                if frame.location and frame.location.file_path:
                    ib_path = IbPath.from_native(frame.location.file_path)
                    return ib_path.resolve_dot_segments().to_native()
        return None

    def get_current_script_dir(self) -> Optional[str]:
        """
        获取当前脚本所在目录

        返回:
            Optional[str]: 脚本目录（字符串格式），未找到则返回 None
        """
        path = self.get_current_script_path()
        if path:
            ib_path = IbPath.from_native(path)
            parent = ib_path.parent
            return parent.to_native() if parent else None
        return None

    def get_entry_path(self) -> Optional[str]:
        """获取入口文件路径"""
        return self._entry_file

    def get_entry_dir(self) -> Optional[str]:
        """获取入口文件目录"""
        return self._entry_dir

    def resolve_path(self, path: str) -> IbPath:
        """
        所有相对路径的统一解析入口

        所有相对路径都基于入口文件目录解析，确保无论在哪个 IBCI 文件中执行，
        相对路径都相对于入口文件目录。
        """
        if not path:
            return IbPath.from_native("")

        ib_path = IbPath.from_native(path)

        if ib_path.is_absolute:
            return ib_path.resolve_dot_segments()

        if self._entry_dir:
            return (IbPath.from_native(self._entry_dir) / ib_path).resolve_dot_segments()

        return ib_path

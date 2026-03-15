from typing import Any, Protocol, Optional, List, Dict, Union, Mapping, runtime_checkable

# --- Diagnostics ---

@runtime_checkable
class ISourceProvider(Protocol):
    """
    源码提供者接口。支持“无盘化”诊断，从内存缓冲区获取代码片段。
    """
    def get_line(self, file_path: str, lineno: int) -> Optional[str]: ...
    def get_full_source(self, file_path: str) -> Optional[str]: ...

@runtime_checkable
class ICompilerService(Protocol):
    """
    编译器服务接口。允许运行时动态编译代码或查询模块信息。
    """
    def compile_file(self, file_path: str) -> Any: ...
    def resolve_module_path(self, module_name: str) -> Optional[str]: ...
    def get_module_source(self, module_name: str) -> Optional[str]: ...

@runtime_checkable
class IssueTracker(Protocol):
    """诊断管理器接口"""
    def report(self, severity: Any, code: str, message: str, 
               location: Optional[Any] = None, hint: Optional[str] = None) -> None: ...
    def has_errors(self) -> bool: ...

# --- Execution Context ---

@runtime_checkable
class IExecutionContext(Protocol):
    """
    [IES 2.1 Decoupling] 运行时执行上下文数据协议。
    作为 Interpreter 与底层组件（Kernel/Foundation）解耦的桥梁。
    它仅包含执行所需的只读数据池、栈内省能力以及求值入口。
    """
    @property
    def node_pool(self) -> Mapping[str, Any]: ...
    
    @property
    def stack_inspector(self) -> 'IStackInspector': ...
    
    @property
    def registry(self) -> Any: ...
    
    @property
    def runtime_context(self) -> Any: ...
    
    def visit(self, node_uid: str) -> Any:
        """评估 AST 节点并返回 IbObject"""
        ...

    def get_node_data(self, node_uid: str) -> Mapping[str, Any]: ...
    
    def get_side_table(self, table_name: str, key: str) -> Any: ...

    def push_stack(self, name: str, location: Optional[Any] = None, is_user_function: bool = False, **kwargs) -> None:
        """向逻辑调用栈压入一帧"""
        ...

    def pop_stack(self) -> None:
        """从逻辑调用栈弹出最后一帧"""
        ...

# --- IBCI Core Object Protocol ---

@runtime_checkable
class IIbObject(Protocol):
    """
    IBC-Inter 统一对象模型协议。
    允许插件在不导入 runtime.objects 的情况下识别并操作 IBC 对象。
    """
    ib_class: Any
    fields: Dict[str, Any]
    def receive(self, message: str, args: List[Any]) -> Any: ...
    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any: ...
    def serialize_for_debug(self) -> Dict[str, Any]: ...

# --- Extension Capabilities & Introspection ---

@runtime_checkable
class IStateReader(Protocol):
    """提供对解释器运行时状态（如变量）的只读访问"""
    def get_vars_snapshot(self) -> Dict[str, Any]:
        """获取当前可见的所有变量快照"""
        ...

@runtime_checkable
class ISymbolView(Protocol):
    """只读符号视图接口"""
    def get(self, name: str) -> Any: ...
    def get_symbol(self, name: str) -> Optional[Any]: ...
    def has(self, name: str) -> bool: ...

@runtime_checkable
class IStackInspector(Protocol):
    """提供对调用栈和意图栈的内省能力"""
    def get_call_stack_depth(self) -> int:
        ...
    def get_active_intents(self) -> List[str]:
        ...
    def get_instruction_count(self) -> int:
        ...
    def get_captured_intents(self, obj: Any) -> List[str]:
        """获取指定对象（如 Lambda）捕获的意图栈"""
        ...

@runtime_checkable
class ILLMProvider(Protocol):
    """LLM 服务提供者标准接口"""
    def __call__(self, sys_prompt: str, user_prompt: str, scene: str = "general") -> str:
        ...
    def get_last_call_info(self) -> Dict[str, Any]:
        ...
    def set_retry_hint(self, hint: str) -> None:
        ...

@runtime_checkable
class ILLMExecutor(Protocol):
    """提供对内核 LLM 执行器的内省能力"""
    def get_last_call_info(self) -> Dict[str, Any]: ...

@runtime_checkable
class IIntentManager(Protocol):
    """提供对意图（Global, Block）的管理能力"""
    def set_global_intent(self, intent: Union[str, 'IbIntent']) -> None: ...
    def clear_global_intents(self) -> None: ...
    def remove_global_intent(self, intent: Union[str, 'IbIntent']) -> None: ...
    def get_global_intents(self) -> List[Any]: ...
    def get_active_intents(self) -> List[Any]: ...
    def push_intent(self, intent: Union[str, Any], mode: str = "+", tag: Optional[str] = None) -> None: ...

class ExtensionCapabilities:
    """扩展模块持有的能力集合容器 (IES 2.0 SDK)"""
    def __init__(self, registry: Optional[Any] = None):
        self.stack_inspector: Optional[IStackInspector] = None
        self.llm_provider: Optional[ILLMProvider] = None
        self.llm_executor: Optional[ILLMExecutor] = None
        self.intent_manager: Optional[IIntentManager] = None
        self.state_reader: Optional[IStateReader] = None
        self.symbol_view: Optional[ISymbolView] = None
        self.service_context: Optional[Any] = None 
        self._registry = registry

    def box(self, value: Any) -> Any:
        """
        [IES 2.0 SDK] 将 Python 原生对象转换为 IBCI 对象。
        职责下放的核心接口：插件负责产生数据，SDK 负责平权包装。
        """
        if self._registry:
            # [IES 2.0 Strict] 仅在 STAGE_4 (加载插件实现) 之后允许装箱
            self._registry.verify_level_at_least(4) # STAGE_4_PLUGIN_IMPL
            return self._registry.box(value)
        return value

    def register_type(self, py_class: type, descriptor: Any):
        """
        [IES 2.0 SDK] 注册自定义 Python 类与 UTS 描述符的映射。
        """
        if self._registry:
            # [IES 2.0 Strict] 仅允许在 STAGE_4 阶段注册新类型
            self._registry.verify_level(4) # STAGE_4_PLUGIN_IMPL
            
            token = self._registry.get_extension_token()
            self._registry.register_boxer(py_class, lambda r, v, m: r.create_instance("Object", v, descriptor=descriptor), token=token)

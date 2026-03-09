from typing import Any, Protocol, Optional, List, Dict, runtime_checkable

# --- Diagnostics ---

@runtime_checkable
class IssueTracker(Protocol):
    """诊断管理器接口"""
    def report(self, severity: Any, code: str, message: str, 
               location: Optional[Any] = None, hint: Optional[str] = None) -> None: ...
    def has_errors(self) -> bool: ...

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
    def set_global_intent(self, intent: str) -> None: ...
    def clear_global_intents(self) -> None: ...
    def remove_global_intent(self, intent: str) -> None: ...
    def get_global_intents(self) -> List[str]: ...

class ExtensionCapabilities:
    """扩展模块持有的能力集合容器"""
    def __init__(self):
        self.stack_inspector: Optional[IStackInspector] = None
        self.llm_provider: Optional[ILLMProvider] = None
        self.llm_executor: Optional[ILLMExecutor] = None
        self.intent_manager: Optional[IIntentManager] = None
        self.state_reader: Optional[IStateReader] = None
        self.symbol_view: Optional[ISymbolView] = None

from typing import Dict, Any, List, Optional, Protocol, runtime_checkable

@runtime_checkable
class IStateReader(Protocol):
    """提供对解释器运行时状态（如变量）的只读访问"""
    def get_vars_snapshot(self) -> Dict[str, Any]:
        """获取当前可见的所有变量快照"""
        ...

@runtime_checkable
class IStackInspector(Protocol):
    """提供对调用栈和意图栈的内省能力"""
    def get_call_stack_depth(self) -> int:
        ...
    def get_active_intents(self) -> List[str]:
        ...
    def get_instruction_count(self) -> int:
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
class IIntentManager(Protocol):
    """提供对意图（Global, Block）的管理能力"""
    def set_global_intent(self, intent: str) -> None: ...
    def clear_global_intents(self) -> None: ...
    def remove_global_intent(self, intent: str) -> None: ...
    def get_global_intents(self) -> List[str]: ...

class ExtensionCapabilities:
    """扩展模块持有的能力集合容器"""
    def __init__(self):
        self.state_reader: Optional[IStateReader] = None
        self.stack_inspector: Optional[IStackInspector] = None
        self.llm_provider: Optional[ILLMProvider] = None
        self.intent_manager: Optional[IIntentManager] = None

from typing import Any, Protocol, Optional, List, Dict, Union, Mapping, runtime_checkable

__all__ = [
    "ISourceProvider",
    "ICompilerService",
    "IssueTracker",
    "IStateReader",
    "ISymbolView",
    "ILLMProvider",
    "ILLMExecutor",
    "IILLMExecutor",
    "IIntentManager",
]

@runtime_checkable
class ISourceProvider(Protocol):
    """
    源码提供者接口。支持"无盘化"诊断，从内存缓冲区获取代码片段。
    """
    def get_line(self, file_path: str, lineno: int) -> Optional[str]: ...
    def get_full_source(self, file_path: str) -> Optional[str]: ...

@runtime_checkable
class ICompilerService(Protocol):
    """
    编译器服务接口。允许运行时动态编译代码或查询模块信息。
    """
    def compile_file(self, file_path: str) -> Any: ...
    def compile_to_artifact_dict(self, file_path: str) -> Dict[str, Any]: ...
    def resolve_module_path(self, module_name: str) -> Optional[str]: ...
    def get_module_source(self, module_name: str) -> Optional[str]: ...

@runtime_checkable
class IssueTracker(Protocol):
    """诊断管理器接口"""
    def report(self, severity: Any, code: str, message: str,
               location: Optional[Any] = None, hint: Optional[str] = None) -> None: ...
    def has_errors(self) -> bool: ...

@runtime_checkable
class IStateReader(Protocol):
    """提供对解释器运行时状态（如变量）的只读访问"""
    def get_vars_snapshot(self) -> Dict[str, Any]: ...

@runtime_checkable
class ISymbolView(Protocol):
    """只读符号视图接口"""
    def get(self, name: str) -> Any: ...
    def get_symbol(self, name: str) -> Optional[Any]: ...
    def has(self, name: str) -> bool: ...

@runtime_checkable
class ILLMProvider(Protocol):
    """LLM 服务提供者标准接口"""
    def __call__(self, sys_prompt: str, user_prompt: str, scene: str = "general") -> str: ...
    def get_last_call_info(self) -> Dict[str, Any]: ...
    def set_retry_hint(self, hint: str) -> None: ...
    def get_retry_prompt(self, node_type: str) -> Optional[str]: ...

@runtime_checkable
class ILLMExecutor(Protocol):
    """提供对内核 LLM 执行器的内省能力（向后兼容接口）"""
    def get_last_call_info(self) -> Dict[str, Any]: ...


@runtime_checkable
class IILLMExecutor(Protocol):
    """
    内核级 LLM 执行器完整接口。

    职责划分
    --------
    * ``invoke_behavior``             —— 行为对象公理化调用入口（供 IbBehavior.call() 使用）
    * ``execute_behavior_expression`` —— 行为描述行底层执行
    * ``execute_behavior_object``     —— 被动行为对象的底层执行
    * ``get_last_call_info``          —— 内省上次 LLM 调用的诊断信息

    设计原则：此接口驻留于 core.base，不依赖任何 runtime 具体类型；
    所有参数/返回类型均使用 Any，由实现层负责具体类型约束。
    """
    def invoke_behavior(self, behavior: Any, context: Any) -> Any:
        """
        执行一个行为对象，返回 IbObject 结果。

        该方法封装了全部执行细节（意图捕获、类型推导、结果缓存），
        是 IbBehavior.call() 的唯一对外接触点，严禁再使用 _execute_behavior。
        """
        ...

    def execute_behavior_expression(
        self,
        node_uid: str,
        context: Any,
        call_intent: Any = None,
        captured_intents: Any = None,
    ) -> Any:
        """执行行为描述行节点，返回 LLMResult。"""
        ...

    def execute_behavior_object(self, behavior: Any, context: Any) -> Any:
        """执行被动行为对象，返回 LLMResult。"""
        ...

    def get_last_call_info(self) -> Dict[str, Any]:
        """获取最后一次 LLM 调用的诊断信息。"""
        ...

@runtime_checkable
class IIntentManager(Protocol):
    """提供对意图（Global, Block）的管理能力"""
    def set_global_intent(self, intent: Union[str, Any]) -> None: ...
    def clear_global_intents(self) -> None: ...
    def remove_global_intent(self, intent: Union[str, Any]) -> None: ...
    def get_global_intents(self) -> List[Any]: ...
    def get_active_intents(self) -> List[Any]: ...
    def push_intent(self, intent: Union[str, Any], mode: str = "+", tag: Optional[str] = None) -> None: ...

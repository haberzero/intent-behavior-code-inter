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
    "IExecutionFrame",
    "IVMTask",
    "IVMExecutor",
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
    """
    提供对解释器运行时状态（变量、意图、LLM 结果）的只读访问。

    由 RuntimeContextImpl 实现，通过 KernelRegistry.get_state_reader() 供
    核心层插件（如 ibci_idbg）访问，无需持有 ServiceContext 引用。
    """
    def get_vars_snapshot(self) -> Dict[str, Any]: ...
    def get_vars(self) -> Dict[str, Any]: ...
    def get_active_intents(self) -> List[Any]: ...
    def get_last_llm_result(self) -> Optional[Any]: ...
    def get_llm_except_frames(self) -> List[Any]: ...

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

    def invoke_llm_function(self, func: Any, context: Any) -> Any:
        """
        执行一个命名 LLM 函数对象，返回 IbObject 结果。

        作用域管理和参数绑定已由 IbLLMFunction.call() 完成。
        此方法负责：调用 execute_llm_function、回写 last_llm_result（供 llmexcept 使用），
        并返回解析后的 IbObject，而非 LLMResult。
        是 IbLLMFunction.call() 的唯一执行分发点。
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


@runtime_checkable
class IExecutionFrame(Protocol):
    """
    IBCI 执行帧协议：单次函数调用的完整状态单元。
    等价于 CPU 上下文切换寄存器组；是并发、快照、切片的最小单位。

    RuntimeContextImpl 是其当前实现（无需修改现有代码，仅命名已有结构）。
    未来 IbIntentContext 公理化后，intent_context 属性将持有 IbIntentContext 对象。

    Protocol 方法约定：
    - current_scope  —— 当前作用域链（局部变量）
    - intent_stack   —— 意图栈顶节点（IntentNode 链表，或 IbIntentContext 对象）
    - get_llm_except_frames() —— LLM 异常帧栈（只读副本）
    - get_last_llm_result()   —— LLM 结果寄存器
    - fork_intent_snapshot()  —— 为 dispatch/retry 返回意图快照（Step 6 实现）
    """
    @property
    def current_scope(self) -> Any: ...

    @property
    def intent_stack(self) -> Any: ...

    def get_llm_except_frames(self) -> List[Any]: ...

    def get_last_llm_result(self) -> Optional[Any]: ...

    def fork_intent_snapshot(self) -> Any: ...


# ---------------------------------------------------------------------------
# VM 调度循环协议（M3a 骨架；M3b/M3c/M3d 将逐步扩展）
# ---------------------------------------------------------------------------

@runtime_checkable
class IVMTask(Protocol):
    """VM 调度单元协议（公理 VM-T1）。

    每个 VMTask 包装一个生成器协程，形态等价于 CPU 寄存器组：
    ``node_uid`` 标识当前帧对应的 AST 节点；``generator`` 是按 yield 协议表达的
    协程，节点之间通过 ``yield child_uid`` 让出控制权。

    M3a 阶段实现位于 ``core.runtime.vm.task.VMTask``；该协议仅声明对外可观测属性。
    """
    node_uid: str
    generator: Any


@runtime_checkable
class IVMExecutor(Protocol):
    """VM 调度循环协议（公理 VM-S1）。

    职责
    ----
    * 显式帧栈管理：以非 Python 递归的方式驱动 IBCI AST 求值
    * 控制流信号传播：在帧栈上传播 ``ControlSignal``（M3a 通过异常，M3b 数据化）
    * 与既有 ``Interpreter.visit()`` 并行：未实现节点回退到 ``fallback_visit``

    M3a 阶段实现位于 ``core.runtime.vm.vm_executor.VMExecutor``。
    M3d 阶段会把 ``Interpreter.visit()`` 主路径改为本协议驱动。
    """

    def supports(self, node_uid: str) -> bool:
        """判断节点是否有 CPS 处理器。"""
        ...

    def run(self, node_uid: str) -> Any:
        """执行 ``node_uid`` 子树并返回 IbObject 结果。"""
        ...

    def fallback_visit(self, node_uid: str) -> Any:
        """对未实现节点回退到原递归 visit() 路径。"""
        ...

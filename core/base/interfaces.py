from typing import Any, Protocol, Optional, List, Dict, Union, Mapping, runtime_checkable

__all__ = [
    "ISourceProvider",
    "ICompilerService",
    "IssueTracker",
    "IStateReader",
    "ISymbolView",
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
    def get_llm_except_frames(self) -> List[Any]: ...

@runtime_checkable
class ISymbolView(Protocol):
    """只读符号视图接口"""
    def get(self, name: str) -> Any: ...
    def get_symbol(self, name: str) -> Optional[Any]: ...
    def has(self, name: str) -> bool: ...

@runtime_checkable
class ILLMExecutor(Protocol):
    """提供对内核 LLM 执行器的内省能力。"""
    def get_current_call_info(self) -> Dict[str, Any]: ...


@runtime_checkable
class IILLMExecutor(Protocol):
    """
    内核级 LLM 执行器完整接口。

    职责划分
    --------
    * ``dispatch_eager``             —— 赋值上下文行为描述行并发派发（线程池 + LLMFuture）
    * ``resolve``                    —— 阻塞等待 Future 完成
    * ``run_batch``                  —— 并发批量执行行为对象
    * ``get_current_call_info``      —— 内省最近 resolve 的 LLM 调用诊断信息

    行为/LLM 函数的 CPS 执行入口（``execute_behavior_expression_cps`` /
    ``execute_llm_function_cps`` / ``invoke_*_cps``）为运行时内部协作路径，
    由 VM handler（``_vm_invoke_behavior`` / ``_vm_invoke_llm_function``）经
    ``yield from`` 驱动，不在此公开协议面。

    设计原则：此接口驻留于 core.base，不依赖任何 runtime 具体类型；
    所有参数/返回类型均使用 Any，由实现层负责具体类型约束。
    """
    def get_current_call_info(self) -> Dict[str, Any]:
        """获取最近一次 resolve 的 LLM 调用诊断信息。"""
        ...

    def resolve(self, node_uid: str) -> Any:
        """阻塞等待 ``node_uid`` 对应的 ``LLMFuture`` 完成，返回结果。"""
        ...

    def dispatch_eager(
        self,
        node_uid: str,
        execution_context: Any,
        intent_ctx: Any = None,
    ) -> Any:
        """立即将 LLM 调用提交到后台线程池，返回 ``LLMFuture``（非阻塞）。"""
        ...

    def hydrate(self, service_context: Any) -> None:
        """水化依赖（注入 ``ServiceContext`` 并初始化结果解析器）。"""
        ...

    def run_batch(self, behavior: Any, items: Any, execution_context: Any) -> Any:
        """并发批量执行行为对象，返回可帧内 CPS 驱动的 Waitable（保序结果列表）。"""
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
    - get_llm_except_frames() —— LLM 异常帧栈（只读副本）
    - fork_intent_snapshot()  —— 为 dispatch/retry 返回意图快照
    """
    @property
    def current_scope(self) -> Any: ...

    @property
    def intent_context(self) -> Any: ...

    def get_llm_except_frames(self) -> List[Any]: ...

    def fork_intent_snapshot(self) -> Any: ...

    def clear_inherited_intents(self) -> None: ...

    def use_intent_context(self, ctx: Any) -> None: ...

    def get_active_intent_ibobj(self) -> Any: ...

    def enter_intent_scope(self) -> tuple: ...

    def exit_intent_scope(self, saved: tuple) -> None: ...

    def replace_intent_context(self, new_ctx: Any) -> None: ...


# ---------------------------------------------------------------------------
# VM 调度循环协议（CPS 是主路径）
# ---------------------------------------------------------------------------

@runtime_checkable
class IVMTask(Protocol):
    """VM 调度单元协议。

    每个 VMTask 包装一个生成器协程，形态等价于 CPU 寄存器组：
    ``node_uid`` 标识当前帧对应的 AST 节点；``generator`` 是按 yield 协议表达的
    协程，节点之间通过 ``yield child_uid`` 让出控制权。
    """
    node_uid: str
    generator: Any


@runtime_checkable
class IVMExecutor(Protocol):
    """VM 调度循环协议（公理 VM-S1）。

    职责
    ----
    * 显式帧栈管理：以非 Python 递归的方式驱动 IBCI AST 求值
    * 控制流信号传播：在帧栈上通过 ``Signal(kind, value)`` 数据对象传播控制流
    * 43 种 AST 节点类型均有 CPS handler

    实现位于 ``core.runtime.vm.vm_executor.VMExecutor``。
    ``Interpreter.execute_module()`` 和 ``IbUserFunction.call()`` 均以本协议为主路径。
    """

    def supports(self, node_uid: str) -> bool:
        """判断节点是否有 CPS 处理器。"""
        ...

    def run(self, node_uid: str) -> Any:
        """执行 ``node_uid`` 子树并返回 IbObject 结果。"""
        ...

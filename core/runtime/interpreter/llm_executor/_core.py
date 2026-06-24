"""``LLMExecutorCore`` —— 共享状态与底层能力。

本模块是 ``llm_executor`` 包拆分后的"核心"切片，持有所有 mixin 共享的实例状态，
并提供被 function / behavior 两条执行路径共同调用的底层 LLM 调用入口
(:meth:`_call_llm`)。

共享状态协议 (``self.*`` 属性)
-------------------------------
下列属性由 :meth:`LLMExecutorCore.__init__` 初始化，并由各 mixin 读写。
任何 mixin 方法都可在假定这些属性已存在的前提下直接访问：

状态初始化 / 水化:
    - ``self._service_context``        —— ``ServiceContext``，水化前可能为 ``None``
    - ``self._execution_context``      —— ``IExecutionContext``
    - ``self._result_parser``          —— ``LLMResultParser``，水化后惰性创建

调用追踪:
    - ``self.last_call_info``          —— ``Mapping[str, Any]``，最后一次 LLM 调用信息

预期类型栈:
    - ``self._expected_type_stack``    —— ``List[str]``，由 :meth:`push_expected_type`
                                         / :meth:`pop_expected_type` 维护

LLMScheduler 状态 (由 ``_SchedulerMixin`` 使用):
    - ``self._max_workers``            —— ``int``，线程池大小
    - ``self._thread_pool``            —— ``Optional[ThreadPoolExecutor]``
    - ``self._pending_futures``        —— ``Dict[str, LLMFuture]``，node_uid → future
    - ``self._pending_futures_lock``   —— ``threading.Lock``，保护 ``_pending_futures``

派生属性 (property, 依赖 ``self._service_context``):
    - ``self.service_context`` / ``self.registry`` / ``self.interop``
    - ``self.issue_tracker`` / ``self.debugger`` / ``self.llm_callback``
"""

import threading
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from typing import Any, List, Optional, Dict, Union, Mapping

from core.runtime.interfaces import ServiceContext, Registry, InterOp, IExecutionContext
from core.base.interfaces import ILLMProvider, IssueTracker

from core.kernel.issue import InterpreterError
from core.runtime.shared.llm_result import LLMFuture
from core.base.diagnostics.codes import RUN_LLM_ERROR
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.exceptions import ThrownException

from core.runtime.interpreter.llm_parsing_strategy import LLMResultParser


class LLMExecutorCore:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
     采用上下文注入模式，支持延迟水化以消除解释器内部的属性补丁。

    新增 ``dispatch_eager`` / ``resolve`` 接口（LLMScheduler 能力），
    内部持有 ``ThreadPoolExecutor`` 以支持 behavior 表达式的并发 LLM 调用。
    """
    def __init__(self,
                 service_context: Optional[ServiceContext] = None,
                 execution_context: Optional[IExecutionContext] = None,
                 max_workers: int = 8):
        """
        service_context: 运行时服务聚合容器 (可能在构造期为 None)
        execution_context: 执行状态容器
        max_workers: LLMScheduler 线程池大小（默认 8；LLM 调用为 I/O bound，
                     GIL 在 HTTP 等待期间释放，高并发可提升吞吐）
        """
        self._service_context = service_context
        self._execution_context = execution_context

        self.last_call_info: Mapping[str, Any] = {} # 记录最后一次 LLM 调用信息
        self._expected_type_stack: List[str] = []

        # LLMScheduler 状态
        self._max_workers: int = max_workers
        self._thread_pool: Optional[_ThreadPoolExecutor] = None
        self._pending_futures: Dict[str, LLMFuture] = {}  # node_uid → LLMFuture
        self._pending_futures_lock = threading.Lock()  # 保护 _pending_futures 的并发访问

        # LLM Result Parser (lazy initialized after hydration)
        self._result_parser: Optional[LLMResultParser] = None

    def hydrate(self, service_context: ServiceContext):
        """ 水化依赖，由解释器在服务准备就绪后调用"""
        self._service_context = service_context
        # Initialize the result parser after hydration
        self._result_parser = LLMResultParser(self.registry, self.debugger)

    @property
    def service_context(self) -> ServiceContext:
        if not self._service_context:
            raise RuntimeError("LLMExecutorImpl: ServiceContext not hydrated.")
        return self._service_context

    @property
    def registry(self) -> Registry: return self.service_context.registry
    @property
    def interop(self) -> InterOp: return self.service_context.interop
    @property
    def issue_tracker(self) -> IssueTracker: return self.service_context.issue_tracker
    @property
    def debugger(self) -> Any: return self.service_context.debugger or core_debugger
    @property
    def llm_callback(self) -> Optional[ILLMProvider]:
        # 唯一来源：通过能力注册中心获取 Provider (能力名: llm_provider)
        # ibci_ai.setup() 在加载时调用 capabilities.expose("llm_provider", self) 完成注册。
        if self.service_context.capability_registry:
            provider = self.service_context.capability_registry.get("llm_provider")
            if provider:
                return provider
        return None

    def push_expected_type(self, type_name: str):
        self._expected_type_stack.append(type_name)

    def pop_expected_type(self):
        if self._expected_type_stack:
            self._expected_type_stack.pop()
    def get_last_call_info(self) -> Mapping[str, Any]:
        """获取最后一次 LLM 调用信息"""
        # 优先返回 executor 自身记录的信息（包含合并后的 Prompt）
        if self.last_call_info:
            return self.last_call_info

        # 否则尝试从 Provider (ai 模块) 获取
        if self.llm_callback and hasattr(self.llm_callback, 'get_last_call_info'):
            return self.llm_callback.get_last_call_info()

        return {}

    def _call_llm(self, sys_prompt: str, user_prompt: Union[str, List[Union[str, Dict[str, Any]]]], node_uid: str, execution_context: Optional[IExecutionContext] = None, target_model: str = "") -> str:
        """底层 LLM 调用。成功时返回 response 字符串。
        失败時（provider 层异常）直接 raise ThrownException(LLMCallError)，不返回 error 值。

        ``user_prompt``：
            - str: 纯文本用户提示词（向后兼容路径）
            - List[Union[str, dict]]: 含多模态结构化 content blocks（多模态路径）
              列表中 str 元素为纯文本片段，dict 元素为结构化 content block
              (e.g. {"type":"image_url","image_url":{"url":"data:..."}})

        ``target_model``：命名模型标识符，传递给 LLM provider 用于路由到特定模型配置。
        空字符串表示使用默认模型。
        """
        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "Calling LLM")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "System Prompt:", data=sys_prompt)
        if isinstance(user_prompt, str):
            self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt:", data=user_prompt)
        else:
            self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt (multimodal):", data=f"[{len(user_prompt)} content blocks]")
        if target_model:
            self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Target model: {target_model}")

        context = execution_context.runtime_context if execution_context else None
        retry_hint = context.retry_hint if context else None

        if self.llm_callback:
            try:
                if retry_hint:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting retry hint: {retry_hint}")
                    self.llm_callback.set_retry_hint(retry_hint)

                response = self.llm_callback(sys_prompt, user_prompt, target_model=target_model)
                self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "LLM Response received.")
                self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "LLM Raw Response:", data=response)
                return response
            except Exception as e:
                # LLM provider 层失败（网络错误、鉴权错误、配额耗尽等）→ LLMCallError。
                # 此类错误与 LLM 输出内容无关，llmexcept retry 对其无效，因此
                # 直接抛出 ThrownException，跳过 llmexcept 重试循环，
                # 让外层 try/except LLMCallError（或 LLMError/Exception）捕获。
                #
                # NOTE [未来演进 — VM 信号/中断机制]:
                # 当前方案依赖用户在外层书写 try/except LLMCallError。
                # 未来 IBCI VM 计划提供类操作系统的信号机制（见 PENDING_TASKS §十四），
                # 允许用户在语言层面注册基础设施错误处理回调，无需侵入业务逻辑代码。
                self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"LLM call failed (infra): {e}")
                error_obj = self.registry.make_llm_call_error(
                    message=str(e),
                    provider_error=str(e),
                )
                raise ThrownException(error_obj) from e

        # 如果没有回调，说明配置缺失，抛出错误
        raise InterpreterError(
            "LLM 运行配置缺失：未配置有效的 LLM 调用接口。\n"
            "请确保已导入 'ai' 模块并正确调用了 'ai.set_config'。",
            node_uid,
            error_code=RUN_LLM_ERROR
        )

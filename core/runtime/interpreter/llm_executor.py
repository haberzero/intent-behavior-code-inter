import re
import json
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any, List, Optional, Dict, Union, Callable, Mapping, Set, TYPE_CHECKING
from core.runtime.interfaces import LLMExecutor, RuntimeContext, ServiceContext, InterOp, Registry, IExecutionContext
from core.base.interfaces import ILLMProvider, IssueTracker

from core.kernel.issue import InterpreterError
from core.runtime.interpreter.llm_result import LLMResult, LLMFuture
from core.base.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.intent import IbIntent
from core.runtime.exceptions import ThrownException

from core.kernel.intent_logic import IntentMode, IntentRole
from core.kernel.intent_resolver import IntentResolver
from core.kernel.registry import KernelRegistry
from core.runtime.interpreter.llm_parsing_strategy import LLMResultParser

if TYPE_CHECKING:
    from core.runtime.objects.intent_context import IbIntentContext

class LLMExecutorImpl:
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

    def execute_llm_function(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None) -> LLMResult:
        """
        [职责解耦] 仅处理 LLM 推理过程。
        作用域管理和参数绑定已由 IbLLMFunction.call 完成。

        返回 LLMResult，不再抛出异常。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        name = node_data.get("name", "unknown")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{name}'")

        sys_prompt_segments = node_data.get("sys_prompt")
        user_prompt_segments = node_data.get("user_prompt")
        
        # 获取函数参数列表，用于在 prompt 中进行参数替换
        param_names = self._get_function_param_names(node_data, execution_context)

        sys_prompt = self._evaluate_segments(sys_prompt_segments, execution_context, param_names)
        user_prompt = self._evaluate_segments(user_prompt_segments, execution_context, param_names)
        
        # 2. 注入意图增强 (被动消费已消解的现场)
        # @! 排他意图已由 RuntimeContext 作为临时单次意图处理
        merged_intents = context.get_resolved_prompt_intents(execution_context)
        if merged_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
            sys_prompt += intent_block
            
        # 3. 处理 __llmretry__ 提示词注入
        # 优先级：运行时 context.retry_hint (来自 llmretry 语句) > 函数定义中的 retry_hint
        retry_hint_segments = None
        
        # 首先检查运行时上下文中的 retry_hint（来自 llmretry 语句）
        current_retry_hint = context.retry_hint
        if current_retry_hint:
            retry_hint_segments = [current_retry_hint]
        else:
            # 回退到函数定义中的 __llmretry__ 提示词
            retry_hint_segments = node_data.get("retry_hint")
        
        # 如果有 retry_hint，注入到系统提示词
        if retry_hint_segments:
            retry_hint_text = self._evaluate_segments(retry_hint_segments, execution_context, param_names)
            sys_prompt += f"\n\n[重试提示] 上一次执行失败，请参考以下提示进行重试：\n{retry_hint_text}"
            
        # 清除运行时上下文中的 retry_hint（防止污染后续调用）
        context.retry_hint = None
            
        # 4. 处理返回类型提示注入
        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data["_type"] == "IbName":
                type_name = returns_data.get("id", "str")

        # 从 LLM Provider 获取返回类型提示
        if self.llm_callback and hasattr(self.llm_callback, 'get_return_type_prompt'):
            type_prompt = self.llm_callback.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        # 5. 调用底层模型
        raw_res = self._call_llm(sys_prompt, user_prompt, node_uid, execution_context=execution_context)

        # 处理 MOCK:REPAIR 特殊标记
        if raw_res == "__MOCK_REPAIR__":
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        # 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if raw_res == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            return LLMResult.uncertain_result(
                raw_response="MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "response": raw_res,
            "raw_response": raw_res,
            "merged_intents": merged_intents
        }

        # 6. 解析结果
        return self._parse_result(raw_res, type_name, node_uid)

    def _get_function_param_names(self, node_data: Mapping[str, Any], execution_context: IExecutionContext) -> Set[str]:
        """
        获取 llm 函数的参数名列表。
         用于判断 prompt 中的 $auto 是否是函数参数。
        """
        param_names = set()
        args = node_data.get("args", [])
        for arg_uid in args:
            arg_data = execution_context.get_node_data(arg_uid)
            if not arg_data:
                continue
            
            # 处理直接的 IbArg 或 被 IbTypeAnnotatedExpr 包装的 IbArg
            actual_arg_data = arg_data
            if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                actual_arg_uid = arg_data.get("target")
                actual_arg_data = execution_context.get_node_data(actual_arg_uid)
            
            if actual_arg_data and actual_arg_data.get("_type") == "IbArg":
                param_names.add(actual_arg_data.get("arg", ""))
        return param_names

    def _evaluate_segments(self, segments: Optional[List[Any]], execution_context: IExecutionContext, param_names: Optional[Set[str]] = None) -> str:
        """同步版段求值（兼容入口）。

        实现委托给 ``_evaluate_segments_cps`` 生成器；当 ``vm_executor`` 可用时，
        通过 ``vm.run(uid)`` 对 yield 出的子节点求值。该路径用于：
        - ``dispatch_eager`` 在后台线程中的同步求值
        - 不经 VM 调度的旧测试路径

        CPS 主路径（由 VM handler 触发的 invoke_*）改用 ``_evaluate_segments_cps``
        + ``yield from``，使段求值作为子任务嵌入到外层 VM 帧栈，而非启动一个
        独立的 ``_drive_loop``，从而正确反映 ``frame_stack_depth``。
        """
        gen = self._evaluate_segments_cps(segments, execution_context, param_names)
        vm = execution_context.vm_executor if execution_context is not None else None
        sent = None
        try:
            while True:
                child = gen.send(sent) if sent is not None else next(gen)
                if child is None:
                    sent = None
                    continue
                if vm is None:
                    raise RuntimeError("LLMExecutor._evaluate_segments: vm_executor not available")
                sent = vm.run(child)
        except StopIteration as si:
            return si.value or ""

    def _evaluate_segments_cps(self, segments: Optional[List[Any]], execution_context: IExecutionContext, param_names: Optional[Set[str]] = None):
        """CPS 版段求值（生成器）。

        ``yield`` 出待求值的子节点 UID，调用方负责把求值结果通过 ``send`` 注回；
        最终用 ``return`` 返回拼接后的字符串。语义与 :meth:`_evaluate_segments`
        完全一致；唯一区别是把"调用 vm.run"替换为"yield 节点 UID"，让外层 VM
        调度循环把段求值作为子任务接管。

        设计目的：
        - 消除 `_evaluate_segments` 通过 ``vm.run`` 重入 ``_drive_loop`` 的"同步
          旁路"，使段求值真正纳入 CPS 帧栈。
        - 维持 lambda/snapshot/behavior 在段求值期间的栈可观察性与可暂停语义。
        """
        if not segments:
            return ""

        content_parts: List[str] = []
        for segment in segments:
            if isinstance(segment, Mapping) and segment.get("_type") == "ext_ref":
                val = execution_context.resolve_value(segment)
                content_parts.append(str(val))
                continue

            if isinstance(segment, str):
                if segment.startswith("node_"):
                    val = yield segment
                    if hasattr(val, '__to_prompt__'):
                        content_parts.append(val.__to_prompt__())
                    elif hasattr(val, 'to_native'):
                        content_parts.append(str(val.to_native()))
                    else:
                        content_parts.append(str(val))
                else:
                    content_parts.append(segment)
            elif hasattr(segment, 'id'):
                # IbName 节点（变量引用）
                var_name = segment.id

                # 只有当变量名是函数参数时才进行替换
                if param_names and var_name in param_names:
                    val = yield segment
                    if hasattr(val, '__to_prompt__'):
                        content_parts.append(val.__to_prompt__())
                    elif hasattr(val, 'to_native'):
                        content_parts.append(str(val.to_native()))
                    else:
                        content_parts.append(str(val))
                else:
                    # 非函数参数的 $auto，作为普通文本处理（保持 $ 符号）
                    content_parts.append(f"${var_name}")
            else:
                content_parts.append(str(segment))
        return "".join(content_parts)

    def _get_llmoutput_hint(self, node_uid: str, node_data: Mapping[str, Any], execution_context: IExecutionContext) -> Optional[str]:
        """获取 __outputhint_prompt__ 用于注入到提示词

        查找顺序：
        1. Axiom 内置类型：通过 meta_reg.get_llm_output_hint_cap(descriptor)
        2. 用户自定义 IBCI 类：通过类 vtable 查找 __outputhint_prompt__ 方法
        """
        def _try_axiom_hint(type_name: str) -> Optional[str]:
            meta_reg = self.registry.get_metadata_registry()
            if meta_reg:
                descriptor = meta_reg.resolve(type_name)
                if descriptor:
                    hint_cap = meta_reg.get_llm_output_hint_cap(descriptor)
                    if hint_cap:
                        return hint_cap.__outputhint_prompt__(descriptor)
            return None

        def _try_vtable_hint(type_name: str) -> Optional[str]:
            """回退：通过用户类 vtable 查找 __outputhint_prompt__（类方法语义）"""
            ib_class = self.registry.get_class(type_name)
            if ib_class:
                method = ib_class.lookup_method('__outputhint_prompt__')
                if method:
                    try:
                        result = method.call(ib_class, [])
                        hint = result.to_native() if hasattr(result, 'to_native') else str(result)
                        return str(hint) if hint is not None else None
                    except Exception as e:
                        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC,
                            f"vtable __outputhint_prompt__ failed for '{type_name}': {e}")
            return None

        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data.get("_type") == "IbName":
                type_name = returns_data.get("id", "str")
                hint = _try_axiom_hint(type_name)
                if hint is not None:
                    return hint
                hint = _try_vtable_hint(type_name)
                if hint is not None:
                    return hint

        node_to_type = execution_context.get_side_table("node_to_type", node_uid)
        if node_to_type:
            type_name = getattr(node_to_type, 'name', None)
            if type_name:
                hint = _try_axiom_hint(type_name)
                if hint is not None:
                    return hint
                hint = _try_vtable_hint(type_name)
                if hint is not None:
                    return hint

        return None

    def _get_expected_type_hint(self, node_uid: str, node_data: Mapping[str, Any], execution_context: IExecutionContext) -> Optional[str]:
        """获取预期的类型名称，用于 __from_prompt__ 解析"""
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data.get("_type") == "IbName":
                return returns_data.get("id", "str")
        
        node_to_type = execution_context.get_side_table("node_to_type", node_uid)
        if node_to_type:
            if hasattr(node_to_type, 'name'):
                return node_to_type.name
        
        return None

    def _parse_result(self, raw_res: str, type_name: str, node_uid: str, execution_context: Optional[IExecutionContext] = None) -> LLMResult:
        """
        Parse LLM result using the chain of responsibility pattern.

        This method delegates to LLMResultParser which applies parsing strategies
        in order: Axiom → VTable → Default.

        Args:
            raw_res: Raw LLM response string
            type_name: Expected type name
            node_uid: Node unique identifier
            execution_context: Optional execution context

        Returns:
            LLMResult with parsed value or uncertainty
        """
        if not self._result_parser:
            # Fallback if parser not initialized (shouldn't happen after hydration)
            self._result_parser = LLMResultParser(self.registry, self.debugger)

        return self._result_parser.parse_result(raw_res, type_name, node_uid, execution_context)

    # ---------------------------------------------------------------------------
    # LLMScheduler — dispatch_eager / resolve / 线程池管理
    # ---------------------------------------------------------------------------

    def _get_thread_pool(self) -> _ThreadPoolExecutor:
        """惰性初始化线程池（首次 dispatch_eager 调用时创建）。"""
        if self._thread_pool is None:
            self._thread_pool = _ThreadPoolExecutor(max_workers=self._max_workers)
        return self._thread_pool

    def dispatch_eager(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        intent_ctx: Optional[Any] = None,
    ) -> LLMFuture:
        """立即将 LLM 调用提交到线程池，返回 ``LLMFuture``（非阻塞）。

        在 ``dispatch_eligible=True`` 且数据依赖已满足时，由 VM 调度器调用。
        在 dispatch 时刻捕获 prompt 内容与意图上下文，后台线程中发起实际调用。

        参数：
            node_uid:          对应 ``IbBehaviorExpr`` 节点的 UID
            execution_context: 当前执行上下文（用于 prompt 求值；调用时刻只读）
            intent_ctx:        （可选）已 fork 的意图上下文快照；None 表示使用
                               当前 runtime_context 的活跃意图

        返回：
            ``LLMFuture``，可通过 ``resolve(node_uid)`` 阻塞等待结果。
        """
        def _run() -> LLMResult:
            return self.execute_behavior_expression(
                node_uid, execution_context, captured_intents=intent_ctx
            )

        future = self._get_thread_pool().submit(_run)
        llm_future = LLMFuture(node_uid=node_uid, future=future)
        self._pending_futures[node_uid] = llm_future
        return llm_future

    def resolve(self, node_uid: str) -> IbObject:
        """阻塞等待 ``node_uid`` 对应的 ``LLMFuture`` 完成，返回 ``IbObject``。

        在变量使用点检测到对应 ``LLMFuture`` 时由 VM 调度器调用。

        若 ``dispatch_eager`` 尚未被调用，或对应 Future 已被 resolve 消费，
        则抛出 ``RuntimeError``。
        """
        llm_future = self._pending_futures.pop(node_uid, None)
        if llm_future is None:
            raise RuntimeError(
                f"LLMExecutorImpl.resolve: 节点 {node_uid!r} 没有待解析的 Future。"
                f"请确认 dispatch_eager() 已在 resolve() 之前被调用，"
                f"且每个 Future 只被 resolve 一次。"
            )
        return llm_future.get(self.registry)

    def close(self) -> None:
        """关闭线程池（等待已提交任务完成）。

        应优先调用此方法显式释放资源，而非依赖 ``__del__``。
        关闭后不应再调用 ``dispatch_eager()``（会重新创建线程池）。
        """
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None

    def __del__(self) -> None:
        """关闭线程池（非阻塞；允许已提交的任务完成）。"""
        if self._thread_pool is not None:
            try:
                self._thread_pool.shutdown(wait=False)
            except Exception:
                pass

    def execute_behavior_expression(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None, captured_intents: Optional['IbIntentContext'] = None) -> LLMResult:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。

        返回 LLMResult：
        - success=True, is_uncertain=False: 成功且结果确定
        - success=True, is_uncertain=True: 成功但结果不确定，需要 retry
        - success=False: 执行失败

        不再抛出 LLMUncertaintyError，所有不确定性通过 LLMResult 返回。

        ``captured_intents`` 协议：
            - ``None``  → 使用当前 RuntimeContext 的活跃意图栈（lambda 模式）
            - ``IbIntentContext`` 实例 → 已 fork 的意图值快照（snapshot 模式 / dispatch_eager）

        其他类型一律视为契约违反并 raise TypeError。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        # 1. 评估段式插值
        content = self._evaluate_segments(node_data.get("segments"), execution_context)

        # 2. 收集与合并意图 (被动消费已消解的现场)
        # auto_intent_injection 配置从已注册的 LLM Provider 读取（通过能力注册中心）
        provider = self.llm_callback
        auto_intent = True
        if provider and hasattr(provider, "_config"):
            auto_intent = provider._config.get("auto_intent_injection", True)

        if not auto_intent:
            # 如果关闭了自动注入，仅保留当前节点的意图 (如果有)
            if call_intent:
                content_str = call_intent.resolve_content(context, execution_context)
                return LLMResult.success_result(
                    value=self.registry.box(content_str),
                    raw_response=content_str
                )

        # 获取消解后的最终列表
        # 如果提供了捕获的意图栈，则优先使用捕获的，否则使用当前上下文的
        if captured_intents is not None:
            from core.runtime.objects.intent_context import IbIntentContext as _IbIntentContext
            if not isinstance(captured_intents, _IbIntentContext):
                # 所有生产者只产出 None 或 IbIntentContext。
                # 历史的 IntentNode 链表 / 已展平 list 路径已无产生方；命中即为契约违反。
                raise TypeError(
                    f"execute_behavior_expression: captured_intents must be "
                    f"None or IbIntentContext, got {type(captured_intents).__name__}"
                )
            # snapshot 捕获了 IbIntentContext.fork() 的完整值快照
            active_list = captured_intents.get_active_intents()
            all_intents = IntentResolver.resolve(
                active_intents=active_list,
                global_intents=captured_intents.get_global_intents(),
                context=context,
                execution_context=execution_context
            )
        else:
            all_intents = context.get_resolved_prompt_intents(execution_context)

        # 获取 __outputhint_prompt__ 注入到系统提示词
        llmoutput_hint = self._get_llmoutput_hint(node_uid, node_data, execution_context)

        sys_prompt = "你是一个意图行为代码执行器。"

        # 注入 __outputhint_prompt__
        if llmoutput_hint:
            sys_prompt += f"\n\n[输出格式要求]\n{llmoutput_hint}"

        # 读取 retry_hint 后立即清除，防止污染后续 LLM 调用（无论本次执行走哪条路径）
        current_retry_hint = context.retry_hint
        context.retry_hint = None
        if provider and not current_retry_hint and hasattr(provider, "_retry_hint"):
            current_retry_hint = provider._retry_hint

        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        # 4. 构造意图增强块
        if all_intents:
            intent_block = "\n当前上下文意图：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        # 5. 调用底层模型
        response = self._call_llm(sys_prompt, content, node_uid)

        # 6.1 处理 MOCK:REPAIR 特殊标记
        if response == "__MOCK_REPAIR__":
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        # 6.2 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if response == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            return LLMResult.uncertain_result(
                raw_response="MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": content,
            "response": response,
            "raw_response": response,
            "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in active_list] if 'active_list' in dir() else [],
            "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
            "merged_intents": all_intents
        }

        # 7. 处理返回类型
        # 使用 __from_prompt__ 机制进行解析
        type_hint = self._get_expected_type_hint(node_uid, node_data, execution_context)
        if type_hint:
            return self._parse_result(response, type_hint, node_uid)

        return LLMResult.success_result(
            value=self.registry.box(response),
            raw_response=response
        )


    def execute_behavior_object(self, behavior: IbObject, execution_context: IExecutionContext) -> LLMResult:
        """
        执行一个被动行为对象。
        环境（意图栈）已由 Interpreter/Handler 在调用前准备就绪。

        返回 LLMResult。

        缓存策略：``_cache`` 仅对 **immediate** 行为对象（``capture_mode is None``）有意义——
        那是值语义的「求值一次后复用」对象。对 lambda / snapshot 模式而言，每次调用
        都必须是独立的 LLM 推理（这是 lambda 「读现场」与 snapshot 「无状态可重入」
        语义的共同要求），因此跳过缓存读写。
        """
        if not (isinstance(behavior, IbValue) and behavior.ib_class.name == "behavior"):
             return LLMResult.success_result(value=behavior)

        cache_enabled = getattr(behavior, "capture_mode", None) is None
        if cache_enabled and behavior._cache is not None:
            return LLMResult.success_result(value=behavior._cache)

        # 1. 处理预期类型注入
        type_pushed = False
        if behavior.expected_type:
            self.push_expected_type(behavior.expected_type)
            type_pushed = True

        try:
            # 2. 递归调用 execute_behavior_expression (环境已由 Caller 准备)
            # 传入行为对象捕获的意图栈
            result = self.execute_behavior_expression(behavior.node, execution_context, captured_intents=behavior.captured_intents)
            if cache_enabled:
                behavior._cache = result.value if result else None
            return result
        finally:
            # 3. 环境恢复 (类型栈)
            if type_pushed:
                self.pop_expected_type()

    def invoke_behavior(self, behavior: IbObject, execution_context: IExecutionContext) -> IbObject:
        """
        公理化行为调用入口 —— 供 IbBehavior.call() 使用。

        封装了完整执行流程：
        1. 委托给 execute_behavior_object 完成 LLM 调用及类型解析；
        2. 将 LLMResult 回写到 RuntimeContext（供 llmexcept 检查）；
        3. 直接返回 IbObject，调用方无需了解 LLMResult 内部结构。
        """
        result = self.execute_behavior_object(behavior, execution_context)
        if execution_context is not None:
            execution_context.runtime_context.set_last_llm_result(result)
        # 使用 is not None 判断，避免将 IbBool(False)/IbInteger(0) 等假值误判为空
        if result is not None and result.value is not None:
            return result.value
        return self.registry.get_none()

    def invoke_llm_function(self, func: IbObject, execution_context: IExecutionContext) -> IbObject:
        """
        公理化命名 LLM 函数调用入口 —— 供 IbLLMFunction.call() 使用。

        作用域管理和参数绑定已由 IbLLMFunction.call() 完成，此方法负责：
        1. 从 func 对象提取 call_intent（函数头意图）；
        2. 委托给 execute_llm_function 完成 LLM 推理并返回 LLMResult；
        3. 将 LLMResult 回写到 RuntimeContext（供 llmexcept 检查）；
        4. 直接返回 IbObject（result.value），调用方无需了解 LLMResult 内部结构。
        """
        # call_intent 由 IbLLMFunction 在调用前已解析并暂存到 _pending_call_intent
        call_intent = getattr(func, '_pending_call_intent', None)
        result = self.execute_llm_function(func.node_uid, execution_context, call_intent=call_intent)
        if execution_context is not None:
            execution_context.runtime_context.set_last_llm_result(result)
        # 使用 is not None 判断，避免将 IbBool(False)/IbInteger(0) 等假值误判为空
        if result is not None and result.value is not None:
            return result.value
        return self.registry.get_none()

    # ------------------------------------------------------------------ #
    # CPS-friendly generator variants                                    #
    # ------------------------------------------------------------------ #
    #
    # 这些 ``*_cps`` 生成器把段求值阶段（``_evaluate_segments_cps``）通过
    # ``yield from`` 嵌入 VM 调度循环。语义与同步版本完全一致，唯一区别是
    # prompt 段中的子节点（``node_*`` 或 IbName）通过 yield 交给外层 VM 帧栈
    # 求值，而不是再启动一次 ``_drive_loop``。
    #
    # 调用约定：调用方需要 ``yield from`` 这些方法，最终值通过 ``return``
    # 携带（``StopIteration.value``）。LLM HTTP 请求本身仍是同步的——这是
    # 当前架构下的下一步演进点（详见 ``_call_llm`` 内部注释）。
    # ------------------------------------------------------------------ #

    def execute_llm_function_cps(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None):
        """CPS 版 :meth:`execute_llm_function`；逻辑等价，段求值通过 yield from。"""
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        name = node_data.get("name", "unknown")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{name}'")

        sys_prompt_segments = node_data.get("sys_prompt")
        user_prompt_segments = node_data.get("user_prompt")

        param_names = self._get_function_param_names(node_data, execution_context)

        sys_prompt = yield from self._evaluate_segments_cps(sys_prompt_segments, execution_context, param_names)
        user_prompt = yield from self._evaluate_segments_cps(user_prompt_segments, execution_context, param_names)

        merged_intents = context.get_resolved_prompt_intents(execution_context)
        if merged_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
            sys_prompt += intent_block

        retry_hint_segments = None
        current_retry_hint = context.retry_hint
        if current_retry_hint:
            retry_hint_segments = [current_retry_hint]
        else:
            retry_hint_segments = node_data.get("retry_hint")

        if retry_hint_segments:
            retry_hint_text = yield from self._evaluate_segments_cps(retry_hint_segments, execution_context, param_names)
            sys_prompt += f"\n\n[重试提示] 上一次执行失败，请参考以下提示进行重试：\n{retry_hint_text}"

        context.retry_hint = None

        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data["_type"] == "IbName":
                type_name = returns_data.get("id", "str")

        if self.llm_callback and hasattr(self.llm_callback, 'get_return_type_prompt'):
            type_prompt = self.llm_callback.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        raw_res = self._call_llm(sys_prompt, user_prompt, node_uid, execution_context=execution_context)

        if raw_res == "__MOCK_REPAIR__":
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        if raw_res == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            return LLMResult.uncertain_result(
                raw_response="MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "response": raw_res,
            "raw_response": raw_res,
            "merged_intents": merged_intents
        }
        return self._parse_result(raw_res, type_name, node_uid)

    def execute_behavior_expression_cps(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None, captured_intents: Optional['IbIntentContext'] = None):
        """CPS 版 :meth:`execute_behavior_expression`；段求值通过 yield from。"""
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        content = yield from self._evaluate_segments_cps(node_data.get("segments"), execution_context)

        provider = self.llm_callback
        auto_intent = True
        if provider and hasattr(provider, "_config"):
            auto_intent = provider._config.get("auto_intent_injection", True)

        if not auto_intent:
            if call_intent:
                content_str = call_intent.resolve_content(context, execution_context)
                return LLMResult.success_result(
                    value=self.registry.box(content_str),
                    raw_response=content_str
                )

        if captured_intents is not None:
            from core.runtime.objects.intent_context import IbIntentContext as _IbIntentContext
            if not isinstance(captured_intents, _IbIntentContext):
                raise TypeError(
                    f"execute_behavior_expression_cps: captured_intents must be "
                    f"None or IbIntentContext, got {type(captured_intents).__name__}"
                )
            active_list = captured_intents.get_active_intents()
            all_intents = IntentResolver.resolve(
                active_intents=active_list,
                global_intents=captured_intents.get_global_intents(),
                context=context,
                execution_context=execution_context
            )
        else:
            all_intents = context.get_resolved_prompt_intents(execution_context)

        llmoutput_hint = self._get_llmoutput_hint(node_uid, node_data, execution_context)

        sys_prompt = "你是一个意图行为代码执行器。"

        if llmoutput_hint:
            sys_prompt += f"\n\n[输出格式要求]\n{llmoutput_hint}"

        current_retry_hint = context.retry_hint
        context.retry_hint = None
        if provider and not current_retry_hint and hasattr(provider, "_retry_hint"):
            current_retry_hint = provider._retry_hint

        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        if all_intents:
            intent_block = "\n当前上下文意图：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        response = self._call_llm(sys_prompt, content, node_uid)

        if response == "__MOCK_REPAIR__":
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        if response == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            return LLMResult.uncertain_result(
                raw_response="MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": content,
            "response": response,
            "raw_response": response,
            "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
            "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
            "merged_intents": all_intents
        }

        type_hint = self._get_expected_type_hint(node_uid, node_data, execution_context)
        if type_hint:
            return self._parse_result(response, type_hint, node_uid)

        return LLMResult.success_result(
            value=self.registry.box(response),
            raw_response=response
        )

    def execute_behavior_object_cps(self, behavior: IbObject, execution_context: IExecutionContext):
        """CPS 版 :meth:`execute_behavior_object`；委托给 execute_behavior_expression_cps。"""
        if not (isinstance(behavior, IbValue) and behavior.ib_class.name == "behavior"):
            return LLMResult.success_result(value=behavior)

        cache_enabled = getattr(behavior, "capture_mode", None) is None
        if cache_enabled and behavior._cache is not None:
            return LLMResult.success_result(value=behavior._cache)

        type_pushed = False
        if behavior.expected_type:
            self.push_expected_type(behavior.expected_type)
            type_pushed = True

        try:
            result = yield from self.execute_behavior_expression_cps(
                behavior.node, execution_context, captured_intents=behavior.captured_intents
            )
            if cache_enabled:
                behavior._cache = result.value if result else None
            return result
        finally:
            if type_pushed:
                self.pop_expected_type()

    def invoke_behavior_cps(self, behavior: IbObject, execution_context: IExecutionContext):
        """CPS 版 :meth:`invoke_behavior`；段求值嵌入外层 VM 帧栈。"""
        result = yield from self.execute_behavior_object_cps(behavior, execution_context)
        if execution_context is not None:
            execution_context.runtime_context.set_last_llm_result(result)
        if result is not None and result.value is not None:
            return result.value
        return self.registry.get_none()

    def invoke_llm_function_cps(self, func: IbObject, execution_context: IExecutionContext):
        """CPS 版 :meth:`invoke_llm_function`；段求值嵌入外层 VM 帧栈。"""
        call_intent = getattr(func, '_pending_call_intent', None)
        result = yield from self.execute_llm_function_cps(
            func.node_uid, execution_context, call_intent=call_intent
        )
        if execution_context is not None:
            execution_context.runtime_context.set_last_llm_result(result)
        if result is not None and result.value is not None:
            return result.value
        return self.registry.get_none()

    def _call_llm(self, sys_prompt: str, user_prompt: str, node_uid: str, execution_context: Optional[IExecutionContext] = None) -> str:
        """底层 LLM 调用。成功时返回 response 字符串。
        失败時（provider 层异常）直接 raise ThrownException(LLMCallError)，不返回 error 值。
        """
        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "Calling LLM")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "System Prompt:", data=sys_prompt)
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt:", data=user_prompt)

        context = execution_context.runtime_context if execution_context else None
        retry_hint = context.retry_hint if context else None

        if self.llm_callback:
            try:
                if retry_hint:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting retry hint: {retry_hint}")
                    self.llm_callback.set_retry_hint(retry_hint)

                response = self.llm_callback(sys_prompt, user_prompt)
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


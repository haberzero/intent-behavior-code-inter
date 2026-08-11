"""``_BehaviorMixin`` —— behavior 表达式 / 对象执行。

包含 behavior (即时、匿名 LLM 调用) 的 CPS 执行入口（``execute_behavior_expression_cps``
/ ``execute_behavior_object_cps`` / ``invoke_behavior_cps``），以及供
``dispatch_eager``（后台线程）与 ``run_batch``（ai.run_batch）使用的同步预求值
``_prepare_behavior_call``。

依赖 :class:`LLMExecutorCore` 的 ``_call_llm`` / ``llm_callback`` /
``_current_call_info`` 等共享状态，
以及 :class:`_PromptMixin` 的 ``_evaluate_segments`` /
``_evaluate_segments_cps`` / ``_get_llmoutput_hint`` /
``_get_expected_type_hint`` / ``_parse_result``。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Mapping

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import (
    LLMResult,
    LLMFuture,
    LLMBatchFuture,
    MOCK_REPAIR_SENTINEL,
    MOCK_AMBIGUOUS_SENTINEL,
)

from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.intent import IbIntent
from core.runtime.objects.intent_context import IbIntentContext
from core.runtime.objects.primitives.callables import (
    bind_behavior_closure,
    bind_behavior_call_args,
)
from core.runtime.exceptions import ThrownException

from core.kernel.intent_resolver import IntentResolver


@dataclass
class BehaviorCallSpec:
    """行为调用预求值结果（主线程完成，worker 仅执行 LLM 调用 + 解析）。

    拆分的边界：主线程预求值 prompt 段（``_evaluate_segments`` / 意图消解 /
    output hint / retry_hint），把与执行线程无关的输入快照进本对象；
    worker 线程只读本对象执行 ``_call_llm`` + 解析，不访问 live context。

    ``pre_resolved``：auto_intent 关闭且携带 ``call_intent`` 时的短路结果
    （不经 LLM 调用），由调用方直接返回。
    """

    sys_prompt: str
    user_prompt: Union[str, List[Union[str, Dict[str, Any]]]]
    type_hint: Optional[str]
    target_model: str
    active_intents: List[Any] = field(default_factory=list)
    global_intents: List[Any] = field(default_factory=list)
    merged_intents: List[Any] = field(default_factory=list)
    pre_resolved: Optional[LLMResult] = None


class _RunBatchDrive:
    """``ai.run_batch`` 的帧内 CPS 驱动 Waitable。

    由 :meth:`_BehaviorMixin.run_batch` 返回；VM ``vm_handle_IbCall`` 识别其为
    ``Waitable`` + ``CPSDrivable`` 后 ``yield from`` ``cps_drive``，使每项 prompt
    预求值（``_prepare_behavior_call_cps``）嵌入当前 VM 帧栈（消除 ``vm.run``
    重入），并把多 LLM Future 聚合为 :class:`LLMBatchFuture` ``yield`` 让出
    调度线程（消除主线程 ``fut.result()`` 硬阻塞）——与 ``stream_call`` 返回
    Waitable 的范式一致。

    ``try_result``/``result`` 走同步 :meth:`_BehaviorMixin._run_batch_sync` 兜底
    （宿主/线程体直接调用、无活跃 VM 时），与 ``_SlotUpdateWaitable`` 的
    ``_drive`` 同步兜底同构；VM 主路径以 ``cps_drive`` 为权威。
    """

    def __init__(self, executor, behavior: IbObject, items: List[IbObject], ec):
        self._executor = executor
        self._behavior = behavior
        self._items = items
        self._ec = ec
        self._done = False
        self._results = None

    @property
    def is_done(self) -> bool:
        return self._done

    def _drive(self):
        """宿主/线程体同步驱动（无 VM CPS 上下文时；非权威路径）。"""
        self._results = self._executor._run_batch_sync(
            self._behavior, self._items, self._ec
        )
        self._done = True
        return self._results

    def cps_drive(self, executor):
        """帧内 CPS 驱动（并入当前调度器；VM 权威路径）。

        每项预求值经 ``_prepare_behavior_call_cps`` 嵌入当前 VM 帧栈（由外层
        ``_drive_loop_gen`` 统一驱动，不新建调度器），聚合 LLM Future 由调度器
        非阻塞等待，完成后返回 boxed IbList。
        """
        self._results = yield from self._executor._run_batch_cps(
            self._behavior, self._items, executor.ec
        )
        self._done = True
        return self._results

    def try_result(self):
        if self._done:
            return (True, self._results)
        self._drive()
        return (True, self._results)

    def result(self):
        self._drive()
        return self._results

    def register_wake(self, event) -> None:
        event.set()


class _BehaviorMixin:
    def _prepare_behavior_call(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        call_intent: Optional[IbIntent] = None,
        captured_intents: Optional[IbIntentContext] = None,
        target_model: str = "",
    ) -> BehaviorCallSpec:
        """主线程预求值行为调用的全部输入（prompt 段 + 意图 + 输出约束）。

        在 dispatch 时刻同步调用；``_evaluate_segments`` 经 ``vm.run`` 重入
        主线程调度循环（同线程嵌套 drive_loop 安全）。worker 线程随后仅读
        返回的 :class:`BehaviorCallSpec`，不再访问 live context。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        if not target_model:
            target_model = node_data.get("tag", "")

        content = self._evaluate_segments(node_data.get("segments"), execution_context)

        provider = self.llm_callback
        auto_intent = True
        if provider:
            auto_intent = provider.is_auto_intent_injection_enabled()

        if not auto_intent:
            if call_intent:
                content_str = call_intent.resolve_content(context, execution_context)
                return BehaviorCallSpec(
                    sys_prompt="",
                    user_prompt=content_str,
                    type_hint=None,
                    target_model=target_model,
                    pre_resolved=LLMResult.success_result(
                        value=self.registry.box(content_str),
                        raw_response=content_str,
                    ),
                )

        active_list: List[Any] = []
        global_intents: List[Any] = []
        if captured_intents is not None:
            if not isinstance(captured_intents, IbIntentContext):
                raise TypeError(
                    f"_prepare_behavior_call: captured_intents must be "
                    f"None or IbIntentContext, got {type(captured_intents).__name__}"
                )
            active_list = captured_intents.get_active_intents()
            global_intents = captured_intents.get_global_intents()
            all_intents = IntentResolver.resolve(
                active_intents=active_list,
                global_intents=global_intents,
                context=context,
                execution_context=execution_context,
            )
        else:
            all_intents = context.get_resolved_prompt_intents(execution_context)
            global_intents = context.get_global_intents()

        llmoutput_hint = self._get_llmoutput_hint(node_uid, node_data, execution_context)

        sys_prompt = "你是一个意图行为代码执行器。"

        if llmoutput_hint:
            sys_prompt += f"\n\n[输出格式要求]\n{llmoutput_hint}"

        frame = context.get_current_llm_except_frame()
        current_retry_hint = frame.retry_hint if frame else None

        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        if all_intents:
            intent_block = "\n当前上下文意图（必须严格遵守）：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        type_hint = self._get_expected_type_hint(node_uid, node_data, execution_context)

        return BehaviorCallSpec(
            sys_prompt=sys_prompt,
            user_prompt=content,
            type_hint=type_hint,
            target_model=target_model,
            active_intents=[i.content if hasattr(i, "content") else str(i) for i in active_list],
            global_intents=[i.content if hasattr(i, "content") else str(i) for i in global_intents],
            merged_intents=all_intents,
        )

    def _prepare_behavior_call_cps(
        self,
        node_uid: str,
        node_data: Mapping[str, Any],
        execution_context: IExecutionContext,
        call_intent: Optional[IbIntent] = None,
        captured_intents: Optional[IbIntentContext] = None,
        target_model: str = "",
    ):
        """CPS 版 :meth:`_prepare_behavior_call`（M4：段求值经 yield from，非阻塞）。

        与同步版同语义（prompt 段预求值 + 意图消解 + 输出约束 + retry_hint），
        但段求值经 ``_evaluate_segments_cps``（yield）、hint 经
        ``_get_llmoutput_hint_cps``（yield）——调用方须 ``yield from``。
        返回 :class:`BehaviorCallSpec`，供 ``_call_and_parse`` 在 worker 线程
        执行（本方法不调用 LLM，不阻塞调度线程）。
        """
        if not target_model:
            target_model = node_data.get("tag", "")

        content = yield from self._evaluate_segments_cps(node_data.get("segments"), execution_context)

        provider = self.llm_callback
        auto_intent = True
        if provider:
            auto_intent = provider.is_auto_intent_injection_enabled()

        if not auto_intent:
            if call_intent:
                content_str = call_intent.resolve_content(
                    execution_context.runtime_context, execution_context
                )
                return BehaviorCallSpec(
                    sys_prompt="",
                    user_prompt=content_str,
                    type_hint=None,
                    target_model=target_model,
                    pre_resolved=LLMResult.success_result(
                        value=self.registry.box(content_str),
                        raw_response=content_str,
                    ),
                )

        context = execution_context.runtime_context
        active_list: List[Any] = []
        global_intents: List[Any] = []
        if captured_intents is not None:
            if not isinstance(captured_intents, IbIntentContext):
                raise TypeError(
                    f"_prepare_behavior_call_cps: captured_intents must be "
                    f"None or IbIntentContext, got {type(captured_intents).__name__}"
                )
            active_list = captured_intents.get_active_intents()
            global_intents = captured_intents.get_global_intents()
            all_intents = yield from IntentResolver.resolve_cps(
                active_intents=active_list,
                global_intents=global_intents,
                context=context,
                execution_context=execution_context,
            )
        else:
            all_intents = yield from context.get_resolved_prompt_intents_cps(execution_context)
            global_intents = context.get_global_intents()

        llmoutput_hint = yield from self._get_llmoutput_hint_cps(node_uid, node_data, execution_context)

        sys_prompt = "你是一个意图行为代码执行器。"

        if llmoutput_hint:
            sys_prompt += f"\n\n[输出格式要求]\n{llmoutput_hint}"

        frame = context.get_current_llm_except_frame()
        current_retry_hint = frame.retry_hint if frame else None

        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        if all_intents:
            intent_block = "\n当前上下文意图（必须严格遵守）：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        type_hint = self._get_expected_type_hint(node_uid, node_data, execution_context)

        return BehaviorCallSpec(
            sys_prompt=sys_prompt,
            user_prompt=content,
            type_hint=type_hint,
            target_model=target_model,
            active_intents=[i.content if hasattr(i, "content") else str(i) for i in active_list],
            global_intents=[i.content if hasattr(i, "content") else str(i) for i in global_intents],
            merged_intents=all_intents,
        )

    def _call_and_parse(
        self, spec: BehaviorCallSpec, node_uid: str, execution_context: IExecutionContext
    ) -> LLMResult:
        """执行 LLM 调用并解析结果（worker 线程可安全调用）。

        只读 :class:`BehaviorCallSpec`，不写主线程单写槽（``_current_call_info``
        由调用方在 sync 尾部或 resolve 点记录）；不访问 live context。
        """
        if spec.pre_resolved is not None:
            return spec.pre_resolved

        response = self._call_llm(spec.sys_prompt, spec.user_prompt, node_uid, target_model=spec.target_model)

        def _call_info(resp: str) -> dict:
            return {
                "sys_prompt": spec.sys_prompt,
                "user_prompt": spec.user_prompt,
                "response": resp,
                "raw_response": resp,
                "active_intents": list(spec.active_intents),
                "global_intents": list(spec.global_intents),
                "merged_intents": list(spec.merged_intents),
            }

        if response == MOCK_REPAIR_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_REPAIR_SENTINEL,
                    retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试",
                ),
                _call_info(MOCK_REPAIR_SENTINEL),
                record_current=False,
            )

        if response == MOCK_AMBIGUOUS_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_AMBIGUOUS_SENTINEL,
                    retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理",
                ),
                _call_info(MOCK_AMBIGUOUS_SENTINEL),
                record_current=False,
            )

        if spec.type_hint:
            result = self._parse_result(response, spec.type_hint, node_uid)
        else:
            result = LLMResult.success_result(
                value=self.registry.box(response),
                raw_response=response,
            )
        return self._finalize_call(result, _call_info(response), record_current=False)

    def execute_behavior_expression_cps(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None, captured_intents: Optional['IbIntentContext'] = None, target_model: str = ""):
        """CPS 版 :meth:`execute_behavior_expression`；段求值通过 yield from。

        **LLM 真挂起**：spec 经 ``_prepare_behavior_call_cps``
        （段求值 yield）构建，随后 ``_call_and_parse`` 提交线程池并 ``yield``
        返回的 ``LLMFuture``——调度器挂起本根、让出给其它根，LLM 就绪后
        ``send`` 回 ``LLMResult`` 恢复。消除了同步 ``_call_llm`` 阻塞调度线程
        （"可挂起但未挂起"），使 ``run_many`` LLM 并发达 CPS 直连路径。
        """
        node_data = execution_context.get_node_data(node_uid)
        spec = yield from self._prepare_behavior_call_cps(
            node_uid, node_data, execution_context, call_intent, captured_intents, target_model
        )
        if spec.pre_resolved is not None:
            return spec.pre_resolved

        future = self._get_thread_pool().submit(
            self._call_and_parse, spec, node_uid, execution_context
        )
        llm_future = LLMFuture(node_uid=node_uid, future=future)
        result = yield llm_future
        if result is not None and result.call_info is not None:
            self._record_current_call_info(result.call_info)
        return result

    def execute_behavior_object_cps(self, behavior: IbObject, execution_context: IExecutionContext):
        """CPS 版 :meth:`execute_behavior_object`；委托给 execute_behavior_expression_cps。"""
        if not (isinstance(behavior, IbValue) and behavior.ib_class.name == "behavior"):
            return LLMResult.success_result(value=behavior)

        cache_enabled = behavior.capture_mode is None
        if cache_enabled and behavior._cache is not None:
            return LLMResult.success_result(value=behavior._cache)

        result = yield from self.execute_behavior_expression_cps(
            behavior.node, execution_context, captured_intents=behavior.captured_intents
        )
        if cache_enabled:
            behavior._cache = result.value if result else None
        return result

    def invoke_behavior_cps(self, behavior: IbObject, execution_context: IExecutionContext):
        """CPS 版 :meth:`invoke_behavior`；段求值嵌入外层 VM 帧栈。"""
        result = yield from self.execute_behavior_object_cps(behavior, execution_context)
        return self._finalize_invoke_result(result)

    def run_batch(
        self,
        behavior: IbObject,
        items: List[IbObject],
        execution_context: IExecutionContext,
    ):
        """并发批量执行行为对象，返回可帧内 CPS 驱动的 Waitable。

        ``items`` 逐项作为行为参数在子作用域中绑定（``bind_behavior_closure``
        + ``bind_behavior_call_args``）。返回 :class:`_RunBatchDrive`：
        VM 主路径经 ``cps_drive`` 帧内 CPS 驱动——每项 prompt 预求值用
        ``_prepare_behavior_call_cps``（段求值/意图消解/hint 嵌入当前 VM 帧栈，
        消除 ``vm.run`` 同步重入），并把多 LLM Future 聚合为
        :class:`LLMBatchFuture` 由调度器非阻塞等待（消除主线程 ``fut.result()``
        硬阻塞），与 ``stream_call`` 的 Waitable 范式一致。宿主/线程体直接调用
        走 ``try_result``/``result`` 的同步 ``_drive``（旧路径）。
        """
        if not (isinstance(behavior, IbValue) and behavior.ib_class.name == "behavior"):
            raise TypeError(
                f"run_batch: expected a behavior, got {type(behavior).__name__}"
            )
        return _RunBatchDrive(self, behavior, list(items), execution_context)

    def _run_batch_sync(
        self,
        behavior: IbObject,
        items: List[IbObject],
        execution_context: IExecutionContext,
    ) -> List[IbObject]:
        """同步版批量执行（宿主/线程体 ``_RunBatchDrive._drive`` 兜底）。

        用同步 ``_prepare_behavior_call``（``vm.run`` 段求值重入）预求值 + 提交
        Future + ``fut.result()`` 阻塞取回。与 ``_SlotUpdateWaitable._drive``
        同构——仅非 VM 上下文（无活跃 VM 可 CPS 驱动）时触发；VM 主路径走
        :meth:`_run_batch_cps` 为权威路径。
        """
        ec = execution_context
        rt = ec.runtime_context

        specs: List[BehaviorCallSpec] = []
        for item in items:
            rt.enter_scope()
            try:
                bind_behavior_closure(behavior, rt)
                bind_behavior_call_args(behavior, [item], ec, rt)
                spec = self._prepare_behavior_call(
                    behavior.node, ec, captured_intents=behavior.captured_intents
                )
                specs.append(spec)
            finally:
                rt.exit_scope()

        pool = self._get_thread_pool()
        futures = [
            pool.submit(self._call_and_parse, spec, behavior.node, ec)
            for spec in specs
        ]
        llm_results = [fut.result() for fut in futures]
        return self._aggregate_batch_results(ec, llm_results)

    def _run_batch_cps(
        self,
        behavior: IbObject,
        items: List[IbObject],
        execution_context: IExecutionContext,
    ):
        """CPS 版批量执行（VM 权威路径，生成器）。

        与 :meth:`_run_batch_sync` 同语义，但：预求值用 ``_prepare_behavior_call_cps``
        （段求值/意图消解/hint ``yield from`` 嵌入当前 VM 帧栈，消除 ``vm.run``
        重入）；多 LLM Future 聚合为 :class:`LLMBatchFuture` ``yield`` 由调度器
        非阻塞等待（让出调度线程）。调用方（``_RunBatchDrive.cps_drive``）须
        ``yield from``。
        """
        ec = execution_context
        rt = ec.runtime_context

        specs: List[BehaviorCallSpec] = []
        for item in items:
            rt.enter_scope()
            try:
                bind_behavior_closure(behavior, rt)
                bind_behavior_call_args(behavior, [item], ec, rt)
                spec = yield from self._prepare_behavior_call_cps(
                    behavior.node,
                    ec.get_node_data(behavior.node),
                    ec,
                    captured_intents=behavior.captured_intents,
                )
                specs.append(spec)
            finally:
                rt.exit_scope()

        pool = self._get_thread_pool()
        futures = [
            LLMFuture(
                node_uid=behavior.node,
                future=pool.submit(self._call_and_parse, spec, behavior.node, ec),
            )
            for spec in specs
        ]
        results = yield LLMBatchFuture(futures)
        return self.registry.box(self._aggregate_batch_results(ec, results))

    def _aggregate_batch_results(
        self, ec: IExecutionContext, llm_results: List[Any]
    ) -> List[IbObject]:
        """聚合 LLM 结果列表为语言值列表：任一项不确定即抛 LLMParseError。

        ``llm_results`` 为保序的 :class:`LLMResult` 列表（同步路径经
        ``fut.result()`` 取回、CPS 路径经 :class:`LLMBatchFuture` 取回）；
        调用方决定是否装箱（CPS 主路径 ``registry.box`` 为语言层 IbList）。
        """
        results: List[IbObject] = []
        for llm_result in llm_results:
            if llm_result is not None and llm_result.is_uncertain:
                error = self.registry.make_llm_parse_error(
                    llm_result.retry_hint or "LLM output could not be parsed",
                    raw_response=llm_result.raw_response or "",
                    type_name="unknown",
                )
                raise ThrownException(error)
            results.append(self._finalize_invoke_result(llm_result))
        return results

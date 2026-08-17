"""``_BehaviorMixin`` —— behavior 表达式 / 对象执行。

包含 behavior (即时、匿名 LLM 调用) 的 CPS 执行入口（``execute_behavior_expression_cps``
/ ``execute_behavior_object_cps`` / ``invoke_behavior_cps``），以及供
``dispatch_eager``（主线程预求值）与 ``run_batch``（ai.run_batch）使用的同步
薄包装 :meth:`_prepare_behavior_call`——经 :meth:`_pump_cps` 驱动 CPS 权威版本，
sync/CPS 无双写。

依赖 :class:`LLMExecutorCore` 的 ``_call_llm`` / ``llm_callback`` /
``_current_call_info`` 等共享状态，
以及 :class:`_PromptMixin` 的 ``_evaluate_segments_cps`` /
``_get_llmoutput_hint_cps`` /
``_get_expected_type_hint`` / ``_parse_result``。
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Mapping

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import (
    LLMResult,
    LLMFuture,
    LLMBatchFuture,
    MOCK_REPAIR_SENTINEL,
    MOCK_AMBIGUOUS_SENTINEL,
)

from core.runtime.interpreter.llm_executor._prompt_assembly import (
    build_retry_message_history_from_attempts,
)

from core.base.llm_protocol import (
    LLMCallRequest,
    OutputContract,
    IntentBlock,
)
from core.base.llm_protocol.llm_call import ContentValue

from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.intent_context import IbIntentContext
from core.runtime.objects.primitives.callables import (
    bind_behavior_closure,
    bind_behavior_call_args,
)
from core.runtime.exceptions import ThrownException


@dataclass
class BehaviorCallSpec:
    """行为调用预求值结果（主线程完成，worker 仅执行 LLM 调用 + 解析）。

    拆分的边界：主线程预求值 behavior 语义（段 ``_evaluate_segments_cps`` /
    意图消解 / output hint / retry_hint），装配为一次结构化
    :class:`LLMCallRequest`；worker 线程只读本对象执行 ``_call_llm`` + 解析，
    不访问 live context。
    """

    request: LLMCallRequest
    type_hint: Optional[str]


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
        """宿主/线程体同步驱动（无 VM CPS 上下文时；非权威路径）。

        与 :meth:`cps_drive` 同返回形态（boxed IbList），保证同一 Waitable
        对象经任一驱动路径产出语言层一致的 boxed 结果。
        """
        self._results = self._executor.registry.box(
            self._executor._run_batch_sync(self._behavior, self._items, self._ec)
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
    def _build_behavior_call_request(
        self,
        *,
        node_uid: str,
        user_prompt: ContentValue,
        llmoutput_hint: Optional[str],
        type_hint: Optional[str],
        active_intents: List[Any],
        global_intents: List[Any],
        merged_intents: List[Any],
        target_model: str,
        message_history: Optional[List[Dict[str, Any]]],
        suppress_type_constraint: bool,
    ) -> LLMCallRequest:
        """把 behavior 语义装配为一次结构化 :class:`LLMCallRequest`（sync/CPS 共用）。

        内核只收集**结构化物**（意图栈原始三层 / 输出契约原始值 / user 内容），
        **不**拼装系统提示词字符串——提示词形态由 provider（推荐模板）决定，
        可自定义 provider 改写"面对某左值/类型的默认行为"。

        ``suppress_type_constraint``：存在排他意图（``@!``）时，用户已显式指定
        输出形态，不注入类型级输出格式/期望类型约束，避免与用户指令冲突。
        """
        return LLMCallRequest(
            node_uid=node_uid,
            user_prompt=user_prompt,
            intents=IntentBlock(
                active=[str(x) for x in active_intents],
                global_=[str(x) for x in global_intents],
                merged=[str(x) for x in merged_intents],
            ),
            output_contract=OutputContract(
                expected_type=None if suppress_type_constraint else type_hint,
                output_hint=None if suppress_type_constraint else llmoutput_hint,
                suppress_type_constraint=suppress_type_constraint,
            ),
            target_model=target_model,
            message_history=message_history,
        )

    def _build_retry_message_history(self, frame: Optional[Any]) -> Optional[List[Dict[str, Any]]]:
        """从 llmexcept 帧构造标准多轮对话的重试消息历史。

        只在存在重试帧且已记录失败尝试时返回非空；初调（无帧）返回 None。
        """
        if frame is None:
            return None
        return build_retry_message_history_from_attempts(
            getattr(frame, "attempt_history", None)
        )

    def _prepare_behavior_call(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        captured_intents: Optional[IbIntentContext] = None,
        target_model: str = "",
    ) -> BehaviorCallSpec:
        """主线程预求值行为调用的全部输入（prompt 段 + 意图 + 输出约束）。

        同步薄包装：经 :meth:`_pump_cps` 驱动 CPS 权威版本
        :meth:`_prepare_behavior_call_cps`（段求值/意图消解/hint 唯一实现），
        yield 出的子节点经 ``vm.run`` 重入主线程调度循环（同线程嵌套
        drive_loop 安全）。供 ``dispatch_eager``（主线程预求值）与
        ``_run_batch_sync``（宿主/线程体兜底）使用；VM 主路径直接
        ``yield from`` CPS 版本。
        """
        node_data = execution_context.get_node_data(node_uid)
        return self._pump_cps(
            self._prepare_behavior_call_cps(
                node_uid, node_data, execution_context, captured_intents, target_model
            ),
            execution_context,
        )

    def _prepare_behavior_call_cps(
        self,
        node_uid: str,
        node_data: Mapping[str, Any],
        execution_context: IExecutionContext,
        captured_intents: Optional[IbIntentContext] = None,
        target_model: str = "",
    ):
        """CPS 版 :meth:`_prepare_behavior_call`（M4：段求值经 yield from，非阻塞）。

        本方法是预求值逻辑的唯一权威实现（prompt 段预求值 + 意图消解 +
        输出约束 + retry_hint）；同步薄包装经 :meth:`_pump_cps` 驱动本方法。
        段求值经 ``_evaluate_segments_cps``（yield）、hint 经
        ``_get_llmoutput_hint_cps``（yield）——调用方须 ``yield from``。
        返回 :class:`BehaviorCallSpec`，供 ``_call_and_parse`` 在 worker 线程
        执行（本方法不调用 LLM，不阻塞调度线程）。
        """
        if not target_model:
            target_model = node_data.get("tag", "")

        content = yield from self._evaluate_segments_cps(node_data.get("segments"), execution_context)

        context = execution_context.runtime_context
        # 原始意图各层 content（未拼串）；merged 为进入本次调用的合并消解提示列表
        active_contents: List[str] = []
        global_contents: List[str] = []
        all_intents: List[str] = []
        has_override = False
        if captured_intents is not None:
            if not isinstance(captured_intents, IbIntentContext):
                raise TypeError(
                    f"_prepare_behavior_call_cps: captured_intents must be "
                    f"None or IbIntentContext, got {type(captured_intents).__name__}"
                )
            active_list = captured_intents.get_active_intents()
            global_intents = captured_intents.get_global_intents()
            has_override = captured_intents.has_override()
            all_intents = yield from captured_intents.resolve_to_prompts_cps(context, execution_context)
        else:
            has_override = context.intent_context.has_override()
            all_intents = yield from context.get_resolved_prompt_intents_cps(execution_context)
            global_intents = context.get_global_intents()
            active_list = context.get_active_intents()
        active_contents = [i.content if hasattr(i, "content") else str(i) for i in active_list]
        global_contents = [i.content if hasattr(i, "content") else str(i) for i in global_intents]
        merged_contents = [str(i) for i in all_intents]

        llmoutput_hint = yield from self._get_llmoutput_hint_cps(node_uid, node_data, execution_context)
        type_hint = self._get_expected_type_hint(node_uid, node_data, execution_context)
        frame = context.get_current_llm_except_frame()
        message_history = self._build_retry_message_history(frame)

        request = self._build_behavior_call_request(
            node_uid=node_uid,
            user_prompt=content,
            llmoutput_hint=llmoutput_hint,
            type_hint=type_hint,
            active_intents=active_contents,
            global_intents=global_contents,
            merged_intents=merged_contents,
            target_model=target_model,
            message_history=message_history,
            suppress_type_constraint=has_override,
        )

        return BehaviorCallSpec(
            request=request,
            type_hint=type_hint,
        )

    def _call_and_parse(
        self, spec: BehaviorCallSpec, node_uid: str, execution_context: IExecutionContext
    ) -> LLMResult:
        """执行 LLM 调用并解析结果（worker 线程可安全调用）。

        只读 :class:`BehaviorCallSpec`，不写主线程单写槽（``_current_call_info``
        由调用方在 sync 尾部或 resolve 点记录）；不访问 live context。
        """
        req = spec.request
        call_result = self._call_llm(req)
        response = call_result.content

        def _call_info(resp: str) -> dict:
            d = req.as_dict()
            # provider 回填其实际组装/发送的信息（如最终 sys_prompt）
            d.update(call_result.provider_meta or {})
            d["response"] = resp
            d["raw_response"] = call_result.raw_response if call_result.raw_response else resp
            return d

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

    def execute_behavior_expression_cps(self, node_uid: str, execution_context: IExecutionContext, captured_intents: Optional['IbIntentContext'] = None, target_model: str = ""):
        """行为表达式 CPS 执行入口；段求值通过 yield from。

        **LLM 真挂起**：spec 经 ``_prepare_behavior_call_cps``
        （段求值 yield）构建，随后 ``_call_and_parse`` 提交线程池并 ``yield``
        返回的 ``LLMFuture``——调度器挂起本根、让出给其它根，LLM 就绪后
        ``send`` 回 ``LLMResult`` 恢复。消除了同步 ``_call_llm`` 阻塞调度线程
        （"可挂起但未挂起"），使 ``run_many`` LLM 并发达 CPS 直连路径。
        """
        node_data = execution_context.get_node_data(node_uid)
        spec = yield from self._prepare_behavior_call_cps(
            node_uid, node_data, execution_context, captured_intents, target_model
        )

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
                # 每条调用独立 fork 意图快照：语句级 @!/@ 意图对批内
                # 每个 LLM 调用都可见，而不是被第一条调用消费后丢失。
                captured_intents = behavior.captured_intents
                if captured_intents is None:
                    captured_intents = rt.fork_intent_snapshot()
                spec = self._prepare_behavior_call(
                    behavior.node, ec, captured_intents=captured_intents
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
                # 每条调用独立 fork 意图快照：语句级 @!/@ 意图对批内
                # 每个 LLM 调用都可见，而不是被第一条调用消费后丢失。
                captured_intents = behavior.captured_intents
                if captured_intents is None:
                    captured_intents = rt.fork_intent_snapshot()
                spec = yield from self._prepare_behavior_call_cps(
                    behavior.node,
                    ec.get_node_data(behavior.node),
                    ec,
                    captured_intents=captured_intents,
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
        # 记录最近一次 LLM 调用信息（与单调用路径对齐）：批内最后一次结果
        # 携带完整 call_info（worker 经 _finalize_call record_current=False 绑定，
        # 这里统一记录到主线程单写槽）。首项（批量语义上代表本次调用）优先。
        for llm_result in results:
            if llm_result is not None and getattr(llm_result, "call_info", None) is not None:
                self._record_current_call_info(llm_result.call_info)
                break
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

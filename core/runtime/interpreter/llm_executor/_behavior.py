"""``_BehaviorMixin`` —— behavior 表达式 / 对象执行。

包含 behavior (即时、匿名 LLM 调用) 的同步执行入口及其 CPS 生成器孪生，
同步与 CPS 版本成对放置于同一文件。

依赖 :class:`LLMExecutorCore` 的 ``_call_llm`` / ``llm_callback`` /
``_current_call_info`` 等共享状态，
以及 :class:`_PromptMixin` 的 ``_evaluate_segments`` /
``_evaluate_segments_cps`` / ``_get_llmoutput_hint`` /
``_get_expected_type_hint`` / ``_parse_result``。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult, MOCK_REPAIR_SENTINEL, MOCK_AMBIGUOUS_SENTINEL

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
            intent_block = "\n当前上下文意图：\n" + "\n".join(f"- {i}" for i in all_intents)
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

    def execute_behavior_expression(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        call_intent: Optional[IbIntent] = None,
        captured_intents: Optional[IbIntentContext] = None,
        target_model: str = "",
    ) -> LLMResult:
        """处理行为描述行（即时、匿名的 LLM 调用）。

        返回 LLMResult：
        - success=True, is_uncertain=False: 成功且结果确定
        - success=True, is_uncertain=True: 成功但结果不确定，需要 retry
        - success=False: 执行失败

        不再抛出 LLMUncertaintyError，所有不确定性通过 LLMResult 返回。

        ``captured_intents`` 协议：
            - ``None``  → 使用当前 RuntimeContext 的活跃意图栈（lambda 模式）
            - ``IbIntentContext`` 实例 → 已 fork 的意图值快照（snapshot 模式 / dispatch_eager）

        其他类型一律视为契约违反并 raise TypeError。

        ``target_model``：
            - ``""``（空字符串）→ 使用默认模型配置（无 tag 的 @~ ... ~ 语法）
            - 非空字符串 → 路由到命名模型配置（@NAME~ ... ~ 语法中的 NAME）

        本方法为主线程同步入口：``_prepare_behavior_call``（prompt 预求值）
        + ``_call_and_parse``（LLM 调用 + 解析）顺序执行，结果绑定 call_info，
        并在尾部记录主线程单写槽。
        """
        spec = self._prepare_behavior_call(
            node_uid, execution_context, call_intent, captured_intents, target_model
        )
        result = self._call_and_parse(spec, node_uid, execution_context)
        if result is not None and result.call_info is not None:
            self._record_current_call_info(result.call_info)
        return result


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

        cache_enabled = behavior.capture_mode is None
        if cache_enabled and behavior._cache is not None:
            return LLMResult.success_result(value=behavior._cache)

        result = self.execute_behavior_expression(behavior.node, execution_context, captured_intents=behavior.captured_intents)
        if cache_enabled:
            behavior._cache = result.value if result else None
        return result

    def invoke_behavior(self, behavior: IbObject, execution_context: IExecutionContext) -> IbObject:
        """
        公理化行为调用入口 —— 供 IbBehavior.call() 使用。

        封装了完整执行流程：
        1. 委托给 execute_behavior_object 完成 LLM 调用及类型解析；
        2. 直接返回 IbObject；不确定性结果经 ``_finalize_invoke_result``
           转译为 ``IbLLMCallResult(is_certain=False)`` 供语句层消费者处理。
        """
        result = self.execute_behavior_object(behavior, execution_context)
        return self._finalize_invoke_result(result)

    def execute_behavior_expression_cps(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None, captured_intents: Optional['IbIntentContext'] = None, target_model: str = ""):
        """CPS 版 :meth:`execute_behavior_expression`；段求值通过 yield from。"""
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        # 如果未显式传递 target_model，从 node_data 中读取 tag 字段
        if not target_model:
            target_model = node_data.get("tag", "")

        content = yield from self._evaluate_segments_cps(node_data.get("segments"), execution_context)

        provider = self.llm_callback
        auto_intent = True
        if provider:
            auto_intent = provider.is_auto_intent_injection_enabled()

        if not auto_intent:
            if call_intent:
                content_str = call_intent.resolve_content(context, execution_context)
                return LLMResult.success_result(
                    value=self.registry.box(content_str),
                    raw_response=content_str
                )

        if captured_intents is not None:
            if not isinstance(captured_intents, IbIntentContext):
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

        frame = context.get_current_llm_except_frame()
        current_retry_hint = frame.retry_hint if frame else None

        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        if all_intents:
            intent_block = "\n当前上下文意图：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        response = self._call_llm(sys_prompt, content, node_uid, target_model=target_model)

        def _call_info(resp: str) -> dict:
            return {
                "sys_prompt": sys_prompt,
                "user_prompt": content,
                "response": resp,
                "raw_response": resp,
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": all_intents
            }

        if response == MOCK_REPAIR_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_REPAIR_SENTINEL,
                    retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
                ),
                _call_info(MOCK_REPAIR_SENTINEL),
            )

        if response == MOCK_AMBIGUOUS_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_AMBIGUOUS_SENTINEL,
                    retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
                ),
                _call_info(MOCK_AMBIGUOUS_SENTINEL),
            )

        type_hint = self._get_expected_type_hint(node_uid, node_data, execution_context)
        if type_hint:
            result = self._parse_result(response, type_hint, node_uid)
        else:
            result = LLMResult.success_result(
                value=self.registry.box(response),
                raw_response=response
            )
        return self._finalize_call(result, _call_info(response))

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
    ) -> List[IbObject]:
        """并发批量执行行为对象：逐项绑定参数，并行调用，保序返回。

        ``items`` 逐项作为行为参数在子作用域中绑定（``bind_behavior_closure``
        + ``bind_behavior_call_args``），每项在主线程预求值 prompt
        （``_prepare_behavior_call``），后台并发执行 ``_call_and_parse``
        （不重入 VM、不写主线程单写槽）。返回结果列表（按 ``items`` 顺序）。

        任一项结果不确定（parse 失败）即抛 ``LLMParseError``——与无
        llmexcept 的同步语义一致，错误粒度为整个批次。
        """
        if not (isinstance(behavior, IbValue) and behavior.ib_class.name == "behavior"):
            raise TypeError(
                f"run_batch: expected a behavior, got {type(behavior).__name__}"
            )

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
        results: List[IbObject] = []
        for fut in futures:
            llm_result = fut.result()
            if llm_result is not None and llm_result.is_uncertain:
                error = self.registry.make_llm_parse_error(
                    llm_result.retry_hint or "LLM output could not be parsed",
                    raw_response=llm_result.raw_response or "",
                    type_name="unknown",
                )
                raise ThrownException(error)
            results.append(self._finalize_invoke_result(llm_result))
        return results

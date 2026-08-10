"""``_LLMFunctionMixin`` —— 命名 LLM 函数执行。

包含命名 LLM 函数的同步执行入口 (:meth:`execute_llm_function` /
:meth:`invoke_llm_function`) 及其 CPS 生成器孪生 (:meth:`execute_llm_function_cps`
/ :meth:`invoke_llm_function_cps`)。同步与 CPS 版本成对放置。

依赖 :class:`LLMExecutorCore` 的 ``_call_llm`` / ``llm_callback`` / ``_current_call_info``
等共享状态，以及 :class:`_PromptMixin` 的 ``_get_function_param_names`` /
``_evaluate_segments`` / ``_evaluate_segments_cps`` / ``_parse_result``。
"""

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult, LLMFuture, MOCK_REPAIR_SENTINEL, MOCK_AMBIGUOUS_SENTINEL

from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent import IbIntent


@dataclass
class LLMFunctionCallSpec:
    """LLM 函数调用预求值结果（主线程完成，worker 仅执行 LLM 调用 + 解析）。

    拆分的边界（与 :class:`BehaviorCallSpec` 同构）：主线程经 CPS 段求值
    预构建 ``sys_prompt`` / ``user_prompt`` 并快照 intent 列表；worker 线程
    只读本对象执行 ``_call_llm`` + ``_parse_result``，不访问 live context、
    不重入 VM、不写主线程单写槽。
    """

    sys_prompt: str
    user_prompt: str
    type_name: str
    node_uid: str
    active_intents: List[Any] = field(default_factory=list)
    global_intents: List[Any] = field(default_factory=list)
    merged_intents: List[Any] = field(default_factory=list)


class _LLMFunctionMixin:
    def execute_llm_function(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None) -> LLMResult:
        """
        [职责解耦] 仅处理 LLM 推理过程。
        作用域管理和参数绑定已由 IbLLMFunction.call 完成。

        返回 LLMResult，不再抛出异常。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        name = node_data.get("name", "unknown")

        sys_prompt_segments = node_data.get("sys_prompt")
        user_prompt_segments = node_data.get("user_prompt")

        # 获取函数参数列表，用于在 prompt 中进行参数替换
        param_names = self._get_function_param_names(node_data, execution_context)

        sys_prompt = self._evaluate_segments(sys_prompt_segments, execution_context, param_names)
        if not isinstance(sys_prompt, str):
            raise TypeError("__sys__ prompt segments must produce text-only content")
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

        # retry_hint 绑定到当前 llmexcept 帧（持续覆盖），回退到函数定义 __llmretry__
        frame = context.get_current_llm_except_frame()
        current_retry_hint = frame.retry_hint if frame else None
        if current_retry_hint:
            retry_hint_segments = [current_retry_hint]
        else:
            retry_hint_segments = node_data.get("retry_hint")

        # 如果有 retry_hint，注入到系统提示词
        if retry_hint_segments:
            retry_hint_text = self._evaluate_segments(retry_hint_segments, execution_context, param_names)
            if not isinstance(retry_hint_text, str):
                raise TypeError("retry hint segments must produce text-only content")
            sys_prompt += f"\n\n[重试提示] 上一次执行失败，请参考以下提示进行重试：\n{retry_hint_text}"

        # 4. 处理返回类型提示注入
        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data["_type"] == "IbName":
                type_name = returns_data.get("id", "str")

        # 从 LLM Provider 获取返回类型提示（协议声明能力，直接调用）
        if self.llm_callback:
            type_prompt = self.llm_callback.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        # 5. 调用底层模型
        raw_res = self._call_llm(sys_prompt, user_prompt, node_uid, execution_context=execution_context)

        def _call_info(resp: str) -> dict:
            return {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": resp,
                "raw_response": resp,
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": merged_intents
            }

        # 处理 MOCK:REPAIR 特殊标记
        if raw_res == MOCK_REPAIR_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_REPAIR_SENTINEL,
                    retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
                ),
                _call_info(MOCK_REPAIR_SENTINEL),
            )

        # 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if raw_res == MOCK_AMBIGUOUS_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_AMBIGUOUS_SENTINEL,
                    retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
                ),
                _call_info(MOCK_AMBIGUOUS_SENTINEL),
            )

        # 6. 解析结果并绑定调用信息
        return self._finalize_call(
            self._parse_result(raw_res, type_name, node_uid),
            _call_info(raw_res),
        )

    def invoke_llm_function(self, func: IbObject, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None) -> IbObject:
        """
        公理化命名 LLM 函数调用入口 —— 供 IbLLMFunction.call() 使用。

        作用域管理和参数绑定已由 IbLLMFunction.call() 完成，此方法负责：
        1. 委托给 execute_llm_function 完成 LLM 推理并返回 LLMResult；
        2. 直接返回 IbObject；不确定性结果经 ``_finalize_invoke_result``
           转译为 ``IbLLMCallResult(is_certain=False)`` 供语句层消费者处理。

        ``call_intent`` 为调用前已解析的函数头意图，显式传参。
        """
        result = self.execute_llm_function(func.node_uid, execution_context, call_intent=call_intent)
        return self._finalize_invoke_result(result)

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
    # 携带（``StopIteration.value``）。

    def _prepare_llm_function_call_cps(
        self,
        node_uid: str,
        node_data: Mapping[str, Any],
        execution_context: IExecutionContext,
        param_names: Optional[Any],
    ) -> LLMFunctionCallSpec:
        """CPS 版 LLM 函数调用预求值（段求值经 yield from，worker 安全）。

        与 :meth:`execute_llm_function` 前段（sys/user prompt 段求值 + 意图
        注入 + retry_hint + 返回类型提示）同语义，但段求值经
        ``_evaluate_segments_cps``（yield 嵌入外层 VM 帧栈）——不重入
        ``vm.run``。返回 :class:`LLMFunctionCallSpec`，供 ``_call_and_parse_llm_function``
        在 worker 线程只读执行（快照 intent 列表，不访问 live context）。
        """
        context = execution_context.runtime_context

        sys_prompt = yield from self._evaluate_segments_cps(
            node_data.get("sys_prompt"), execution_context, param_names
        )
        if not isinstance(sys_prompt, str):
            raise TypeError("__sys__ prompt segments must produce text-only content")
        user_prompt = yield from self._evaluate_segments_cps(
            node_data.get("user_prompt"), execution_context, param_names
        )

        merged_intents = context.get_resolved_prompt_intents(execution_context)
        if merged_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
            sys_prompt += intent_block

        retry_hint_segments = None
        frame = context.get_current_llm_except_frame()
        current_retry_hint = frame.retry_hint if frame else None
        if current_retry_hint:
            retry_hint_segments = [current_retry_hint]
        else:
            retry_hint_segments = node_data.get("retry_hint")

        if retry_hint_segments:
            retry_hint_text = yield from self._evaluate_segments_cps(
                retry_hint_segments, execution_context, param_names
            )
            if not isinstance(retry_hint_text, str):
                raise TypeError("retry hint segments must produce text-only content")
            sys_prompt += f"\n\n[重试提示] 上一次执行失败，请参考以下提示进行重试：\n{retry_hint_text}"

        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data["_type"] == "IbName":
                type_name = returns_data.get("id", "str")

        if self.llm_callback:
            type_prompt = self.llm_callback.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        return LLMFunctionCallSpec(
            sys_prompt=sys_prompt,
            user_prompt=user_prompt,
            type_name=type_name,
            node_uid=node_uid,
            active_intents=[
                i.content if hasattr(i, "content") else str(i)
                for i in context.get_active_intents()
            ],
            global_intents=[
                i.content if hasattr(i, "content") else str(i)
                for i in context.get_global_intents()
            ],
            merged_intents=merged_intents,
        )

    def _call_and_parse_llm_function(
        self, spec: LLMFunctionCallSpec, node_uid: str
    ) -> LLMResult:
        """执行 LLM 函数调用并解析结果（worker 线程可安全调用）。

        只读 :class:`LLMFunctionCallSpec`，不访问 live context，不重入 VM，
        不写主线程单写槽（``record_current=False``，由调用方在 yield 恢复点
        记录）。与 :meth:`_call_and_parse`（behavior 路径）同构。
        """
        raw_res = self._call_llm(spec.sys_prompt, spec.user_prompt, node_uid)

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

        if raw_res == MOCK_REPAIR_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_REPAIR_SENTINEL,
                    retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试",
                ),
                _call_info(MOCK_REPAIR_SENTINEL),
                record_current=False,
            )

        if raw_res == MOCK_AMBIGUOUS_SENTINEL:
            return self._finalize_call(
                LLMResult.uncertain_result(
                    raw_response=MOCK_AMBIGUOUS_SENTINEL,
                    retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理",
                ),
                _call_info(MOCK_AMBIGUOUS_SENTINEL),
                record_current=False,
            )

        return self._finalize_call(
            self._parse_result(raw_res, spec.type_name, node_uid),
            _call_info(raw_res),
            record_current=False,
        )

    def execute_llm_function_cps(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None):
        """CPS 版 :meth:`execute_llm_function`；逻辑等价，段求值通过 yield from。

        **LLM 真挂起**（与 behavior 路径 :meth:`execute_behavior_expression_cps`
        同构）：prompt 经 ``_prepare_llm_function_call_cps``（段求值 yield）构建
        spec，随后 ``_call_and_parse_llm_function`` 提交线程池并 ``yield`` 返回的
        ``LLMFuture``——调度器挂起本根、让出给其它根，LLM 就绪后 ``send`` 回
        ``LLMResult`` 恢复。消除了同步 ``_call_llm`` 阻塞调度线程。
        """
        node_data = execution_context.get_node_data(node_uid)
        param_names = self._get_function_param_names(node_data, execution_context)
        spec = yield from self._prepare_llm_function_call_cps(
            node_uid, node_data, execution_context, param_names
        )

        future = self._get_thread_pool().submit(
            self._call_and_parse_llm_function, spec, node_uid
        )
        llm_future = LLMFuture(node_uid=node_uid, future=future)
        result = yield llm_future
        if result is not None and result.call_info is not None:
            self._record_current_call_info(result.call_info)
        return result

    def invoke_llm_function_cps(self, func: IbObject, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None):
        """CPS 版 :meth:`invoke_llm_function`；段求值嵌入外层 VM 帧栈。"""
        result = yield from self.execute_llm_function_cps(
            func.node_uid, execution_context, call_intent=call_intent
        )
        return self._finalize_invoke_result(result)

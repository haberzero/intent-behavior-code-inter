"""``_LLMFunctionMixin`` —— 命名 LLM 函数执行。

包含命名 LLM 函数的同步执行入口 (:meth:`execute_llm_function` /
:meth:`invoke_llm_function`) 及其 CPS 生成器孪生 (:meth:`execute_llm_function_cps`
/ :meth:`invoke_llm_function_cps`)。同步与 CPS 版本成对放置。

依赖 :class:`LLMExecutorCore` 的 ``_call_llm`` / ``llm_callback`` / ``last_call_info``
等共享状态，以及 :class:`_PromptMixin` 的 ``_get_function_param_names`` /
``_evaluate_segments`` / ``_evaluate_segments_cps`` / ``_parse_result``。
"""

from typing import Optional

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult, MOCK_REPAIR_SENTINEL, MOCK_AMBIGUOUS_SENTINEL
from core.base.diagnostics.debugger import CoreModule, DebugLevel

from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent import IbIntent


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
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{name}'")

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

        # 从 LLM Provider 获取返回类型提示
        if self.llm_callback and hasattr(self.llm_callback, 'get_return_type_prompt'):
            type_prompt = self.llm_callback.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        # 5. 调用底层模型
        raw_res = self._call_llm(sys_prompt, user_prompt, node_uid, execution_context=execution_context)

        # 处理 MOCK:REPAIR 特殊标记
        if raw_res == MOCK_REPAIR_SENTINEL:
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": MOCK_REPAIR_SENTINEL,
                "raw_response": MOCK_REPAIR_SENTINEL,
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": merged_intents
            }
            return LLMResult.uncertain_result(
                raw_response=MOCK_REPAIR_SENTINEL,
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        # 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if raw_res == MOCK_AMBIGUOUS_SENTINEL:
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": MOCK_AMBIGUOUS_SENTINEL,
                "raw_response": MOCK_AMBIGUOUS_SENTINEL,
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": merged_intents
            }
            return LLMResult.uncertain_result(
                raw_response=MOCK_AMBIGUOUS_SENTINEL,
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "response": raw_res,
            "raw_response": raw_res,
            "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
            "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
            "merged_intents": merged_intents
        }

        # 6. 解析结果
        return self._parse_result(raw_res, type_name, node_uid)

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
        return self._finalize_invoke_result(result, execution_context)

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
        if not isinstance(sys_prompt, str):
            raise TypeError("__sys__ prompt segments must produce text-only content")
        user_prompt = yield from self._evaluate_segments_cps(user_prompt_segments, execution_context, param_names)

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
            retry_hint_text = yield from self._evaluate_segments_cps(retry_hint_segments, execution_context, param_names)
            if not isinstance(retry_hint_text, str):
                raise TypeError("retry hint segments must produce text-only content")
            sys_prompt += f"\n\n[重试提示] 上一次执行失败，请参考以下提示进行重试：\n{retry_hint_text}"

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

        if raw_res == MOCK_REPAIR_SENTINEL:
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": MOCK_REPAIR_SENTINEL,
                "raw_response": MOCK_REPAIR_SENTINEL,
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": merged_intents
            }
            return LLMResult.uncertain_result(
                raw_response=MOCK_REPAIR_SENTINEL,
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        if raw_res == MOCK_AMBIGUOUS_SENTINEL:
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": MOCK_AMBIGUOUS_SENTINEL,
                "raw_response": MOCK_AMBIGUOUS_SENTINEL,
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": merged_intents
            }
            return LLMResult.uncertain_result(
                raw_response=MOCK_AMBIGUOUS_SENTINEL,
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "response": raw_res,
            "raw_response": raw_res,
            "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_active_intents()],
            "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
            "merged_intents": merged_intents
        }
        return self._parse_result(raw_res, type_name, node_uid)

    def invoke_llm_function_cps(self, func: IbObject, execution_context: IExecutionContext):
        """CPS 版 :meth:`invoke_llm_function`；段求值嵌入外层 VM 帧栈。"""
        call_intent = getattr(func, '_pending_call_intent', None)
        result = yield from self.execute_llm_function_cps(
            func.node_uid, execution_context, call_intent=call_intent
        )
        return self._finalize_invoke_result(result, execution_context)

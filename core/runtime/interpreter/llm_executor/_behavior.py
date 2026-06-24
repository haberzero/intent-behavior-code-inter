"""``_BehaviorMixin`` —— behavior 表达式 / 对象执行。

包含 behavior (即时、匿名 LLM 调用) 的同步执行入口及其 CPS 生成器孪生，
同步与 CPS 版本成对放置于同一文件。

依赖 :class:`LLMExecutorCore` 的 ``_call_llm`` / ``llm_callback`` /
``last_call_info`` / ``push_expected_type`` / ``pop_expected_type`` 等共享状态，
以及 :class:`_PromptMixin` 的 ``_evaluate_segments`` /
``_evaluate_segments_cps`` / ``_get_llmoutput_hint`` /
``_get_expected_type_hint`` / ``_parse_result``。
"""

from typing import Optional

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult

from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.intent import IbIntent
from core.runtime.objects.intent_context import IbIntentContext

from core.kernel.intent_resolver import IntentResolver


class _BehaviorMixin:
    def execute_behavior_expression(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None, captured_intents: Optional['IbIntentContext'] = None, target_model: str = "") -> LLMResult:
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

        ``target_model``：
            - ``""``（空字符串）→ 使用默认模型配置（无 tag 的 @~ ... ~ 语法）
            - 非空字符串 → 路由到命名模型配置（@NAME~ ... ~ 语法中的 NAME）
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

        # 如果未显式传递 target_model，从 node_data 中读取 tag 字段
        if not target_model:
            target_model = node_data.get("tag", "")

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
            if not isinstance(captured_intents, IbIntentContext):
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
        response = self._call_llm(sys_prompt, content, node_uid, target_model=target_model)

        # 6.1 处理 MOCK:REPAIR 特殊标记
        if response == "__MOCK_REPAIR__":
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": content,
                "response": "__MOCK_REPAIR__",
                "raw_response": "__MOCK_REPAIR__",
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": all_intents
            }
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        # 6.2 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if response == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": content,
                "response": "MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                "raw_response": "MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": all_intents
            }
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
            "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
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

        current_retry_hint = context.retry_hint
        context.retry_hint = None
        if provider and not current_retry_hint and hasattr(provider, "_retry_hint"):
            current_retry_hint = provider._retry_hint

        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        if all_intents:
            intent_block = "\n当前上下文意图：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        response = self._call_llm(sys_prompt, content, node_uid, target_model=target_model)

        if response == "__MOCK_REPAIR__":
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": content,
                "response": "__MOCK_REPAIR__",
                "raw_response": "__MOCK_REPAIR__",
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": all_intents
            }
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        if response == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": content,
                "response": "MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                "raw_response": "MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in (captured_intents.get_active_intents() if captured_intents else [])],
                "global_intents": [i.content if hasattr(i, 'content') else str(i) for i in context.get_global_intents()],
                "merged_intents": all_intents
            }
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

"""``_LLMCallableMixin`` —— LLMCallable 统一装配与执行。

对用户自定义 llm 可调用类实例（实现 ``LLMCallable`` 协议 = 含 ``__llm_call__`` 方法）：
- :meth:`assemble_llm_callable_request_cps`：协议门（``satisfies_protocol(..., 'llm_callable'``
  为唯一入口判定）→ CPS 调用用户 ``__llm_call__(self) -> dict``（经 ``UserFunctionCall``
  yield 驱动）→ 把返回装配 dict 映射为一次结构化 :class:`LLMCallRequest`；返回
  ``(request, type_hint, retry_policy)`` 三元组（``retry_policy`` 为 ``__retry__``
  声明的策略或 None）；
- :meth:`invoke_llm_callable_cps`：装配 → 统一 worker ``_call_and_parse``（``_call_llm`` +
  ``_parse_result``），与行为路径同构；声明 ``__retry__`` 时经策略驱动重试循环
  多轮执行（:meth:`_invoke_llm_callable_retry_cps`）。

装配差异经**协议方法自身**承载（机制同构，禁 ``if 标志位`` 过程分派）：用户 llm 类的
``__llm_call__`` 返回装配配置 dict；行为值的装配走既有语义槽路径（后续收敛到统一入口）。
"""
from typing import Any, Dict, Optional

from core.runtime.interfaces import IExecutionContext

from core.base.llm_protocol import LLMCallRequest, OutputContract, IntentBlock
from core.base.llm_protocol.llm_call import PromptSlot

from core.runtime.shared.user_call import UserFunctionCall
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent_context import IbIntentContext


class _StreamCallableDrive:
    """``ai.stream_call`` / ``ai.stream_channel`` 的帧内 CPS 驱动 Waitable。

    与 :class:`_RunLLMCallableDrive` 同范式：VM 主路径经 ``cps_drive`` 帧内 CPS 统一装配
    （行为值 → 语义槽装配 / 用户 llm 可调用类 → 统一装配入口，含 ``__intent__`` 可选
    改写），随后构造 :class:`IbStreamHandle`（producer = provider 流式执行装配好的
    request；后台线程即刻流式生产）。

    - ``channel_mode=False``（stream_call）：**yield 句柄交调度器等待流耗尽**，恢复后
      返回完整文本——与旧字符串形态"调用点 auto-yield 返回完整文本"语义一致
      （``await`` 幂等：``await ai.stream_call(...)`` 与赋值都得到完整文本）；
    - ``channel_mode=True``（stream_channel）：返回包裹 stream Channel 的
      ``IbChannel``，逐块 ``recv`` 增量消费。
    """

    def __init__(self, executor, target, ec, provider_stream, channel_mode: bool):
        self._executor = executor
        self._target = target
        self._ec = ec
        self._provider_stream = provider_stream
        self._channel_mode = channel_mode
        self._done = False
        self._result = None

    @property
    def is_done(self) -> bool:
        return self._done

    def register_wake(self, event) -> None:
        if self._done:
            event.set()

    def cps_drive(self, executor):
        """帧内 CPS 驱动（并入当前调度器；VM 权威路径）。"""
        request = yield from self._executor.assemble_stream_request_cps(self._target, self._ec)
        from core.runtime.objects.stream import IbStreamHandle

        handle = IbStreamHandle(producer=lambda: self._provider_stream(request))
        if self._channel_mode:
            from core.runtime.objects.kernel import IbChannel

            chan_cls = self._executor.registry.get_class("chan")
            self._result = IbChannel(ib_class=chan_cls, core=handle.channel)
        else:
            self._result = yield handle
        self._done = True
        return self._result

    def _drive(self):
        """宿主/线程体同步驱动（无 VM CPS 上下文时；非权威路径）。"""
        from core.runtime.coordinator import _drive_generator

        gen = self.cps_drive(self._ec.vm_executor)
        self._result = _drive_generator(self._ec.vm_executor, gen)
        self._done = True
        return self._result

    def try_result(self):
        if self._done:
            return (True, self._result)
        self._drive()
        return (True, self._result)

    def result(self):
        self._drive()
        return self._result


class _LLMCallableMixin:
    def _resolve_llm_callable_intents(self, ec: IExecutionContext, captured_intents: Optional[Any]):
        """消解进入本次 LLM 调用的意图三层（active/global/merged）。

        行为与 llm 可调用类两条消费路径的**单一权威实现**：``captured_intents``
        为 None 时从实时上下文解析（调用点意图）；非 None 时从冻结快照解析
        （定义时刻意图）。返回 ``(active, globals_, merged, has_override)``。

        意图值已 eager 求值（一等值模型），渲染为同步操作（``resolve_to_prompts``
        直返渲染文本）——本方法为同步函数（历史 CPS 版已随渲染同步化收敛），
        调用方直接调用即可。
        """
        if captured_intents is not None and not isinstance(captured_intents, IbIntentContext):
            raise TypeError(
                f"_resolve_llm_callable_intents: captured_intents must be "
                f"None or IbIntentContext, got {type(captured_intents).__name__}"
            )
        context = ec.runtime_context
        if captured_intents is not None:
            active_list = captured_intents.get_active_intents()
            global_intents = captured_intents.get_global_intents()
            has_override = captured_intents.has_override()
            all_intents = captured_intents.resolve_to_prompts(context, ec)
        else:
            has_override = context.intent_context.has_override()
            all_intents = context.get_resolved_prompt_intents(ec)
            global_intents = context.get_global_intents()
            active_list = context.get_active_intents()
        active = [i.content for i in active_list]
        globals_ = [i.content for i in global_intents]
        merged = [str(i) for i in all_intents]
        return active, globals_, merged, has_override

    def assemble_llm_callable_request_cps(
        self,
        callable_inst: IbObject,
        ec: IExecutionContext,
        *,
        target_model: str = "",
        captured_intents: Optional[Any] = None,
        item: Optional[IbObject] = None,
        call_args: Optional[list] = None,
    ):
        """统一装配：协议门 → 用户 ``__llm_call__``（返回装配 dict）→ LLMCallRequest。

        返回 ``(LLMCallRequest, type_hint, retry_policy)``——``retry_policy`` 为
        ``__retry__`` 可选协议方法声明的策略 dict（``{"max_retry", "hint"}``）或
        None（未声明）。调用方（``invoke_llm_callable_cps`` /
        run_batch / stream）须 ``yield from``。

        - ``item``：run_batch 逐项调用时传入；用户 ``__llm_call__`` 声明
          非 self 参数时作为该参数传入，用于逐项装配；
        - ``call_args``：llm 可调用类实例直接调用 ``f(...)`` 时按位绑定到
          ``__llm_call__`` 非 self 参数；缺省（None）时回落 ``item`` 路径。
        - 装配 dict 契约：``user_prompt``（必需）/ ``output_hint`` /
          ``expected_type`` / ``model`` / ``prompt_slots``（可选，自定义语义槽，
          ``[{kind, text}]``）。
        """
        ib_class = callable_inst.ib_class
        reg = getattr(ib_class, "registry", None)
        meta = reg.get_metadata_registry() if reg is not None else None
        spec = getattr(ib_class, "spec", None)
        if meta is None or spec is None or not meta.satisfies_protocol(spec, "llm_callable"):
            raise TypeError(
                "invoke_llm_callable: value does not satisfy the LLMCallable protocol "
                "(requires '__llm_call__')."
            )

        method = ib_class.lookup_method("__llm_call__")
        if method is None:
            raise TypeError("invoke_llm_callable: __llm_call__ method not found on class.")
        from core.runtime.objects.kernel import IbUserFunction
        if not isinstance(method, IbUserFunction):
            raise TypeError(
                "invoke_llm_callable: __llm_call__ must be a user method "
                f"(got {type(method).__name__})."
            )

        # 非 self 参数检测：`func __llm_call__(self[, any item ...])`。显式 call_args
        # （直接调用 f(args)）按位绑定；否则 run_batch 逐项以 item 作为唯一实参。
        method_spec = getattr(method, "spec", None)
        takes_params = bool(method_spec is not None and getattr(method_spec, "param_types", None))
        if call_args is None:
            call_args = [item] if (item is not None and takes_params) else []

        # CPS 调用用户 __llm_call__(self[, ...]) -> dict（含 Waitable 则调度器挂起）。
        result = yield UserFunctionCall(method, call_args, callable_inst)
        if not isinstance(result, IbObject):
            raise TypeError(
                "invoke_llm_callable: __llm_call__ must return a config dict, "
                f"got {type(result).__name__}."
            )
        config = self._llm_callable_config_to_dict(result)

        active, globals_, merged, has_override = self._resolve_llm_callable_intents(
            ec, captured_intents
        )

        # `__intent__` 可选协议方法运行时发现（receive 同源虚表查找）——
        # 未声明 → 意图原样透传（行为默认透传）；存在 → 用户方法改写进入本次调用
        # 的意图三层（消解/增删/重排），结果合并回装配。
        intent_method = self._discover_optional_protocol_method(callable_inst, "__intent__")
        if intent_method is not None:
            active, globals_, merged = yield from self._apply_intent_rewrite_cps(
                intent_method, callable_inst, active, globals_, merged
            )

        # `__retry__` 可选协议方法运行时发现（同 `__intent__` 通道）——
        # 未声明 → 不自动重试（结果交语句层 llmexcept / LLMParseError，与现状一致）；
        # 存在 → 解析策略声明（max_retry/hint），invoke 路径据此驱动重试循环。
        retry_policy = None
        retry_method = self._discover_optional_protocol_method(callable_inst, "__retry__")
        if retry_method is not None:
            retry_policy = yield from self._resolve_retry_policy_cps(retry_method, callable_inst)

        # 装配 dict 的 `prompt_slots` 键（自定义语义槽，经 __llm_call__ 装配；缺省为空列表）。
        prompt_slots = self._llm_callable_config_prompt_slots(config)

        user_prompt = config.get("user_prompt")
        if user_prompt is None:
            raise TypeError(
                "invoke_llm_callable: __llm_call__ config dict missing 'user_prompt'."
            )
        llmoutput_hint = config.get("output_hint")
        type_hint = config.get("expected_type")
        model = config.get("model") or target_model
        suppress_type_constraint = has_override

        node_uid = getattr(callable_inst, "node", None) or getattr(callable_inst, "node_uid", None)
        request = LLMCallRequest(
            node_uid=node_uid,
            user_prompt=user_prompt,
            prompt_slots=prompt_slots,
            intents=IntentBlock(active=active, global_=globals_, merged=merged),
            output_contract=OutputContract(
                expected_type=None if suppress_type_constraint else type_hint,
                output_hint=None if suppress_type_constraint else llmoutput_hint,
                suppress_type_constraint=suppress_type_constraint,
            ),
            target_model=model,
            message_history=None,
        )
        return request, type_hint, retry_policy

    def _discover_optional_protocol_method(self, callable_inst: IbObject, name: str):
        """可选协议方法运行时发现（receive 分派同源虚表查找，非 getattr 能力探测）。

        ``ib_class.lookup_method`` 与 ``receive`` 普通消息路由同源（虚表 + 继承链），
        是"经 receive 分派发现"的运行期形态。未声明 → 返回 None（装配方取缺省默认
        行为：意图原样透传、retry 用帧默认策略）；声明了却非用户函数方法 → fail-fast
        （契约违约显式暴露，不静默忽略）。
        """
        ib_class = callable_inst.ib_class
        method = ib_class.lookup_method(name)
        if method is None:
            return None
        from core.runtime.objects.kernel import IbUserFunction

        if not isinstance(method, IbUserFunction):
            raise TypeError(
                f"invoke_llm_callable: {name} must be a user method "
                f"(got {type(method).__name__})."
            )
        return method

    def _apply_intent_rewrite_cps(
        self,
        intent_method: "IbUserFunction",
        callable_inst: IbObject,
        active: list,
        globals_: list,
        merged: list,
    ):
        """`__intent__` 可选协议方法装配改写：用户方法改写进入本次调用的意图。

        契约（用户语言层）：``func __intent__(self, dict intents) -> dict``——入参
        ``{"active": [str], "global": [str], "merged": [str]}``（装配时消解的意图三层，
        与 ``LLMCallRequest.intents`` 对齐）；返回 dict 键为三层**任意子集**，存在的键
        替换对应层（消解/增删/重排），缺失的键保持原层（合并语义）。返回非 dict、
        层值非 str 列表、参数数非 1 → fail-fast（``TypeError``，契约违约显式暴露）。
        """
        spec = getattr(intent_method, "spec", None)
        param_count = len(getattr(spec, "param_types", None) or [])
        if param_count != 1:
            raise TypeError(
                "invoke_llm_callable: __intent__ must take exactly one argument "
                "'func __intent__(self, dict intents) -> dict' "
                f"(got {param_count})."
            )

        intent_obj = self.registry.box(
            {"active": active, "global": globals_, "merged": merged}
        )
        result = yield UserFunctionCall(intent_method, [intent_obj], callable_inst)
        config = self._llm_callable_config_to_dict(result, method_name="__intent__")

        def _layer(key: str) -> Optional[list]:
            if key not in config:
                return None
            value = config[key]
            if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
                raise TypeError(
                    f"invoke_llm_callable: __intent__ dict key '{key}' must be a "
                    f"list of str (got {type(value).__name__})."
                )
            return value

        # 键存在即替换对应层（含显式空列表 = 清空该层）；键缺失保持原层（合并语义）。
        new_active = _layer("active") if "active" in config else list(active)
        new_global = _layer("global") if "global" in config else list(globals_)
        new_merged = _layer("merged") if "merged" in config else list(merged)
        return new_active, new_global, new_merged

    def _resolve_retry_policy_cps(
        self,
        retry_method: "IbUserFunction",
        callable_inst: IbObject,
    ):
        """`__retry__` 可选协议方法策略解析。

        契约（用户语言层）：``func __retry__(self) -> dict``——无参（self 除外），
        返回策略声明 dict：``{"max_retry": int(>=1, 可选), "hint": str(可选)}``。
        空 dict 合法（启用默认 max_retry=3 的策略重试）。返回非 dict、参数数非 0、
        max_retry 非 int 或 <1、hint 非 str → fail-fast（契约违约显式暴露）。
        策略语义：hint 为每轮失败后注入的补充要求（重试提示经 retry 轮 user 消息
        回喂，不重复注入 sys_prompt）；耗尽后结果交语句层（llmexcept / LLMParseError）。
        """
        spec = getattr(retry_method, "spec", None)
        param_count = len(getattr(spec, "param_types", None) or [])
        if param_count != 0:
            raise TypeError(
                "invoke_llm_callable: __retry__ must take no arguments "
                "'func __retry__(self) -> dict' "
                f"(got {param_count})."
            )

        result = yield UserFunctionCall(retry_method, [], callable_inst)
        config = self._llm_callable_config_to_dict(result, method_name="__retry__")

        policy: Dict[str, Any] = {}
        if "max_retry" in config:
            max_retry = config["max_retry"]
            if not isinstance(max_retry, int) or max_retry < 1:
                raise TypeError(
                    "invoke_llm_callable: __retry__ dict key 'max_retry' must be "
                    f"an int >= 1 (got {max_retry!r})."
                )
            policy["max_retry"] = max_retry
        if "hint" in config:
            hint = config["hint"]
            if not isinstance(hint, str):
                raise TypeError(
                    "invoke_llm_callable: __retry__ dict key 'hint' must be a str "
                    f"(got {type(hint).__name__})."
                )
            policy["hint"] = hint
        return policy

    @staticmethod
    def _llm_callable_config_prompt_slots(config: Dict[str, Any]) -> list:
        """解析装配 dict 的 ``prompt_slots`` 键（自定义语义槽）。

        ``[{kind: str, text: str}, ...]`` → :class:`PromptSlot` 列表；缺省（无该键）
        → 空列表。形态违约（非 list / 元素非 {kind,text} / 值非 str）→ fail-fast
        （契约违约显式暴露）。
        """
        raw = config.get("prompt_slots")
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise TypeError(
                "invoke_llm_callable: 'prompt_slots' must be a list of "
                f"{{'kind': str, 'text': str}} dicts (got {type(raw).__name__})."
            )
        slots = []
        for entry in raw:
            if not isinstance(entry, dict) or "kind" not in entry or "text" not in entry:
                raise TypeError(
                    "invoke_llm_callable: each 'prompt_slots' entry must be "
                    f"{{'kind': str, 'text': str}} (got {entry!r})."
                )
            kind, text = entry["kind"], entry["text"]
            if not isinstance(kind, str) or not isinstance(text, str):
                raise TypeError(
                    "invoke_llm_callable: 'prompt_slots' entry kind/text must be str "
                    f"(got kind={type(kind).__name__}, text={type(text).__name__})."
                )
            slots.append(PromptSlot(kind=kind, text=text))
        return slots

    @staticmethod
    def _llm_callable_config_to_dict(
        result: IbObject, method_name: str = "__llm_call__"
    ) -> Dict[str, Any]:
        """把用户返回的装配 dict（IbDict）解析为普通配置映射（值 unbox）。"""
        if result.ib_class is not None and result.ib_class.name == "dict":
            fields = getattr(result, "fields", None)
            if fields:
                out: Dict[str, Any] = {}
                for k, v in fields.items():
                    out[k] = v.to_native() if hasattr(v, "to_native") else v
                return out
        native = result.to_native() if hasattr(result, "to_native") else result
        if isinstance(native, dict):
            return dict(native)
        raise TypeError(
            f"invoke_llm_callable: {method_name} must return a config dict "
            f"(got {type(result).__name__})."
        )

    def invoke_llm_callable_cps(
        self, callable_inst: IbObject, ec: IExecutionContext, *, target_model: str = "", item: Optional[IbObject] = None, call_args: Optional[list] = None
    ):
        """执行入口：统一装配 → 统一 worker（_call_llm + _parse_result）。

        ``call_args``：llm 可调用类实例直接调用 ``f(args)`` 时按位绑定到
        ``__llm_call__`` 非 self 参数；缺省回落 ``item`` 路径（run_batch 逐项）。

        装配发现 ``__retry__`` 策略时走策略驱动重试循环
        （:meth:`_invoke_llm_callable_retry_cps`）；未声明则单次调用（现状路径）。
        """
        request, type_hint, retry_policy = yield from self.assemble_llm_call_request_cps(
            callable_inst, ec, target_model=target_model, item=item, call_args=call_args
        )
        if retry_policy is not None:
            result = yield from self._invoke_llm_callable_retry_cps(
                request, type_hint, retry_policy, ec
            )
        else:
            from core.runtime.interpreter.llm_executor._behavior import BehaviorCallSpec
            from core.runtime.shared.llm_result import LLMFuture

            spec = BehaviorCallSpec(request=request, type_hint=type_hint)
            future = self._get_thread_pool().submit(
                self._call_and_parse, spec, request.node_uid, ec
            )
            llm_future = LLMFuture(node_uid=request.node_uid, future=future)
            result = yield llm_future
        if result is not None and result.call_info is not None:
            self._record_current_call_info(result.call_info)
        return result

    def _invoke_llm_callable_retry_cps(
        self,
        request: "LLMCallRequest",
        type_hint: Optional[str],
        retry_policy: dict,
        ec: IExecutionContext,
    ):
        """`__retry__` 策略驱动重试循环。

        语义：每轮经统一 worker（``_call_and_parse``）执行；结果不确定时记入
        失败尝试（raw_response/parse_error/hint），用 :mod:`_prompt_assembly`
        单一消息构造（``build_retry_message_history_from_attempts``）累积多轮
        对话历史（``message_history``，provider 追加在首轮之后），再执行下一轮——
        与行为路径的 llmexcept 帧回喂语义一致（hint 经 retry 轮 user 消息回喂，
        不重复注入 sys_prompt）。

        达到 ``max_retry``（声明缺省 3）仍不确定 → 返回最后一次不确定结果，
        交语句层（llmexcept 帧接管 / 无帧则 LLMParseError），与无策略路径一致。
        """
        from dataclasses import replace

        from core.runtime.interpreter.llm_executor._behavior import BehaviorCallSpec
        from core.runtime.interpreter.llm_executor._prompt_assembly import (
            build_retry_message_history_from_attempts,
        )
        from core.runtime.shared.llm_result import LLMFuture

        max_retry = retry_policy.get("max_retry") or 3
        hint = retry_policy.get("hint")
        attempts: list = []
        while True:
            spec = BehaviorCallSpec(request=request, type_hint=type_hint)
            future = self._get_thread_pool().submit(
                self._call_and_parse, spec, request.node_uid, ec
            )
            llm_future = LLMFuture(node_uid=request.node_uid, future=future)
            result = yield llm_future
            if result is None or not result.is_uncertain:
                return result
            attempts.append(
                {
                    "raw_response": result.raw_response or "",
                    "parse_error": result.retry_hint or None,
                    "user_hint": hint,
                }
            )
            if len(attempts) >= max_retry:
                # 耗尽：把最后一次不确定结果交语句层（llmexcept 接管 / LLMParseError）
                return result
            history = build_retry_message_history_from_attempts(attempts)
            request = replace(request, message_history=history)

    def _is_llm_callable_value(self, value: IbObject, ec: IExecutionContext) -> bool:
        """LLMCallable 值判定（satisfies 唯一入口，供 run_batch/stream 校验）。

        satisfies_protocol 异常向上暴露（fail-fast）：元数据与 spec 齐备时判定失败
        是真实错误，不得静默判否为"不可调用"。
        """
        ib_class = getattr(value, "ib_class", None)
        if ib_class is None:
            return False
        reg = getattr(ib_class, "registry", None)
        meta = reg.get_metadata_registry() if reg is not None else None
        spec = getattr(ib_class, "spec", None)
        if meta is None or spec is None:
            return False
        return bool(meta.satisfies_protocol(spec, "llm_callable"))

    def assemble_llm_call_request_cps(
        self,
        target: IbObject,
        ec: IExecutionContext,
        *,
        target_model: str = "",
        captured_intents: Optional[Any] = None,
        item: Optional[IbObject] = None,
        call_args: Optional[list] = None,
    ):
        """统一装配入口：按值类型选装配策略，返回 ``(request, type_hint, retry_policy)``。

        - behavior 值 → 语义槽装配（:meth:`_prepare_behavior_call_cps`，``retry_policy=None``）；
        - 用户 llm 可调用类 → 用户装配 dict（:meth:`assemble_llm_callable_request_cps`，
          含 ``__intent__``/``__retry__`` 可选协议）；
        - 其它值 → fail-fast ``TypeError``。

        装配差异经值自身承载（行为→语义槽、llm 类→用户 dict 是本质差异），
        但分派入口单一——``run_batch``/``invoke``/``stream`` 等值路径消费方不再各自
        重复 ``if behavior/elif llm_callable`` 判断（行为表达式路径按 node_uid 装配，
        不经本入口，见 :meth:`_prepare_behavior_call_cps`）。
        """
        from core.runtime.objects.kernel import IbValue

        if isinstance(target, IbValue) and target.ib_class.name == "behavior":
            node = getattr(target, "node", None)
            if node is None:
                raise TypeError("assemble_llm_call_request: behavior value has no node data.")
            node_data = ec.get_node_data(node)
            if node_data is None:
                raise TypeError(f"assemble_llm_call_request: behavior node data not found for '{node}'.")
            captured = (
                captured_intents
                if captured_intents is not None
                else getattr(target, "captured_intents", None)
            )
            spec = yield from self._prepare_behavior_call_cps(
                node, node_data, ec, captured_intents=captured, target_model=target_model
            )
            return spec.request, spec.type_hint, None
        if self._is_llm_callable_value(target, ec):
            request, type_hint, retry_policy = yield from self.assemble_llm_callable_request_cps(
                target, ec, target_model=target_model, captured_intents=captured_intents,
                item=item, call_args=call_args,
            )
            return request, type_hint, retry_policy
        raise TypeError(
            "assemble_llm_call_request: expected a behavior or LLMCallable instance, "
            f"got {type(target).__name__}"
        )

    def assemble_stream_request_cps(self, target: IbObject, ec: IExecutionContext):
        """统一流式装配：行为值 / 用户 llm 可调用类 → ``LLMCallRequest``（CPS）。

        委托统一装配入口 :meth:`assemble_llm_call_request_cps`（单一分派源）——
        行为值走语义槽装配（零行为变化）；用户 llm 类经用户装配 dict
        （含 ``__intent__`` 可选改写）。其它值 → fail-fast（同一拒绝消息）。
        """
        request, _, _ = yield from self.assemble_llm_call_request_cps(target, ec)
        return request

    def make_stream_callable_drive(
        self,
        target: IbObject,
        ec: IExecutionContext,
        *,
        provider_stream,
        channel_mode: bool = False,
    ):
        """构造流式消费的帧内 CPS 驱动 Waitable（供 ``ai.stream_call``/``stream_channel`` 使用）。

        ``provider_stream`` = provider 的流式执行可调用（``(LLMCallRequest) -> iter[str]``），
        由调用方（ai 模块宿主）注入；``channel_mode`` 为 True 时驱动完成后返回包裹
        stream Channel 的 ``IbChannel``。
        """
        return _StreamCallableDrive(self, target, ec, provider_stream, channel_mode)

    # ------------------------------------------------------------------ #
    # run_batch 逐项批量（items 逐项作为 __llm_call__ 的 item 参）          #
    # ------------------------------------------------------------------ #

    def _invoke_llm_callable_batch_cps(self, callable_inst: IbObject, items, ec: IExecutionContext):
        """CPS 逐项执行：每 item 一次 LLM 调用（经统一装配 + 统一 worker，
        返回 boxed 结果列表）。当前逐项顺序执行（并发优化留待后续）。"""
        values = []
        for item in items:
            result = yield from self.invoke_llm_callable_cps(callable_inst, ec, item=item)
            values.append(result.value if result is not None else self.registry.get_none())
        return self.registry.box(values)

    def _invoke_llm_callable_batch_sync(self, callable_inst: IbObject, items, ec: IExecutionContext):
        """宿主/线程体同步兜底：经 _drive_generator 驱动 CPS 批量版。"""
        from core.runtime.coordinator import _drive_generator

        gen = self._invoke_llm_callable_batch_cps(callable_inst, items, ec)
        return _drive_generator(ec.vm_executor, gen)

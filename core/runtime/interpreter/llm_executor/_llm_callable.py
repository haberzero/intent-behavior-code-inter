"""``_LLMCallableMixin`` —— LLMCallable 统一装配与执行（P1 §2.4 消费路径统一）。

对用户自定义 llm 可调用类实例（实现 ``LLMCallable`` 协议 = 含 ``__llm_call__`` 方法）：
- :meth:`assemble_llm_callable_request_cps`：协议门（``satisfies_protocol(..., 'llm_callable'``
  为唯一入口判定）→ CPS 调用用户 ``__llm_call__(self) -> dict``（经 ``UserFunctionCall``
  yield 驱动）→ 把返回装配 dict 映射为一次结构化 :class:`LLMCallRequest`；
- :meth:`invoke_llm_callable_cps`：装配 → 统一 worker ``_call_and_parse``（``_call_llm`` +
  ``_parse_result``），与行为路径同构。

装配差异经**协议方法自身**承载（机制同构，禁 ``if 标志位`` 过程分派）：用户 llm 类的
``__llm_call__`` 返回装配配置 dict；行为值的装配走既有语义槽路径（后续 P4b-2b 收敛到统一入口）。
"""
from typing import Any, Dict, Optional

from core.runtime.interfaces import IExecutionContext

from core.base.llm_protocol import LLMCallRequest, OutputContract, IntentBlock

from core.runtime.shared.user_call import UserFunctionCall
from core.runtime.objects.kernel import IbObject


class _LLMCallableMixin:
    def _resolve_llm_callable_intents_cps(self, ec: IExecutionContext, captured_intents: Optional[Any]):
        """消解进入本次 LLM 调用的意图三层（active/global/merged），行为/llm 类共用。"""
        context = ec.runtime_context
        if captured_intents is not None:
            active_list = captured_intents.get_active_intents()
            global_intents = captured_intents.get_global_intents()
            has_override = captured_intents.has_override()
            all_intents = yield from captured_intents.resolve_to_prompts_cps(context, ec)
        else:
            has_override = context.intent_context.has_override()
            all_intents = yield from context.get_resolved_prompt_intents_cps(ec)
            global_intents = context.get_global_intents()
            active_list = context.get_active_intents()
        active = [i.content if hasattr(i, "content") else str(i) for i in active_list]
        globals_ = [i.content if hasattr(i, "content") else str(i) for i in global_intents]
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
    ):
        """统一装配：协议门 → 用户 ``__llm_call__``（返回装配 dict）→ LLMCallRequest。

        返回 ``(LLMCallRequest, type_hint)``。调用方（``invoke_llm_callable_cps`` /
        run_batch）须 ``yield from``。``item``（P4b-2c）：run_batch 逐项调用时传入；
        用户 ``__llm_call__`` 声明非 self 参数（``__llm_call__(self, any item)``）
        时作为该参数传入，用于逐项装配。
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

        # item 参检测：用户 'func __llm_call__(self, any item)' 声明非 self 参数时，逐项调用传 item。
        method_spec = getattr(method, "spec", None)
        takes_item = bool(method_spec is not None and getattr(method_spec, "param_types", None))
        call_args = [item] if (item is not None and takes_item) else []

        # CPS 调用用户 __llm_call__(self[, item]) -> dict（含 Waitable 则调度器挂起）。
        result = yield UserFunctionCall(method, call_args, callable_inst)
        if not isinstance(result, IbObject):
            raise TypeError(
                "invoke_llm_callable: __llm_call__ must return a config dict, "
                f"got {type(result).__name__}."
            )
        config = self._llm_callable_config_to_dict(result)

        active, globals_, merged, has_override = yield from self._resolve_llm_callable_intents_cps(
            ec, captured_intents
        )

        # P4b-3a：`__intent__` 可选协议方法运行时发现（receive 同源虚表查找）——
        # 未声明 → 意图原样透传（行为默认透传）；存在 → 用户方法改写进入本次调用
        # 的意图三层（消解/增删/重排），结果合并回装配。
        intent_method = self._discover_optional_protocol_method(callable_inst, "__intent__")
        if intent_method is not None:
            active, globals_, merged = yield from self._apply_intent_rewrite_cps(
                intent_method, callable_inst, active, globals_, merged
            )

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
            intents=IntentBlock(active=active, global_=globals_, merged=merged),
            output_contract=OutputContract(
                expected_type=None if suppress_type_constraint else type_hint,
                output_hint=None if suppress_type_constraint else llmoutput_hint,
                suppress_type_constraint=suppress_type_constraint,
            ),
            target_model=model,
            message_history=None,
        )
        return request, type_hint

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
        """`__intent__` 可选协议方法装配改写（P4b-3a）：用户方法改写进入本次调用的意图。

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
        self, callable_inst: IbObject, ec: IExecutionContext, *, target_model: str = "", item: Optional[IbObject] = None
    ):
        """执行入口：统一装配 → 统一 worker（_call_llm + _parse_result）。"""
        request, type_hint = yield from self.assemble_llm_callable_request_cps(
            callable_inst, ec, target_model=target_model, item=item
        )
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

    def _is_llm_callable_value(self, value: IbObject, ec: IExecutionContext) -> bool:
        """LLMCallable 值判定（satisfies 唯一入口，供 run_batch/stream 校验）。"""
        ib_class = getattr(value, "ib_class", None)
        if ib_class is None:
            return False
        reg = getattr(ib_class, "registry", None)
        meta = reg.get_metadata_registry() if reg is not None else None
        spec = getattr(ib_class, "spec", None)
        try:
            return bool(meta is not None and spec is not None and meta.satisfies_protocol(spec, "llm_callable"))
        except Exception:
            return False

    def _invoke_llm_callable_cps_boxed(self, callable_inst: IbObject, ec: IExecutionContext):
        """CPS 驱动统一装配 + 执行，返回 boxed 单元素 IbList（run_batch 消费面）。"""
        result = yield from self.invoke_llm_callable_cps(callable_inst, ec)
        value = result.value if result is not None else self.registry.get_none()
        return self.registry.box([value])

    def _invoke_llm_callable_sync(self, callable_inst: IbObject, ec: IExecutionContext):
        """宿主/线程体同步兜底（非 VM CPS 上下文）：经 _drive_generator 驱动。"""
        from core.runtime.coordinator import _drive_generator

        gen = self.invoke_llm_callable_cps(callable_inst, ec)
        result = _drive_generator(ec.vm_executor, gen)
        value = result.value if result is not None else self.registry.get_none()
        return [value]

    # ------------------------------------------------------------------ #
    # P4b-2c：run_batch 逐项批量（items 逐项作为 __llm_call__ 的 item 参）  #
    # ------------------------------------------------------------------ #

    def _invoke_llm_callable_batch_cps(self, callable_inst: IbObject, items, ec: IExecutionContext):
        """CPS 逐项执行：每 item 一次 LLM 调用（经统一装配 + 统一 worker），
        返回 boxed 结果列表。当前逐项顺序执行（并发优化留待后续）。"""
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

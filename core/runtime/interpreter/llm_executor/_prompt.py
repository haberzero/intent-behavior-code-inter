"""``_PromptMixin`` —— 提示词构建与结果解析。

包含所有将 IbObject / 段列表转换为 prompt 文本或多模态 content blocks 的方法，
以及 LLM 输出结果的解析入口。所有方法均依赖 :class:`LLMExecutorCore` 提供的
共享状态 (``self.registry`` / ``self._result_parser`` 等)。
"""

from typing import Any, List, Optional, Dict, Union, Mapping, Set

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult

from core.runtime.interpreter.llm_parsing_strategy import LLMResultParser
from core.runtime.objects.kernel.base import IbObject
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK
from core.kernel import ast as ib_ast


class _PromptMixin:
    def _try_axiom_output_hint(self, type_name: str) -> Optional[str]:
        """Axiom 输出格式约束查找（sync/CPS 两路径共享单一实现）。

        经 ``meta_reg.get_llm_output_hint_cap(descriptor)`` 查询内置类型的
        ``__outputhint_prompt__``；用户类 vtable 分支由各路径各自驱动
        （sync ``.call`` / CPS ``UserFunctionCall``），不在本方法内。
        """
        meta_reg = self.registry.get_metadata_registry()
        if meta_reg:
            descriptor = meta_reg.resolve(type_name)
            if descriptor:
                hint_cap = meta_reg.get_llm_output_hint_cap(descriptor)
                if hint_cap:
                    return hint_cap.__outputhint_prompt__(descriptor)
        return None

    @staticmethod
    def _obj_to_prompt_str(val: Any) -> str:
        """Unified protocol-aware conversion of an IbObject to prompt string.

        Resolution order:
        1. __to_prompt__() method via receive() (the canonical prompt protocol)
        2. to_native() fallback (primitive unwrapping)
        3. str() last resort

        This replaces scattered ``hasattr(val, '__to_prompt__')`` checks
        throughout the prompt construction pipeline, using unified vtable dispatch.
        """
        # Try __to_prompt__ through receive() (unified protocol dispatch)
        if hasattr(val, 'receive'):
            try:
                result = val.receive('__to_prompt__', [])
                # Unwrap if result is an IbObject
                if isinstance(result, IbObject):
                    return str(result.to_native())
                return str(result)
            except AttributeError:
                # 协议缺失（receive 对未声明方法抛 AttributeError）→ 回退；
                # 用户 __to_prompt__ 实现体内的真实 bug（TypeError 等）fail-fast，
                # 不再被宽 except 吞掉后静默降级 str()。
                pass

        # Fallback to to_native() for primitives
        if isinstance(val, IbObject):
            try:
                return str(val.to_native())
            except AttributeError:
                pass

        # Last resort: str()
        return str(val)

    @staticmethod
    def _obj_to_payload(val: Any) -> Union[str, Dict[str, Any], List[Dict[str, Any]]]:
        """Protocol-aware conversion of an IbObject to payload content block.

        Resolution order:
        1. __payload_prompt__() via receive() — returns str, dict, or list of dicts
        2. Fallback to _obj_to_prompt_str() (pure text)

        When a value has __payload_prompt__ capability, it can return structured
        content blocks for multi-modal LLM API payloads (e.g. image_url, input_audio).
        If the value only supports __to_prompt__, falls back to plain text.
        """
        if hasattr(val, 'receive'):
            # Try __payload_prompt__ first (multi-modal protocol)
            try:
                result = val.receive('__payload_prompt__', [])
                if result is not None:
                    # Unwrap IbObject wrappers
                    if isinstance(result, IbObject):
                        native = result.to_native()
                        # dict or list of dicts → structured content block
                        if isinstance(native, (dict, list)):
                            return native
                        return str(native)
                    # Already a dict/list (raw return from user class)
                    if isinstance(result, (dict, list)):
                        return result
                    return str(result)
            except AttributeError:
                # 协议缺失（receive 对未声明方法抛 AttributeError）→ 回退纯文本；
                # 用户 __payload_prompt__ 实现体内的真实 bug（TypeError 等）告警，
                # 不再被宽 except 吞掉后静默降级为纯文本。
                pass
            except Exception as e:
                kernel_diagnostic(
                    code=KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK,
                    detail={"error": repr(e)},
                    message=(
                        f"__payload_prompt__ dispatch failed, "
                        f"falling back to text: {e!r}"
                    ),
                )

        # Fallback to plain text via __to_prompt__
        return _PromptMixin._obj_to_prompt_str(val)

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

    def _evaluate_segments(self, segments: Optional[List[Any]], execution_context: IExecutionContext, param_names: Optional[Set[str]] = None) -> Union[str, List[Union[str, Dict[str, Any]]]]:
        """同步版段求值入口。

        实现委托给 ``_evaluate_segments_cps`` 生成器；当 ``vm_executor`` 可用时，
        通过 ``vm.run(uid)`` 对 yield 出的子节点求值。该路径用于：
        - ``dispatch_eager`` 在后台线程中的同步求值
        - 不经 VM 调度的测试路径

        CPS 主路径（由 VM handler 触发的 invoke_*）改用 ``_evaluate_segments_cps``
        + ``yield from``，使段求值作为子任务嵌入到外层 VM 帧栈，而非启动一个
        独立的 ``_drive_loop``，从而正确反映 ``frame_stack_depth``。

        返回值：
        - str: 纯文本内容
        - List[Union[str, dict]]: 含多模态结构化 content blocks
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
            return si.value if si.value is not None else ""

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

        返回值：
        - 纯文本情况：返回拼接后的 str
        - 含多模态内容：返回 List[Union[str, dict]]（混合 content blocks）
          调用方通过 isinstance 检查决定走纯文本路径还是多模态路径。
        """
        if not segments:
            return ""

        content_parts: List[Any] = []  # Union[str, dict, List[dict]]
        has_structured = False  # 是否包含非文本结构化内容

        for segment in segments:
            if isinstance(segment, Mapping) and segment.get("_type") == "ext_ref":
                val = execution_context.resolve_value(segment)
                content_parts.append(str(val))
                continue

            if isinstance(segment, str):
                if segment.startswith("node_"):
                    val = yield segment
                    payload = self._obj_to_payload(val)
                    if isinstance(payload, (dict, list)):
                        has_structured = True
                        content_parts.append(payload)
                    else:
                        content_parts.append(payload)
                else:
                    content_parts.append(segment)
            elif isinstance(segment, ib_ast.IbName):
                # IbName 节点（变量引用）
                var_name = segment.id

                # 只有当变量名是函数参数时才进行替换
                if param_names and var_name in param_names:
                    val = yield segment
                    payload = self._obj_to_payload(val)
                    if isinstance(payload, (dict, list)):
                        has_structured = True
                        content_parts.append(payload)
                    else:
                        content_parts.append(payload)
                else:
                    # 非函数参数的 $auto，作为普通文本处理（保持 $ 符号）
                    content_parts.append(f"${var_name}")
            else:
                content_parts.append(str(segment))

        # 全部为纯文本时返回拼接 str
        if not has_structured:
            return "".join(content_parts)

        # 多模态路径：返回混合 content parts 列表
        # 合并相邻 str 块以减少 API payload 碎片
        merged: List[Union[str, Dict[str, Any]]] = []
        text_buf: List[str] = []
        for part in content_parts:
            if isinstance(part, str):
                text_buf.append(part)
            elif isinstance(part, dict):
                if text_buf:
                    merged.append("".join(text_buf))
                    text_buf = []
                merged.append(part)
            elif isinstance(part, list):
                # List[dict] — multiple content blocks from one value
                if text_buf:
                    merged.append("".join(text_buf))
                    text_buf = []
                merged.extend(part)
        if text_buf:
            merged.append("".join(text_buf))
        return merged

    def _get_llmoutput_hint(self, node_uid: str, node_data: Mapping[str, Any], execution_context: IExecutionContext) -> Optional[str]:
        """获取 __outputhint_prompt__ 用于注入到提示词

        查找顺序：
        1. Axiom 内置类型：经 ``_try_axiom_output_hint``（共享实现）
        2. 用户自定义 IBCI 类：通过类 vtable 查找 __outputhint_prompt__ 方法
        """
        def _try_vtable_hint(type_name: str, module: Optional[str] = None) -> Optional[str]:
            """回退：通过用户类 vtable 查找 __outputhint_prompt__（类方法语义）"""
            ib_class = self.registry.get_class(type_name, module=module)
            if ib_class:
                method = ib_class.lookup_method('__outputhint_prompt__')
                if method:
                    # lookup_method 已预检方法存在——此处无"协议缺失"情形；
                    # 用户方法实现体的真实 bug 直接 fail-fast，不再静默吞掉后无 hint。
                    result = method.call(ib_class, [])
                    hint = result.to_native() if isinstance(result, IbObject) else str(result)
                    return str(hint) if hint is not None else None
            return None

        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data.get("_type") == "IbName":
                type_name = returns_data.get("id", "str")
                hint = self._try_axiom_output_hint(type_name)
                if hint is not None:
                    return hint
                hint = _try_vtable_hint(type_name)
                if hint is not None:
                    return hint

        node_to_type = execution_context.get_side_table("node_to_type", node_uid)
        if node_to_type:
            type_name = getattr(node_to_type, 'name', None)
            if type_name:
                hint = self._try_axiom_output_hint(type_name)
                if hint is not None:
                    return hint
                # [Module Identity] 用户类 hint 查找按 module 限定
                # （node_to_type spec 携带 module_path；跨模块同名类不误选）。
                hint = _try_vtable_hint(
                    type_name,
                    module=getattr(node_to_type, "module_path", None),
                )
                if hint is not None:
                    return hint

        return None

    def _get_llmoutput_hint_cps(self, node_uid: str, node_data: Mapping[str, Any], execution_context: IExecutionContext):
        """CPS 版 :meth:`_get_llmoutput_hint`（用户 hint vtable 分支 CPS 化）。

        与同步版同语义，但用户 hint 方法（``__outputhint_prompt__``）经
        ``UserFunctionCall`` trampoline 驱动（复用统一用户方法 CPS 路径），
        而非同步 ``.call``——后者在 CPS 行为路径内会嵌套调度器，若 hint 方法
        含 Waitable 则死锁。本方法是生成器，yield ``UserFunctionCall`` 由 VM
        调度循环压栈驱动；调用方须 ``yield from``。
        """
        from core.runtime.shared.user_call import UserFunctionCall

        def _drive_vtable_hint(type_name: str, module: Optional[str] = None):
            """用户类 vtable hint：yield UserFunctionCall 驱动（CPS 主路径）。"""
            ib_class = self.registry.get_class(type_name, module=module)
            if not ib_class:
                return None
            method = ib_class.lookup_method('__outputhint_prompt__')
            if not method:
                return None
            from core.runtime.objects.kernel import IbUserFunction, IbLLMFunction
            if isinstance(method, (IbUserFunction, IbLLMFunction)):
                result = yield UserFunctionCall(method, [], ib_class)
            else:
                # 原生 hint 方法：同步调用（非调度路径，无嵌套调度器）。
                result = method.call(ib_class, [])
            hint = result.to_native() if isinstance(result, IbObject) else str(result)
            return str(hint) if hint is not None else None

        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data.get("_type") == "IbName":
                type_name = returns_data.get("id", "str")
                hint = self._try_axiom_output_hint(type_name)
                if hint is not None:
                    return hint
                hint = yield from _drive_vtable_hint(type_name)
                if hint is not None:
                    return hint

        node_to_type = execution_context.get_side_table("node_to_type", node_uid)
        if node_to_type:
            type_name = getattr(node_to_type, 'name', None)
            if type_name:
                hint = self._try_axiom_output_hint(type_name)
                if hint is not None:
                    return hint
                hint = yield from _drive_vtable_hint(
                    type_name,
                    module=getattr(node_to_type, "module_path", None),
                )
                if hint is not None:
                    return hint

        return None

    def _get_expected_type_hint(self, node_uid: str, node_data: Mapping[str, Any], execution_context: IExecutionContext) -> Optional[str]:
        """获取预期的类型名称（module 感知），用于 __from_prompt__ 解析。

        [S2 类身份统一] 优先 node_to_type 侧表（含 module_path 的 spec）——
        返回 qualified 名（``main.Point`` / ``str``），策略内 ``resolve`` /
        ``get_class`` 精确命中 qualified 键（入口类已 module 化不再裸名）。
        returns IbName 裸名路径按当前模块上下文解析为 qualified（与
        ``SpecRegistry.resolve(name, module)`` 同构）。
        """
        node_to_type = execution_context.get_side_table("node_to_type", node_uid)
        if node_to_type:
            name = getattr(node_to_type, "name", None)
            if name:
                module = getattr(node_to_type, "module_path", None)
                return f"{module}.{name}" if module else name

        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data.get("_type") == "IbName":
                bare_name = returns_data.get("id", "str")
                module = getattr(execution_context, "current_module_name", None)
                meta_reg = self.registry.get_metadata_registry()
                if meta_reg is not None and module:
                    spec = meta_reg.resolve(bare_name, module)
                    if spec is not None and getattr(spec, "module_path", None):
                        return f"{spec.module_path}.{bare_name}"
                return bare_name

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
        if self._result_parser is None:
            # hydrate() 已初始化；此处为 None 说明未水化即执行——fail-fast（
            # 原懒重建是 worker 线程可触发的潜在竞争 + 静默兜底，违反 fail-fast）。
            raise RuntimeError(
                "LLMExecutor: result parser not initialized; hydrate() must be called "
                "before _parse_result() (pre-hydration parse is not supported)."
            )

        return self._result_parser.parse_result(raw_res, type_name, node_uid, execution_context)

"""``_PromptMixin`` —— 提示词构建与结果解析。

包含所有将 IbObject / 段列表转换为 prompt 文本或多模态 content blocks 的方法，
以及 LLM 输出结果的解析入口。所有方法均依赖 :class:`LLMExecutorCore` 提供的
共享状态 (``self.registry`` / ``self.debugger`` / ``self._result_parser`` 等)。
"""

from typing import Any, List, Optional, Dict, Union, Mapping, Set

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult
from core.base.diagnostics.debugger import CoreModule, DebugLevel

from core.runtime.interpreter.llm_parsing_strategy import LLMResultParser


class _PromptMixin:
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
                if hasattr(result, 'to_native'):
                    return str(result.to_native())
                return str(result)
            except Exception:
                pass

        # Fallback to to_native() for primitives
        if hasattr(val, 'to_native'):
            try:
                return str(val.to_native())
            except Exception:
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
                    if hasattr(result, 'to_native'):
                        native = result.to_native()
                        # dict or list of dicts → structured content block
                        if isinstance(native, (dict, list)):
                            return native
                        return str(native)
                    # Already a dict/list (raw return from user class)
                    if isinstance(result, (dict, list)):
                        return result
                    return str(result)
            except Exception:
                pass

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
        """同步版段求值（兼容入口）。

        实现委托给 ``_evaluate_segments_cps`` 生成器；当 ``vm_executor`` 可用时，
        通过 ``vm.run(uid)`` 对 yield 出的子节点求值。该路径用于：
        - ``dispatch_eager`` 在后台线程中的同步求值
        - 不经 VM 调度的旧测试路径

        CPS 主路径（由 VM handler 触发的 invoke_*）改用 ``_evaluate_segments_cps``
        + ``yield from``，使段求值作为子任务嵌入到外层 VM 帧栈，而非启动一个
        独立的 ``_drive_loop``，从而正确反映 ``frame_stack_depth``。

        返回值：
        - str: 纯文本内容（向后兼容路径）
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

        返回值：
        - 纯文本情况：返回拼接后的 str（向后兼容）
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
            elif hasattr(segment, 'id'):
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

        # 向后兼容：全部为纯文本时返回拼接 str
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

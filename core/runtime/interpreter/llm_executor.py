import re
import json
from types import SimpleNamespace
from typing import Any, List, Optional, Dict, Union, Callable, Mapping, Set, Tuple, TYPE_CHECKING
from core.runtime.interfaces import LLMExecutor, RuntimeContext, ServiceContext, InterOp, Registry, IExecutionContext
from core.base.interfaces import ILLMProvider, IssueTracker

from core.kernel.issue import InterpreterError
from core.runtime.interpreter.llm_result import LLMResult
from core.base.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent import IbIntent
from core.runtime.objects.builtins import IbBehavior

from core.kernel.intent_logic import IntentMode, IntentRole
from core.kernel.intent_resolver import IntentResolver
from core.kernel.registry import KernelRegistry

class LLMExecutorImpl:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
     采用上下文注入模式，支持延迟水化以消除解释器内部的属性补丁。
    """
    def __init__(self, 
                 service_context: Optional[ServiceContext] = None,
                 execution_context: Optional[IExecutionContext] = None):
        """
        service_context: 运行时服务聚合容器 (可能在构造期为 None)
        execution_context: 执行状态容器
        """
        self._service_context = service_context
        self._execution_context = execution_context
        
        self.last_call_info: Mapping[str, Any] = {} # 记录最后一次 LLM 调用信息
        self._expected_type_stack: List[str] = []

    def hydrate(self, service_context: ServiceContext):
        """ 水化依赖，由解释器在服务准备就绪后调用"""
        self._service_context = service_context

    @property
    def service_context(self) -> ServiceContext:
        if not self._service_context:
            raise RuntimeError("LLMExecutorImpl: ServiceContext not hydrated.")
        return self._service_context

    @property
    def registry(self) -> Registry: return self.service_context.registry
    @property
    def interop(self) -> InterOp: return self.service_context.interop
    @property
    def issue_tracker(self) -> IssueTracker: return self.service_context.issue_tracker
    @property
    def debugger(self) -> Any: return self.service_context.debugger or core_debugger
    @property
    def llm_callback(self) -> Optional[ILLMProvider]:
        # 唯一来源：通过能力注册中心获取 Provider (能力名: llm_provider)
        # ibci_ai.setup() 在加载时调用 capabilities.expose("llm_provider", self) 完成注册。
        if self.service_context.capability_registry:
            provider = self.service_context.capability_registry.get("llm_provider")
            if provider:
                return provider
        return None

    def push_expected_type(self, type_name: str):
        self._expected_type_stack.append(type_name)
    
    def pop_expected_type(self):
        if self._expected_type_stack:
            self._expected_type_stack.pop()
    def get_last_call_info(self) -> Mapping[str, Any]:
        """获取最后一次 LLM 调用信息"""
        # 优先返回 executor 自身记录的信息（包含合并后的 Prompt）
        if self.last_call_info:
            return self.last_call_info
            
        # 否则尝试从 Provider (ai 模块) 获取
        if self.llm_callback and hasattr(self.llm_callback, 'get_last_call_info'):
            return self.llm_callback.get_last_call_info()
            
        return {}

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
        
        # 首先检查运行时上下文中的 retry_hint（来自 llmretry 语句）
        current_retry_hint = context.retry_hint
        if current_retry_hint:
            retry_hint_segments = [current_retry_hint]
        else:
            # 回退到函数定义中的 __llmretry__ 提示词
            retry_hint_segments = node_data.get("retry_hint")
        
        # 如果有 retry_hint，注入到系统提示词
        if retry_hint_segments:
            retry_hint_text = self._evaluate_segments(retry_hint_segments, execution_context, param_names)
            sys_prompt += f"\n\n[重试提示] 上一次执行失败，请参考以下提示进行重试：\n{retry_hint_text}"
            
        # 清除运行时上下文中的 retry_hint（防止污染后续调用）
        context.retry_hint = None
            
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
        raw_res, error_msg = self._call_llm(sys_prompt, user_prompt, node_uid, execution_context=execution_context)

        # 如果调用失败
        if error_msg:
            return LLMResult.uncertain_result(
                raw_response="",
                retry_hint=f"LLM 调用失败: {error_msg}"
            )

        # 处理 MOCK:REPAIR 特殊标记
        if raw_res == "__MOCK_REPAIR__":
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        # 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if raw_res == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
            return LLMResult.uncertain_result(
                raw_response="MAYBE_YES_MAYBE_NO_this_is_ambiguous",
                retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
            )

        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "response": raw_res,
            "raw_response": raw_res,
            "merged_intents": merged_intents
        }

        # 6. 解析结果
        return self._parse_result(raw_res, type_name, node_uid)

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

    def _evaluate_segments(self, segments: Optional[List[Any]], execution_context: IExecutionContext, param_names: Optional[Set[str]] = None) -> str:
        """
        评估结构化提示词片段。

         增强的变量替换逻辑：
        - 只有当变量名是 llm 函数参数时，才会进行变量替换
        - 其他 $变量名 会被作为普通文本处理
        """
        if not segments:
            return ""

        content_parts = []
        for segment in segments:
            if isinstance(segment, Mapping) and segment.get("_type") == "ext_ref":
                val = execution_context.resolve_value(segment)
                content_parts.append(str(val))
                continue

            if isinstance(segment, str):
                if segment.startswith("node_"):
                    val = execution_context.visit(segment)
                    if hasattr(val, '__to_prompt__'):
                        content_parts.append(val.__to_prompt__())
                    elif hasattr(val, 'to_native'):
                        content_parts.append(str(val.to_native()))
                    else:
                        content_parts.append(str(val))
                else:
                    content_parts.append(segment)
            elif hasattr(segment, 'id'):
                # IbName 节点（变量引用）
                var_name = segment.id
                
                # 只有当变量名是函数参数时才进行替换
                if param_names and var_name in param_names:
                    val = execution_context.visit(segment)
                    if hasattr(val, '__to_prompt__'):
                        content_parts.append(val.__to_prompt__())
                    elif hasattr(val, 'to_native'):
                        content_parts.append(str(val.to_native()))
                    else:
                        content_parts.append(str(val))
                else:
                    # 非函数参数的 $auto，作为普通文本处理（保持 $ 符号）
                    content_parts.append(f"${var_name}")
            else:
                content_parts.append(str(segment))
        return "".join(content_parts)

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
        # 兼容 UID 格式的 type_name (来自序列化后的 AST 节点字段)
        # 转换 'type_root.str' -> 'str', 'type_pkg.cls' -> 'pkg.cls'
        if type_name and type_name.startswith("type_"):
            type_name = type_name[5:]
            if type_name.startswith("root."):
                type_name = type_name[5:]

        meta_reg = self.registry.get_metadata_registry()
        descriptor = None
        if meta_reg:
            descriptor = meta_reg.resolve(type_name)
            # Bug #2 修复：当 type_name 含有泛型参数（如 "dict[any,any]"）时，
            # SpecRegistry 中以基础名（如 "dict"）注册，resolve 会失败。
            # 剥离泛型参数后重试，使 DictAxiom 等 Axiom 能够被正确找到。
            if descriptor is None and type_name and '[' in type_name:
                base_name = type_name.split('[')[0]
                descriptor = meta_reg.resolve(base_name)
            if descriptor:
                from_prompt_cap = meta_reg.get_from_prompt_cap(descriptor)
                if from_prompt_cap:
                    success, result = from_prompt_cap.from_prompt(raw_res, descriptor)
                    if success:
                        return LLMResult.success_result(
                            value=self.registry.box(result),
                            raw_response=raw_res
                        )
                    else:
                        return LLMResult.uncertain_result(
                            raw_response=raw_res,
                            retry_hint=result
                        )

                parser = meta_reg.get_parser_cap(descriptor)
                if parser:
                    try:
                        val = parser.parse_value(raw_res)
                        return LLMResult.success_result(
                            value=self.registry.box(val),
                            raw_response=raw_res
                        )
                    except Exception as e:
                        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response via Axiom for type '{type_name}': {str(e)}")
                        return LLMResult.uncertain_result(
                            raw_response=raw_res,
                            retry_hint=f"LLM 返回值类型转换失败：期望 {type_name}。详细: {str(e)}"
                        )

        # Axiom 路径无匹配，尝试用户自定义类 vtable 的 __from_prompt__ 方法。
        # 用户在 IBCI 类中定义 func __from_prompt__(str raw) -> (bool, any)，
        # 由此实现自定义的 LLM 输出解析逻辑。
        # 调用语义：类方法（以 IbClass 对象为 receiver，不需要 self 实例）。
        ib_class = self.registry.get_class(type_name) if type_name else None
        if ib_class:
            method = ib_class.lookup_method('__from_prompt__')
            if method:
                try:
                    raw_arg = self.registry.box(raw_res)
                    result_obj = method.call(ib_class, [raw_arg])
                    # 约定返回值为 tuple (bool, any)：
                    #   elements[0] 为成功标志（truthy/falsy），
                    #   elements[1] 为解析后的值（成功时）或错误提示（失败时）
                    if hasattr(result_obj, 'elements') and len(result_obj.elements) >= 2:
                        success_val = result_obj.elements[0]
                        parsed_val = result_obj.elements[1]
                        success_native = success_val.to_native() if hasattr(success_val, 'to_native') else bool(success_val)
                        if success_native:
                            return LLMResult.success_result(
                                value=parsed_val,
                                raw_response=raw_res
                            )
                        else:
                            hint = parsed_val.to_native() if hasattr(parsed_val, 'to_native') else str(parsed_val)
                            return LLMResult.uncertain_result(
                                raw_response=raw_res,
                                retry_hint=str(hint)
                            )
                except Exception as e:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC,
                        f"vtable __from_prompt__ failed for '{type_name}': {e}")

        return LLMResult.success_result(
            value=self.registry.box(raw_res),
            raw_response=raw_res
        )

    def execute_behavior_expression(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None, captured_intents: Optional[Any] = None) -> LLMResult:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。

        返回 LLMResult：
        - success=True, is_uncertain=False: 成功且结果确定
        - success=True, is_uncertain=True: 成功但结果不确定，需要 retry
        - success=False: 执行失败

        不再抛出 LLMUncertaintyError，所有不确定性通过 LLMResult 返回。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context

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
            from core.runtime.objects.intent_context import IbIntentContext as _IbIntentContext
            if isinstance(captured_intents, _IbIntentContext):
                # snapshot 捕获了 IbIntentContext.fork() 的完整值快照
                active_list = captured_intents.get_active_intents()
                all_intents = IntentResolver.resolve(
                    active_intents=active_list,
                    global_intents=captured_intents.get_global_intents(),
                    context=context,
                    execution_context=execution_context
                )
            else:
                # 兼容旧路径：IntentNode 链表（to_list）或已展平的列表
                active_list = captured_intents.to_list() if hasattr(captured_intents, 'to_list') else captured_intents
                all_intents = IntentResolver.resolve(
                    active_intents=active_list,
                    global_intents=context.get_global_intents(),
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
        response, error_msg = self._call_llm(sys_prompt, content, node_uid)

        # 6. 处理调用失败
        if error_msg:
            return LLMResult.uncertain_result(
                raw_response="",
                retry_hint=f"LLM 调用失败: {error_msg}"
            )

        # 6.1 处理 MOCK:REPAIR 特殊标记
        if response == "__MOCK_REPAIR__":
            return LLMResult.uncertain_result(
                raw_response="__MOCK_REPAIR__",
                retry_hint="MOCK:REPAIR - 模拟 LLM 返回不确定结果，请重试"
            )

        # 6.2 处理 MOCK:FAIL 特殊标记 (LLM 明确拒绝/不确定)
        if response == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
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
            "active_intents": [i.content if hasattr(i, 'content') else str(i) for i in active_list] if 'active_list' in dir() else [],
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
        """
        if not isinstance(behavior, IbBehavior):
             return LLMResult.success_result(value=behavior)

        if behavior._cache is not None:
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
        if execution_context is not None:
            execution_context.runtime_context.set_last_llm_result(result)
        # 使用 is not None 判断，避免将 IbBool(False)/IbInteger(0) 等假值误判为空
        if result is not None and result.value is not None:
            return result.value
        return self.registry.get_none()

    def _call_llm(self, sys_prompt: str, user_prompt: str, node_uid: str, execution_context: Optional[IExecutionContext] = None) -> Tuple[Optional[str], Optional[str]]:
        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "Calling LLM")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "System Prompt:", data=sys_prompt)
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt:", data=user_prompt)

        context = execution_context.runtime_context if execution_context else None
        retry_hint = context.retry_hint if context else None

        if self.llm_callback:
            try:
                if retry_hint:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting retry hint: {retry_hint}")
                    self.llm_callback.set_retry_hint(retry_hint)

                response = self.llm_callback(sys_prompt, user_prompt)
                self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "LLM Response received.")
                self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "LLM Raw Response:", data=response)
                return response, None
            except Exception as e:
                self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"LLM call failed: {e}")
                print(f"\n[AI 拦截器] 发现 AI 服务连接异常: {str(e)}")
                return None, str(e)

        # 如果没有回调，说明配置缺失，抛出错误
        raise InterpreterError(
            "LLM 运行配置缺失：未配置有效的 LLM 调用接口。\n"
            "请确保已导入 'ai' 模块并正确调用了 'ai.set_config'。",
            node_uid,
            error_code=RUN_LLM_ERROR
        )


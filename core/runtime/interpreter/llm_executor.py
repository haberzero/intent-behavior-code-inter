import re
import json
from types import SimpleNamespace
from typing import Any, List, Optional, Dict, Union, Callable, Mapping, TYPE_CHECKING
from core.runtime.interfaces import LLMExecutor, RuntimeContext, ServiceContext, InterOp
from core.foundation.interfaces import ILLMProvider, IssueTracker, IExecutionContext

from core.domain.issue import InterpreterError, LLMUncertaintyError
from core.foundation.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.builtins import IbBehavior
from core.runtime.objects.intent import IbIntent
from core.domain.intent_logic import IntentMode, IntentRole
from core.domain.intent_resolver import IntentResolver
from core.foundation.registry import Registry

class LLMExecutorImpl:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
    """
    def __init__(self, 
                 registry: Registry, 
                 interop: InterOp,
                 issue_tracker: IssueTracker,
                 llm_callback: Optional[ILLMProvider] = None,
                 debugger: Any = None):
        """
        registry: 注册表 (用于对象装箱)
        interop: 互操作接口 (用于获取 ai 模块配置)
        issue_tracker: 错误追踪器
        llm_callback: 实际的 LLM 调用接口 (满足 ILLMProvider 协议)。
        """
        self.registry = registry
        self.interop = interop
        self.issue_tracker = issue_tracker
        self.llm_callback = llm_callback
        self.debugger = debugger or core_debugger
        
        # retry_hint 现状保存在 LLMExecutorImpl 中，为了兼容，
        # 我们会在调用 Provider 时同步同步它
        self.retry_hint: Optional[str] = None
        self.last_call_info: Mapping[str, Any] = {} # 记录最后一次 LLM 调用信息
        self._expected_type_stack: List[str] = []

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

    def execute_llm_function(self, node_uid: str, execution_context: IExecutionContext) -> IbObject:
        """
        [职责解耦] 仅处理 LLM 推理过程。
        作用域管理和参数绑定已由 IbLLMFunction.call 完成。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context
        
        # 此时 context 已经是进入过函数作用域的状态
        name = node_data.get("name", "unknown")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{name}'")

        # 1. 提取并评估结构化 Prompt
        sys_prompt = self._evaluate_segments(node_data.get("sys_prompt"), execution_context)
        user_prompt = self._evaluate_segments(node_data.get("user_prompt"), execution_context)
        
        # 2. 注入意图增强 (三层架构合并)
        merged_intents = self._merge_intents(node_uid, execution_context)
        if merged_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
            sys_prompt += intent_block
            
        # 3. 处理返回类型提示注入
        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = execution_context.get_node_data(returns_uid)
            if returns_data and returns_data["_type"] == "IbName":
                type_name = returns_data.get("id", "str")

        ai_module = self.interop.get_package("ai")
        if ai_module and hasattr(ai_module, "get_return_type_prompt"):
            type_prompt = ai_module.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        # 4. 调用底层模型
        raw_res = self._call_llm(sys_prompt, user_prompt, node_uid)
        
        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "raw_response": raw_res
        }
        
        # 5. 解析结果
        return self._parse_result(raw_res, type_name, node_uid)


    def _merge_intents(self, node_uid: str, execution_context: IExecutionContext, captured_intents: Optional[List[Any]] = None) -> List[str]:
        """合并各层级的意图 (使用 IntentResolver 消解冲突)"""
        context = execution_context.runtime_context
        
        # 1. 静态意图 (AST)
        node_data = execution_context.get_node_data(node_uid)
        intent_uid = node_data.get("intent")
        static_intent = None
        if intent_uid:
            intent_data = execution_context.get_node_data(intent_uid)
            static_intent = IbIntent(
                ib_class=self.registry.get_class("Intent"),
                content=intent_data.get('content', '') if intent_data else '',
                segments=intent_data.get('segments', []) if intent_data else [],
                mode=IntentMode.from_str(intent_data.get('mode', '+')) if intent_data else IntentMode.APPEND,
                tag=intent_data.get('tag') if intent_data else None,
                role=IntentRole.SMEAR,
                source_uid=intent_uid
            )

        # 2. 动态意图与全局意图
        active_intents = context.get_active_intents()
        global_intents = context.get_global_intents()
        
        # 3. 显式捕获意图
        cap_intents = captured_intents or []
        
        # 4. 创建适配器以满足 IbIntent.resolve_content 对 evaluator 的要求
        class EvaluatorShim:
            def __init__(self, executor, exec_ctx):
                self.executor = executor
                self.exec_ctx = exec_ctx
            def _evaluate_segments(self, segments, context):
                return self.executor._evaluate_segments(segments, self.exec_ctx)

        # 5. 调用消解器
        return IntentResolver.resolve(
            active_intents=active_intents + cap_intents,
            global_intents=global_intents,
            call_intent=static_intent,
            context=context,
            evaluator=EvaluatorShim(self, execution_context)
        )

    def _resolve_intent_content(self, intent_uid: Optional[str], execution_context: IExecutionContext) -> Optional[str]:
        if not intent_uid:
            return None
        
        val = execution_context.visit(intent_uid)
        if hasattr(val, 'content'):
            return val.content
        return str(val)

    def _resolve_intent_content_obj(self, intent: Any, context: RuntimeContext) -> str:
        """已废弃：直接使用 IbIntent.resolve_content"""
        if isinstance(intent, IbIntent):
            return intent.resolve_content(context, self)
        # Fallback for old types
        return self._evaluate_segments(getattr(intent, 'segments', []), context).strip()

    def _unique_merge(self, *lists: List[str]) -> List[str]:
        result = []
        seen = set()
        for l in lists:
            for item in l:
                if item and item not in seen:
                    result.append(item)
                    seen.add(item)
        return result

    def _evaluate_segments(self, segments: Optional[List[Any]], execution_context: IExecutionContext) -> str:
        """评估结构化提示词片段"""
        if not segments:
            return ""
        
        content_parts = []
        for segment in segments:
            # [IES 2.2 Security Update] 处理外部资产引用
            if isinstance(segment, Mapping) and segment.get("_type") == "ext_ref":
                # 注意：_resolve_value 依然在 Interpreter 内部，但我们可以通过 IExecutionContext 间接获取
                # 如果 IExecutionContext 不提供，我们需要在 Interpreter 层预处理
                # 目前我们假设 IExecutionContext 暂时不提供 _resolve_value，但我们可以通过 visit 节点来获取常量
                pass

            if isinstance(segment, str):
                if segment.startswith("node_"):
                    # 这是一个节点 UID
                    val = execution_context.visit(segment)
                    if hasattr(val, '__to_prompt__'):
                        content_parts.append(val.__to_prompt__())
                    elif hasattr(val, 'to_native'):
                        content_parts.append(str(val.to_native()))
                    else:
                        content_parts.append(str(val))
                else:
                    content_parts.append(segment)
            else:
                content_parts.append(str(segment))
        return "".join(content_parts)

    def _parse_result(self, raw_res: str, type_name: str, node_uid: str) -> IbObject:
        # [Axiom-Driven] 使用公理系统进行解析 (Instance-based)
        axiom = None
        meta_reg = self.registry.get_metadata_registry()
        if meta_reg:
            axiom_reg = meta_reg.get_axiom_registry()
            if axiom_reg:
                axiom = axiom_reg.get_axiom(type_name)
                
                if not axiom:
                        # 处理泛型 (降级到基础类型公理)
                    if type_name.startswith("list"):
                        axiom = axiom_reg.get_axiom("list")
                    elif type_name.startswith("dict"):
                        axiom = axiom_reg.get_axiom("dict")

        if axiom:
            parser = axiom.get_parser_capability()
            if parser:
                try:
                    val = parser.parse_value(raw_res)
                    return self.registry.box(val)
                except Exception as e:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response via Axiom '{type_name}': {str(e)}")
                    raise LLMUncertaintyError(
                        f"LLM 返回值类型转换失败：期望 {type_name}，但解析出错。\n原始返回: {raw_res}\n详细错误: {str(e)}",
                        node_uid,
                        raw_response=raw_res
                    )

        # Fallback (Default to string boxing if no axiom or no parser capability)
        return self.registry.box(raw_res)

    def execute_behavior_expression(self, node_uid: str, execution_context: IExecutionContext, captured_intents: Optional[List[Any]] = None) -> IbObject:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context
        
        # 0. 准备环境
        ai_module = self.interop.get_package("ai")

        # 1. 评估段式插值
        content = self._evaluate_segments(node_data.get("segments"), execution_context)
        
        # 2. 收集与合并意图
        all_intents = []
        auto_intent = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_intent = ai_module._config.get("auto_intent_injection", True)
        
        if auto_intent:
            all_intents = self._merge_intents(node_uid, execution_context, captured_intents=captured_intents)
        elif node_data.get("intent"):
            all_intents = [self._resolve_intent_content(node_data.get("intent"), execution_context)]
            
        # 3. 确定场景与提示词
        # 核心：使用 side_tables 中的 node_scenes
        scene_name = execution_context.get_side_table("node_scenes", node_uid) or "general"
        sys_prompt = "你是一个意图行为代码执行器。"
        
        current_retry_hint = self.retry_hint
        if ai_module:
            if not current_retry_hint and hasattr(ai_module, "_retry_hint"):
                current_retry_hint = ai_module._retry_hint
            
            if hasattr(ai_module, "get_scene_prompt"):
                sys_prompt = ai_module.get_scene_prompt(scene_name)
        
        if current_retry_hint:
            sys_prompt += f"\n\n注意：上一次执行失败，请参考以下提示进行重试：\n{current_retry_hint}"

        # 4. 构造意图增强块
        if all_intents:
            intent_block = "\n当前上下文意图：\n" + "\n".join(f"- {i}" for i in all_intents)
            sys_prompt += intent_block

        # 5. 调用底层模型
        response = self._call_llm(sys_prompt, content, node_uid)
        
        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": content,
            "raw_response": response
        }

        # 6. 处理返回类型
        if scene_name in ("decision", "choice"):
            decision_map = execution_context.get_side_table("decision_maps", node_uid) or {}
            if decision_map:
                clean_res = response.strip().lower()
                # 模糊匹配
                for k in decision_map:
                    if k.lower() in clean_res:
                        self.retry_hint = None
                        return self.registry.box(decision_map[k])
                
                if clean_res in decision_map:
                    self.retry_hint = None
                    return self.registry.box(decision_map[clean_res])
                
                raise LLMUncertaintyError(f"LLM decision format error: {response}", node_uid, raw_response=response)

        self.retry_hint = None
        return self.registry.box(response)


    def execute_behavior_object(self, behavior: IbObject, execution_context: IExecutionContext) -> IbObject:
        """
        [IES 2.0 Architectural Update] 执行一个被动行为对象。
        """
        if not isinstance(behavior, IbBehavior):
             return behavior

        if behavior._cache is not None:
            return behavior._cache

        context = execution_context.runtime_context
        # 1. 恢复捕获的意图栈
        old_intents = context.intent_stack
        context.intent_stack = list(behavior.captured_intents)

        # 2. 处理预期类型注入
        type_pushed = False
        if behavior.expected_type:
            self.push_expected_type(behavior.expected_type)
            type_pushed = True

        try:
            # 3. 递归调用 execute_behavior_expression
            res = self.execute_behavior_expression(
                behavior.node, execution_context, captured_intents=behavior.captured_intents
            )
            behavior._cache = res
            return res
        finally:
            # 4. 环境恢复
            context.intent_stack = old_intents
            if type_pushed:
                self.pop_expected_type()

    def _call_llm(self, sys_prompt: str, user_prompt: str, node_uid: str, scene: str = "general") -> str:
        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Calling LLM (Scene: {scene})")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "System Prompt:", data=sys_prompt)
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt:", data=user_prompt)
        
        if self.llm_callback:
            # 同步同步重试提示词
            if self.retry_hint:
                self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting retry hint: {self.retry_hint}")
                self.llm_callback.set_retry_hint(self.retry_hint)
            
            # 调用 Provider
            response = self.llm_callback(sys_prompt, user_prompt, scene=scene)
            self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "LLM Response received.")
            self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "LLM Raw Response:", data=response)
            return response
        
        # 如果没有回调，说明配置缺失，抛出错误
        raise InterpreterError(
            "LLM 运行配置缺失：未配置有效的 LLM 调用接口。\n"
            "请确保已导入 'ai' 模块并正确调用了 'ai.set_config'。",
            node_uid,
            error_code=RUN_LLM_ERROR
        )


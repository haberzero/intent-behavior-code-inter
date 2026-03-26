import re
import json
from types import SimpleNamespace
from typing import Any, List, Optional, Dict, Union, Callable, Mapping, TYPE_CHECKING
from core.runtime.interfaces import LLMExecutor, RuntimeContext, ServiceContext, InterOp, IIbBehavior, IIbIntent, Registry, IExecutionContext
from core.base.interfaces import ILLMProvider, IssueTracker

from core.kernel.issue import InterpreterError, LLMUncertaintyError
from core.base.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent import IbIntent

from core.kernel.intent_logic import IntentMode, IntentRole
from core.kernel.intent_resolver import IntentResolver
from core.kernel.registry import KernelRegistry

class LLMExecutorImpl:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
    [IES 2.1 Refactor] 采用上下文注入模式，支持延迟水化以消除解释器内部的属性补丁。
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
        """[IES 2.1] 水化依赖，由解释器在服务准备就绪后调用"""
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
        # [IES 2.2] 优先从能力注册中心获取 Provider (能力名: llm_provider)
        if self.service_context.capability_registry:
            provider = self.service_context.capability_registry.get("llm_provider")
            if provider:
                return provider

        # 回退到从 ai 模块获取 (兼容旧模式)
        ai_module = self.interop.get_package("ai")
        if not ai_module:
            return None
            
        # 1. 优先尝试显式获取 Provider 接口 (用于复杂插件代理)
        if hasattr(ai_module, "get_llm_provider"):
            return ai_module.get_llm_provider()
            
        # 2. 其次检查模块实现是否直接实现了 ILLMProvider (用于核心 AI 插件)
        if isinstance(ai_module, ILLMProvider):
            return ai_module
            
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

    def execute_llm_function(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None) -> IbObject:
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
        
        # 2. 注入意图增强 (被动消费已消解的现场)
        # 呼叫级意图已由 Caller 通过参数传递
        merged_intents = context.get_resolved_prompt_intents(execution_context, call_intent=call_intent)
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

        # [IES 2.2] 从 LLM Provider 获取返回类型提示
        if self.llm_callback and hasattr(self.llm_callback, 'get_return_type_prompt'):
            type_prompt = self.llm_callback.get_return_type_prompt(type_name)
            if type_prompt:
                sys_prompt += f"\n\n{type_prompt}"

        # 4. 调用底层模型
        raw_res = self._call_llm(sys_prompt, user_prompt, node_uid, execution_context=execution_context)
        
        # 记录最后一次调用信息 (兼容 IES 2.0/2.1 命名)
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": user_prompt,
            "response": raw_res,
            "raw_response": raw_res
        }
        
        # 5. 解析结果
        return self._parse_result(raw_res, type_name, node_uid)


    def _evaluate_segments(self, segments: Optional[List[Any]], execution_context: IExecutionContext) -> str:
        """评估结构化提示词片段"""
        if not segments:
            return ""
        
        content_parts = []
        for segment in segments:
            # [IES 2.2 Security Update] 处理外部资产引用
            if isinstance(segment, Mapping) and segment.get("_type") == "ext_ref":
                # 注意：目前由 Interpreter 在更高层处理，此处仅作为占位
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
        # [IES 2.1 Axiom-Driven] 直接通过描述符获取公理能力，彻底消除名称硬编码与降级逻辑
        meta_reg = self.registry.get_metadata_registry()
        if meta_reg:
            descriptor = meta_reg.resolve(type_name)
            if descriptor and descriptor._axiom:
                parser = descriptor._axiom.get_parser_capability()
                if parser:
                    try:
                        val = parser.parse_value(raw_res)
                        return self.registry.box(val)
                    except Exception as e:
                        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response via Axiom for type '{type_name}': {str(e)}")
                        raise LLMUncertaintyError(
                            f"LLM 返回值类型转换失败：期望 {type_name}，但解析出错。\n原始返回: {raw_res}\n详细错误: {str(e)}",
                            node_uid,
                            raw_response=raw_res
                        )

        # Fallback (Default to string boxing if no descriptor, axiom or no parser capability)
        return self.registry.box(raw_res)

    def execute_behavior_expression(self, node_uid: str, execution_context: IExecutionContext, call_intent: Optional[IbIntent] = None) -> IbObject:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。
        """
        node_data = execution_context.get_node_data(node_uid)
        context = execution_context.runtime_context
        
        # 0. 准备环境
        ai_module = self.interop.get_package("ai")

        # 1. 评估段式插值
        content = self._evaluate_segments(node_data.get("segments"), execution_context)
        
        # 2. 收集与合并意图 (被动消费已消解的现场)
        auto_intent = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_intent = ai_module._config.get("auto_intent_injection", True)
        
        if not auto_intent:
            # 如果关闭了自动注入，仅保留当前节点的意图 (如果有)
            if call_intent:
                # 强制覆盖模式：仅返回该意图
                return self.registry.box(call_intent.resolve_content(context, execution_context))

        # [IES 2.1] 获取消解后的最终列表
        all_intents = context.get_resolved_prompt_intents(execution_context, call_intent=call_intent)
        # 核心：使用 side_tables 中的 node_scenes
        scene_val = execution_context.get_side_table("node_scenes", node_uid)
        scene_name = str(scene_val).lower() if scene_val else "general"
        
        sys_prompt = "你是一个意图行为代码执行器。"
        
        current_retry_hint = context.retry_hint
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
        response = self._call_llm(sys_prompt, content, node_uid, scene=scene_name)
        
        # 记录最后一次调用信息 (兼容 IES 2.0/2.1 命名)
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": content,
            "response": response,
            "raw_response": response,
            "scene": scene_name
        }

        # 6. 处理返回类型
        # [IES 2.1 Unified Decision] 统一处理分支、循环和决策场景的模糊判定
        if any(keyword in scene_name for keyword in ("decision", "choice", "branch", "loop")):
            # 1. 优先尝试从侧表获取节点特有的决策映射
            decision_map = execution_context.get_side_table("decision_maps", node_uid)
            
            # 2. 如果侧表没有，则尝试从 AI 插件获取该场景的全局默认映射
            if not decision_map and ai_module and hasattr(ai_module, "get_decision_map"):
                decision_map = ai_module.get_decision_map()
            
            if decision_map:
                clean_res = response.strip().lower()
                
                # 1. 优先尝试精确匹配
                if clean_res in decision_map:
                    context.retry_hint = None
                    return self.registry.box(decision_map[clean_res])
                
                # 2. 尝试带边界的关键词匹配 (防止 "maybe_yes" 匹配到 "yes")
                for k in decision_map:
                    pattern = rf"\b{re.escape(k.lower())}\b"
                    if re.search(pattern, clean_res):
                        context.retry_hint = None
                        return self.registry.box(decision_map[k])
                
                # [IES 2.1 Enforcement] 如果没有匹配到任何项，说明 AI 的回复是模糊的，必须抛出异常
                raise LLMUncertaintyError(
                    f"LLM 决策格式错误或回复模糊：期望匹配 {list(decision_map.keys())} 之一，但 AI 返回了: {response}", 
                    node_uid, 
                    raw_response=response
                )

        context.retry_hint = None
        return self.registry.box(response)


    def execute_behavior_object(self, behavior: IbObject, execution_context: IExecutionContext) -> IbObject:
        """
        [IES 2.0 Architectural Update] 执行一个被动行为对象。
        环境（意图栈）已由 Interpreter/Handler 在调用前准备就绪。
        """
        if not isinstance(behavior, IIbBehavior):
             return behavior

        if behavior._cache is not None:
            return behavior._cache

        # 1. 处理预期类型注入
        type_pushed = False
        if behavior.expected_type:
            self.push_expected_type(behavior.expected_type)
            type_pushed = True

        try:
            # 2. 递归调用 execute_behavior_expression (环境已由 Caller 准备)
            res = self.execute_behavior_expression(behavior.node, execution_context)
            behavior._cache = res
            return res
        finally:
            # 3. 环境恢复 (类型栈)
            if type_pushed:
                self.pop_expected_type()

    def _call_llm(self, sys_prompt: str, user_prompt: str, node_uid: str, scene: str = "general", execution_context: Optional[IExecutionContext] = None) -> str:
        self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Calling LLM (Scene: {scene})")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "System Prompt:", data=sys_prompt)
        self.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt:", data=user_prompt)
        
        context = execution_context.runtime_context if execution_context else None
        retry_hint = context.retry_hint if context else None

        if self.llm_callback:
            # 同步同步重试提示词
            if retry_hint:
                self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting retry hint: {retry_hint}")
                self.llm_callback.set_retry_hint(retry_hint)
            
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


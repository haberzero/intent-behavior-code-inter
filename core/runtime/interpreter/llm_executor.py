import re
import json
from types import SimpleNamespace
from typing import Any, List, Optional, Dict, Union, Callable, Mapping
from core.runtime.interfaces import LLMExecutor, RuntimeContext, ServiceContext
from core.domain.issue import InterpreterError, LLMUncertaintyError
from core.foundation.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.foundation.interfaces import ILLMProvider
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent import IbIntent
from core.domain.intent_logic import IntentMode, IntentRole
from core.domain.intent_resolver import IntentResolver
from core.foundation.registry import Registry

class LLMExecutorImpl:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
    """
    def __init__(self, service_context: Optional[ServiceContext] = None, llm_callback: Optional[ILLMProvider] = None):
        """
        service_context: 注入容器
        llm_callback: 实际的 LLM 调用接口 (满足 ILLMProvider 协议)。
        """
        self.service_context = service_context
        self.llm_callback = llm_callback
        # retry_hint 现状保存在 LLMExecutorImpl 中，为了兼容，
        # 我们会在调用 Provider 时同步同步它
        self.retry_hint: Optional[str] = None
        self.last_call_info: Mapping[str, Any] = {} # 记录最后一次 LLM 调用信息
        self._expected_type_stack: List[str] = []

    @property
    def debugger(self):
        if self.service_context and self.service_context.debugger:
            return self.service_context.debugger
        return core_debugger

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

    def execute_llm_function(self, node_uid: str, context: RuntimeContext) -> IbObject:
        """
        [职责解耦] 仅处理 LLM 推理过程。
        作用域管理和参数绑定已由 IbLLMFunction.call 完成。
        """
        interpreter = self.service_context.interpreter
        node_data = interpreter.get_node_data(node_uid)
        
        # 此时 context 已经是进入过函数作用域的状态
        name = node_data.get("name", "unknown")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{name}'")

        # 1. 提取并评估结构化 Prompt
        sys_prompt = self._evaluate_segments(node_data.get("sys_prompt"), context)
        user_prompt = self._evaluate_segments(node_data.get("user_prompt"), context)
        
        # 2. 注入意图增强 (三层架构合并)
        merged_intents = self._merge_intents(node_uid, context)
        if merged_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
            sys_prompt += intent_block
            
        # 3. 处理返回类型提示注入
        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = interpreter.get_node_data(returns_uid)
            if returns_data and returns_data["_type"] == "IbName":
                type_name = returns_data.get("id", "str")

        ai_module = self.service_context.interop.get_package("ai")
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
            "response": raw_res,
            "type": "callable",
            "name": name
        }
        
        # 5. 结果解析
        return self._parse_result(raw_res, type_name, node_uid)


    def _merge_intents(self, node_uid: Optional[str], context: RuntimeContext, captured_intents: Optional[List[Any]] = None) -> List[str]:
        """
        合并 Global, Block, Smear, Call 三层意图。
        node_uid: 当前正在执行的节点 UID，用于查找侧表中的涂抹意图。
        """
        interpreter = self.service_context.interpreter
        
        # 1. 基础收集：执行栈意图
        global_intents = context.get_global_intents()
        raw_active = captured_intents if captured_intents is not None else context.get_active_intents()
        
        active_intents = list(raw_active) if not hasattr(raw_active, 'to_list') else raw_active.to_list()
            
        # 2. 收集侧表涂抹意图 (Smearing Intents)
        # 按照 IES 2.0 协议，侧表意图比栈意图更具体（内层）
        if node_uid:
            smear_uids = interpreter.get_side_table("node_intents", node_uid)
            if smear_uids:
                if isinstance(smear_uids, str): smear_uids = [smear_uids]
                for uid in smear_uids:
                    intent = self._create_intent_from_uid(uid)
                    if intent:
                        active_intents.append(intent)

        # 3. 处理 Call 层级意图 (最高优先级)
        # 注意：这里的 node_uid 如果是 IbBehaviorExpr，它本身可能持有一个直接的 intent 关联
        call_intent = None
        node_data = interpreter.get_node_data(node_uid) if node_uid else {}
        call_intent_uid = node_data.get("intent")
        if call_intent_uid:
            call_intent = self._create_intent_from_uid(call_intent_uid, role=IntentRole.CALL)
            
        # 4. 调用统一的 Resolver
        final_list = IntentResolver.resolve(
            active_intents=active_intents,
            global_intents=global_intents,
            call_intent=call_intent,
            context=context,
            evaluator=self
        )
        
        # 5. 注入循环上下文
        loop_context = context.get_loop_context()
        if loop_context:
            index, total = loop_context["index"], loop_context["total"]
            final_list.append(f"[循环进度感知: 当前正在处理第 {index + 1} 个元素，总计 {total} 个]")
            
        return final_list

    def _create_intent_from_uid(self, intent_uid: str, role: Any = None) -> Optional[IbIntent]:
        """从 UID 创建 IbIntent 对象"""
        interpreter = self.service_context.interpreter
        try:
            intent_data = interpreter.get_node_data(intent_uid)
        except:
            return None
            
        if not intent_data: return None
        
        return IbIntent(
            ib_class=self.service_context.registry.get_class("Intent"),
            content=intent_data.get('content', ''),
            mode=IntentMode.from_str(intent_data.get('mode', '+')),
            tag=intent_data.get('tag'),
            segments=intent_data.get('segments', []),
            role=role or IntentRole.SMEAR,
            source_uid=intent_uid
        )

    def _resolve_intent_content(self, intent_uid: str, context: RuntimeContext) -> str:
        """从 UID 解析意图内容 (Helper)"""
        # 复用 IbIntent 逻辑
        interpreter = self.service_context.interpreter
        intent_data = interpreter.get_node_data(intent_uid)
        intent = IbIntent(
            ib_class=self.service_context.registry.get_class("Intent"),
            content=intent_data.get("content", ""),
            mode=IntentMode.from_str(intent_data.get("mode", "+")),
            tag=intent_data.get("tag"),
            segments=intent_data.get("segments", []),
            role=IntentRole.BLOCK
        )
        return intent.resolve_content(context, self)

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

    def _evaluate_segments(self, segments: Optional[List[Any]], context: RuntimeContext) -> str:
        """评估结构化提示词片段"""
        if not segments:
            return ""
        
        from core.runtime.objects.kernel import IbObject
        content_parts = []
        for segment in segments:
            # [IES 2.2 Security Update] 处理外部资产引用
            if isinstance(segment, Mapping) and segment.get("_type") == "ext_ref":
                interpreter = self.service_context.interpreter
                if interpreter and hasattr(interpreter, "_resolve_value"):
                    segment = interpreter._resolve_value(segment)

            if isinstance(segment, str):
                if segment.startswith("node_"):
                    # 这是一个节点 UID
                    if self.service_context and self.service_context.interpreter:
                        val = self.service_context.interpreter.visit(segment)
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
        if self.service_context and self.service_context.registry:
            meta_reg = self.service_context.registry.get_metadata_registry()
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
                    return self.service_context.registry.box(val)
                except Exception as e:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response via Axiom '{type_name}': {str(e)}")
                    raise LLMUncertaintyError(
                        f"LLM 返回值类型转换失败：期望 {type_name}，但解析出错。\n原始返回: {raw_res}\n详细错误: {str(e)}",
                        node_uid,
                        raw_response=raw_res
                    )

        # Fallback (Default to string boxing if no axiom or no parser capability)
        return self.service_context.registry.box(raw_res)

    def execute_behavior_expression(self, node_uid: str, context: RuntimeContext, captured_intents: Optional[List[Any]] = None) -> IbObject:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。
        """
        interpreter = self.service_context.interpreter
        node_data = interpreter.get_node_data(node_uid)
        
        # 0. 准备环境
        ai_module = self.service_context.interop.get_package("ai")

        # 1. 评估段式插值
        content = self._evaluate_segments(node_data.get("segments"), context)
        
        # 2. 收集与合并意图
        all_intents = []
        auto_intent = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_intent = ai_module._config.get("auto_intent_injection", True)
        
        if auto_intent:
            all_intents = self._merge_intents(node_uid, context, captured_intents=captured_intents)
        elif node_data.get("intent"):
            all_intents = [self._resolve_intent_content(node_data.get("intent"), context)]
            
        # 3. 确定场景与提示词
        # 核心：使用 side_tables 中的 node_scenes
        scene_name = interpreter.get_side_table("node_scenes", node_uid) or "general"
        sys_prompt = "你是一个意图行为代码执行器。"
        
        current_retry_hint = self.retry_hint
        if ai_module:
            if not current_retry_hint and hasattr(ai_module, "_retry_hint"):
                current_retry_hint = ai_module._retry_hint
            
        if ai_module and hasattr(ai_module, "get_scene_prompt"):
            scene_prompt = ai_module.get_scene_prompt(scene_name.lower())
            if scene_prompt:
                sys_prompt = scene_prompt

        # 注入预期类型约束
        if self._expected_type_stack:
            injected_type = self._expected_type_stack[-1]
            # [Refactor Phase 3] 移除 behavior 过滤，因 BehaviorType.prompt_name 已修正为 'str'
            if injected_type not in ("var", "callable", "Any"):
                # 优先使用 ai 模块定义的针对特定类型的 Prompt
                type_prompt = None
                if ai_module and hasattr(ai_module, "get_return_type_prompt"):
                    type_prompt = ai_module.get_return_type_prompt(injected_type)
                
                if type_prompt:
                    sys_prompt += f"\n\n{type_prompt}"
                else:
                    # 回退到通用的类型声明
                    sys_prompt += f"\n预期返回类型：{injected_type}。请确保输出内容可以直接解析或转换为该类型。"
        
        if all_intents:
            sys_prompt += "\n当前执行意图约束：\n" + "\n".join(f"- {i}" for i in all_intents)
            
        if current_retry_hint:
            sys_prompt += f"\n\n注意：这是重试请求。之前的回答不符合要求，请参考此修正提示：{current_retry_hint}"
            
        # 4. 执行
        response = self._call_llm(sys_prompt, content, node_uid, scene=scene_name.lower())
        
        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": content,
            "response": response,
            "scene": scene_name.lower()
        }
            
        # 5. 严格场景校验 (BRANCH/LOOP)
        if scene_name.upper() in ("BRANCH", "LOOP"):
            clean_res = response.strip().lower()
            decision_map = {"1": 1, "0": 0, "true": 1, "false": 0, "yes": 1, "no": 0}
            if clean_res in decision_map:
                self.retry_hint = None
                return self.service_context.registry.box(decision_map[clean_res])
            
            raise LLMUncertaintyError(f"LLM decision format error: {response}", node_uid, raw_response=response)

        self.retry_hint = None
        return self.service_context.registry.box(response)


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

class intent_scoped:
    """管理意图作用域的上下文管理器装饰器"""
    def __init__(self, service_context: ServiceContext, intent_uid: Optional[str]):
        self.service_context = service_context
        self.intent_uid = intent_uid

    def __call__(self, action: Callable):
        if not self.intent_uid:
            return action()
            
        interpreter = self.service_context.interpreter
        intent_data = interpreter.get_node_data(self.intent_uid)
        
        # 使用 IbIntent 替代 SimpleNamespace
        intent = IbIntent(
            ib_class=self.service_context.registry.get_class("Intent"),
            content=intent_data.get('content', '') if intent_data else '',
            mode=IntentMode.from_str(intent_data.get('mode', '+')) if intent_data else IntentMode.APPEND,
            tag=intent_data.get('tag') if intent_data else None,
            segments=intent_data.get('segments', []) if intent_data else [],
            role=IntentRole.BLOCK,
            source_uid=self.intent_uid
        )
        
        self.service_context.runtime_context.push_intent(intent)
        try:
            return action()
        finally:
            self.service_context.runtime_context.pop_intent()

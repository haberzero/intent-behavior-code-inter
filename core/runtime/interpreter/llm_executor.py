import re
import json
from types import SimpleNamespace
from typing import Any, List, Optional, Dict, Union, Callable
from core.foundation.interfaces import LLMExecutor, RuntimeContext, ServiceContext
from core.domain.issue import InterpreterError, LLMUncertaintyError
from core.support.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.foundation.capabilities import ILLMProvider
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.foundation.kernel import IbObject
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
        self.last_call_info: Dict[str, Any] = {} # 记录最后一次 LLM 调用信息
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
    def get_last_call_info(self) -> Dict[str, Any]:
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
        from core.foundation.registry import Registry
        
        interpreter = self.service_context.interpreter
        node_data = interpreter.node_pool.get(node_uid, {})
        
        # 此时 context 已经是进入过函数作用域的状态
        name = node_data.get("name", "unknown")
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{name}'")

        # 1. 提取并评估结构化 Prompt
        sys_prompt = self._evaluate_segments(node_data.get("sys_prompt"), context)
        user_prompt = self._evaluate_segments(node_data.get("user_prompt"), context)
        
        # 2. 注入意图增强 (三层架构合并)
        merged_intents = self._merge_intents(None, context)
        if merged_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
            sys_prompt += intent_block
            
        # 3. 处理返回类型提示注入
        type_name = "str"
        returns_uid = node_data.get("returns")
        if returns_uid:
            returns_data = interpreter.node_pool.get(returns_uid)
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


    def _merge_intents(self, call_intent_uid: Optional[str], context: RuntimeContext, captured_intents: Optional[List[Any]] = None) -> List[str]:
        """
        合并 Global, Block, Call 三层意图。
        """
        # 1. 基础收集
        global_intents = context.get_global_intents()
        active_intents = context.get_active_intents()
        
        # 2. 处理模式 (Mode) 逻辑
        resolved_block_intents = []
        is_exclusive = False
        for i in reversed(active_intents):
            content = self._resolve_intent_content_obj(i, context)
            if i.mode == "override":
                resolved_block_intents.insert(0, content)
                is_exclusive = True
                break
            resolved_block_intents.insert(0, content)
            
        final_list = []
        if not is_exclusive:
            final_list.extend(global_intents)
        final_list.extend(resolved_block_intents)
        
        # 3. 处理 Call 层级
        if call_intent_uid:
            interpreter = self.service_context.interpreter
            call_intent_data = interpreter.node_pool.get(call_intent_uid, {})
            mode = call_intent_data.get("mode", "append")
            content = self._resolve_intent_content(call_intent_uid, context)
            if mode == "override":
                return [content]
            elif mode == "remove":
                if content in final_list: final_list.remove(content)
            else:
                if content not in final_list: final_list.append(content)
        
        # 4. 注入循环上下文
        loop_context = context.get_loop_context()
        if loop_context:
            index, total = loop_context["index"], loop_context["total"]
            final_list.append(f"[循环进度感知: 当前正在处理第 {index + 1} 个元素，总计 {total} 个]")
            
        return self._unique_merge(final_list)

    def _resolve_intent_content(self, intent_uid: str, context: RuntimeContext) -> str:
        """从 UID 解析意图内容"""
        interpreter = self.service_context.interpreter
        intent_data = interpreter.node_pool.get(intent_uid, {})
        segments = intent_data.get("segments")
        if segments:
            return self._evaluate_segments(segments, context).strip()
        return intent_data.get("content", "").strip()

    def _resolve_intent_content_obj(self, intent: Any, context: RuntimeContext) -> str:
        """从 IntentInfo 对象或字典解析"""
        if isinstance(intent, dict):
            segments = intent.get('segments')
            if segments:
                return self._evaluate_segments(segments, context).strip()
            return intent.get('content', '').strip()
            
        if hasattr(intent, 'segments') and intent.segments:
            return self._evaluate_segments(intent.segments, context).strip()
        return intent.content.strip()

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
        
        from core.foundation.kernel import IbObject
        content_parts = []
        for segment in segments:
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
        clean_res = raw_res.strip()
        
        if type_name == "str":
            return Registry.box(raw_res)
        
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Parsing LLM response to type '{type_name}'")

        try:
            if type_name == "int":
                match = re.search(r'-?\d+', clean_res)
                if match:
                    val = int(match.group())
                    return Registry.box(val)
                raise ValueError(f"No integer found in response: {clean_res}")
            elif type_name == "list":
                match = re.search(r'\[[\s\S]*\]', clean_res)
                if match:
                    json_str = match.group()
                    if json_str.startswith("```"):
                        json_str = re.sub(r'^```(json)?\n?|\n?```$', '', json_str, flags=re.MULTILINE).strip()
                    val = json.loads(json_str)
                    return Registry.box(val)
                raise ValueError(f"No JSON list found in response: {clean_res}")
            elif type_name == "dict":
                match = re.search(r'\{[\s\S]*\}', clean_res)
                if match:
                    json_str = match.group()
                    if json_str.startswith("```"):
                        json_str = re.sub(r'^```(json)?\n?|\n?```$', '', json_str, flags=re.MULTILINE).strip()
                    val = json.loads(json_str)
                    return Registry.box(val)
                raise ValueError(f"No JSON dict found in response: {clean_res}")
            
            return Registry.box(raw_res)

        except Exception as e:
            self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response: {str(e)}")
            raise LLMUncertaintyError(
                f"LLM 返回值类型转换失败：期望 {type_name}，但解析出错。\n原始返回: {raw_res}\n详细错误: {str(e)}",
                node_uid,
                raw_response=raw_res
            )

    def execute_behavior_expression(self, node_uid: str, context: RuntimeContext, captured_intents: Optional[List[Any]] = None) -> IbObject:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。
        """
        interpreter = self.service_context.interpreter
        node_data = interpreter.node_pool.get(node_uid, {})
        
        # 0. 准备环境
        ai_module = self.service_context.interop.get_package("ai")

        # 1. 评估段式插值
        content = self._evaluate_segments(node_data.get("segments"), context)
        
        # 2. 收集与合并意图
        all_intents = []
        auto_intent = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_intent = ai_module._config.get("auto_intent_injection", True)
        
        intent_uid = node_data.get("intent")
        if auto_intent:
            all_intents = self._merge_intents(intent_uid, context, captured_intents=captured_intents)
        elif intent_uid:
            all_intents = [self._resolve_intent_content(intent_uid, context)]
            
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
            if injected_type not in ("var", "callable", "Any"):
                sys_prompt += f"\n预期返回类型：{injected_type}。请确保输出内容可以直接解析或转换为该类型。"
        
        if all_intents:
            sys_prompt += "\n当前执行意图约束：\n" + "\n".join(f"- {i}" for i in all_intents)
            
        if current_retry_hint:
            sys_prompt += f"\n\n注意：这是重试请求。之前的回答不符合要求，请参考此修正提示：{current_retry_hint}"
            
        # 4. 执行
        response = self._call_llm(sys_prompt, content, node_uid, scene=scene_name.lower())
            
        # 5. 严格场景校验 (BRANCH/LOOP)
        from core.foundation.builtins import IbInteger, IbString
        if scene_name.upper() in ("BRANCH", "LOOP"):
            clean_res = response.strip().lower()
            decision_map = {"1": 1, "0": 0, "true": 1, "false": 0, "yes": 1, "no": 0}
            if clean_res in decision_map:
                self.retry_hint = None
                return IbInteger.from_native(decision_map[clean_res])
            
            raise LLMUncertaintyError(f"LLM decision format error: {response}", node_uid, raw_response=response)

        self.retry_hint = None
        return IbString(response)


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
        intent_data = interpreter.node_pool.get(self.intent_uid, {})
        
        # 使用原始字典作为意图信息
        # 为了兼容 .mode 的访问，我们将其包装在一个简单的 namespace 对象中
        intent_info = SimpleNamespace(
            content=intent_data.get('content', ''),
            mode=intent_data.get('mode', 'append'),
            segments=intent_data.get('segments', [])
        )
        
        self.service_context.runtime_context.push_intent(intent_info)
        try:
            return action()
        finally:
            self.service_context.runtime_context.pop_intent()

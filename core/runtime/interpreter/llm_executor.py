import re
import json
from typing import Any, List, Optional, Dict, Union
from .interfaces import LLMExecutor, RuntimeContext, ServiceContext
from core.types import parser_types as ast
from core.types.exception_types import InterpreterError, LLMUncertaintyError
from core.support.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.runtime.ext.capabilities import ILLMProvider
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel

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

    def push_expected_type(self, type_name: str):
        self._expected_type_stack.append(type_name)
    
    def pop_expected_type(self):
        if self._expected_type_stack:
            self._expected_type_stack.pop()

    def execute_llm_function(self, node: ast.LLMFunctionDef, args: List[Any], context: RuntimeContext) -> Any:
        """
        执行命名的 llm 函数定义块。
        """
        # 0. 绑定参数到临时作用域，以便 evaluator 可以解析
        context.enter_scope()
        try:
            if self.service_context and self.service_context.debugger:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{node.name}' with {len(args)} args")

            for i, arg_def in enumerate(node.args):
                if i < len(args):
                    context.define_variable(arg_def.arg, args[i])
                    if self.service_context and self.service_context.debugger:
                        self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Bound arg '{arg_def.arg}' = {args[i]}")

            # 1. 提取并评估结构化 Prompt
            sys_prompt = self._evaluate_segments(node.sys_prompt, context)
            user_prompt = self._evaluate_segments(node.user_prompt, context)
            
            if self.service_context and self.service_context.debugger:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Evaluated segments for LLM function '{node.name}'")
            
            # 2. 注入意图增强 (来自当前解释器的意图栈)
            active_intents = context.get_active_intents()
            if active_intents:
                if self.service_context and self.service_context.debugger:
                    self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting {len(active_intents)} active intents into sys_prompt")
                intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in active_intents)
                sys_prompt += intent_block
                
            # 3. 处理返回类型提示注入
            type_name = self._resolve_type_name(node.returns)
            ai_module = None
            if self.service_context and self.service_context.interop:
                ai_module = self.service_context.interop.get_package("ai")
                
            if ai_module and hasattr(ai_module, "get_return_type_prompt"):
                type_prompt = ai_module.get_return_type_prompt(type_name)
                if type_prompt:
                    if self.service_context and self.service_context.debugger:
                        self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting return type prompt for '{type_name}'")
                    sys_prompt += f"\n\n{type_prompt}"

            # 4. 调用底层模型
            raw_res = self._call_llm(sys_prompt, user_prompt, node)
            
            # 记录最后一次调用信息
            self.last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": raw_res,
                "type": "function",
                "name": node.name
            }
            
            # 5. 解析结果为目标类型
            result = self._parse_result(raw_res, type_name, node)
            if self.service_context and self.service_context.debugger:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"LLM function '{node.name}' execution finished. Result type: {type(result).__name__}")
            return result
        finally:
            context.exit_scope()


    def _evaluate_segments(self, segments: Optional[List[Union[str, ast.Expr]]], context: RuntimeContext) -> str:
        """评估结构化提示词片段"""
        if not segments:
            return ""
        
        content_parts = []
        for segment in segments:
            if isinstance(segment, str):
                content_parts.append(segment)
            elif isinstance(segment, ast.Expr):
                if self.service_context and self.service_context.evaluator:
                    val = self.service_context.evaluator.evaluate_expr(segment, context)
                    content_parts.append(str(val))
                else:
                    raise InterpreterError("Evaluator not initialized in LLMExecutor", segment, error_code=RUN_GENERIC_ERROR)
            else:
                content_parts.append(str(segment))
        return "".join(content_parts)

    def _resolve_type_name(self, type_node: Optional[ast.ASTNode]) -> str:
        if type_node is None:
            return "str"
        if isinstance(type_node, ast.Name):
            return type_node.id
        if isinstance(type_node, ast.Subscript):
            # 简单处理泛型如 list[int] -> list
            return self._resolve_type_name(type_node.value)
        return "str"

    def _parse_result(self, raw_res: str, type_name: str, node: ast.ASTNode) -> Any:
        clean_res = raw_res.strip()
        
        if type_name == "str":
            return raw_res
        
        if self.service_context and self.service_context.debugger:
            self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Parsing LLM response to type '{type_name}'")

        try:
            if type_name == "int":
                # 提取第一个数字序列
                match = re.search(r'-?\d+', clean_res)
                if match:
                    val = int(match.group())
                    if self.service_context and self.service_context.debugger:
                        self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Extracted int: {val}")
                    return val
                raise ValueError("No integer found in response")
            elif type_name == "float":
                # 提取第一个浮点数序列
                match = re.search(r'-?\d+(\.\d+)?', clean_res)
                if match:
                    val = float(match.group())
                    if self.service_context and self.service_context.debugger:
                        self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Extracted float: {val}")
                    return val
                raise ValueError("No float found in response")
            elif type_name == "list":
                # 尝试提取 JSON 数组部分
                match = re.search(r'\[[\s\S]*\]', clean_res)
                if match:
                    json_str = match.group()
                    # 处理可能存在的嵌套 markdown (如果 regex 匹配到了代码块标记)
                    if json_str.startswith("```"):
                        json_str = re.sub(r'^```(json)?\n?|\n?```$', '', json_str, flags=re.MULTILINE).strip()
                    val = json.loads(json_str)
                    if self.service_context and self.service_context.debugger:
                        self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Extracted list with {len(val)} elements")
                    return val
                raise ValueError("No JSON list found in response")
            elif type_name == "dict":
                # 尝试提取 JSON 对象部分
                match = re.search(r'\{[\s\S]*\}', clean_res)
                if match:
                    json_str = match.group()
                    if json_str.startswith("```"):
                        json_str = re.sub(r'^```(json)?\n?|\n?```$', '', json_str, flags=re.MULTILINE).strip()
                    val = json.loads(json_str)
                    if self.service_context and self.service_context.debugger:
                        self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Extracted dict with {len(val)} keys")
                    return val
                raise ValueError("No JSON dictionary found in response")
            elif type_name == "bool":
                lower_res = clean_res.lower()
                val = None
                if re.search(r'\b(true|1|yes|ok)\b', lower_res): val = True
                elif re.search(r'\b(false|0|no|fail)\b', lower_res): val = False
                else: val = bool(clean_res)
                
                if self.service_context and self.service_context.debugger:
                    self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Extracted bool: {val}")
                return val
            
            return raw_res
        except Exception as e:
            if self.service_context and self.service_context.debugger:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response: {str(e)}")
            raise InterpreterError(
                f"LLM 返回值类型转换失败：期望 {type_name}，但解析出错。\n原始返回: {raw_res}\n详细错误: {str(e)}",
                node,
                error_code=RUN_LLM_ERROR
            )

    def execute_behavior_expression(self, node: ast.BehaviorExpr, context: RuntimeContext) -> str:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。
        """
        # 0. 准备环境
        ai_module = None
        if self.service_context and self.service_context.interop:
            ai_module = self.service_context.interop.get_package("ai")

        # 1. 评估段式插值
        content = self._evaluate_segments(node.segments, context)
        
        # 2. 收集意图
        all_intents = []
        auto_intent = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_intent = ai_module._config.get("auto_intent_injection", True)
        
        if auto_intent:
            all_intents = context.get_active_intents()
        
        if node.intent:
            all_intents.append(node.intent)
            
        # 3. 确定场景与提示词
        scene = node.scene_tag
        sys_prompt = "你是一个意图行为代码执行器。"
        
        # 获取场景特定的系统提示词 (通过 ai 组件配置)
        current_retry_hint = self.retry_hint
        if ai_module:
            # 如果内核没有 hint 但 ai 模块有 (用户手动设置)，则同步过来
            if not current_retry_hint and hasattr(ai_module, "_retry_hint"):
                current_retry_hint = ai_module._retry_hint
            
        if ai_module and hasattr(ai_module, "get_scene_prompt"):
            scene_prompt = ai_module.get_scene_prompt(scene.name.lower())
            if scene_prompt:
                sys_prompt = scene_prompt

        # 注入预期类型约束 (如果当前是在赋值上下文中执行)
        injected_type = None
        auto_type = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_type = ai_module._config.get("auto_type_constraint", True)

        if auto_type and self._expected_type_stack:
            injected_type = self._expected_type_stack[-1]
            if injected_type != "var" and injected_type != "callable":
                sys_prompt += f"\n预期返回类型：{injected_type}。请确保输出内容可以直接解析或转换为该类型。"
        
        if self.service_context and self.service_context.debugger:
            self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Synthesizing prompt for behavior (Scene: {scene.name})")
            if node.intent:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injected local intent: {node.intent}")
            if injected_type:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injected expected type constraint: {injected_type}")
            if not auto_intent and context.get_active_intents():
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, "Skipped active intents injection due to configuration.")

        if all_intents:
            sys_prompt += "\n当前执行意图约束：\n" + "\n".join(f"- {i}" for i in all_intents)
            
        # 注入 retry_hint (如果有)
        if current_retry_hint:
            sys_prompt += f"\n\n注意：这是重试请求。之前的回答不符合要求，请参考此修正提示：{current_retry_hint}"
            
        # 4. 执行
        response = self._call_llm(sys_prompt, content, node, scene=scene.name.lower())
            
        # 记录最后一次调用信息
        self.last_call_info = {
            "sys_prompt": sys_prompt,
            "user_prompt": content,
            "response": response,
            "type": "behavior",
            "scene": scene.name.lower()
        }
            
        # 成功执行后清除 retry_hint (或者在 retry 逻辑中控制)
        # 注意：如果是 LLMUncertaintyError，可能会再次进入 retry 流程设置新的 hint
        self.retry_hint = None
        
        # 5. 严格场景校验
        if scene in (ast.Scene.BRANCH, ast.Scene.LOOP):
            clean_res = response.strip().lower()
            
            # 获取决策映射表 (优先从 ai 模块获取)
            decision_map = {
                "1": "1", "0": "0", "true": "1", "false": "0", "yes": "1", "no": "0"
            }
            if ai_module and hasattr(ai_module, "get_decision_map"):
                decision_map = ai_module.get_decision_map()
            
            if clean_res in decision_map:
                mapped_val = decision_map[clean_res]
                if self.service_context and self.service_context.debugger:
                    self.service_context.debugger.trace(
                        CoreModule.LLM, DebugLevel.DETAIL, 
                        f"Decision mapping applied: '{clean_res}' -> '{mapped_val}'"
                    )
                return mapped_val
            
            if self.service_context and self.service_context.debugger:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Ambiguous response in {scene.name} scene: {response}")

            raise LLMUncertaintyError(
                f"LLM 返回值在 {scene.name} 场景下不明确，期望 0 或 1，实际收到: {response}",
                node,
                raw_response=response
            )
            
        return response


    def _call_llm(self, sys_prompt: str, user_prompt: str, node: ast.ASTNode, scene: str = "general") -> str:
        if self.service_context and self.service_context.debugger:
            self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Calling LLM (Scene: {scene})")
            self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "System Prompt:", data=sys_prompt)
            self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "User Prompt:", data=user_prompt)
        
        if self.llm_callback:
            # 同步同步重试提示词
            if self.retry_hint:
                if self.service_context and self.service_context.debugger:
                    self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting retry hint: {self.retry_hint}")
                self.llm_callback.set_retry_hint(self.retry_hint)
            
            # 调用 Provider
            response = self.llm_callback(sys_prompt, user_prompt, scene=scene)
            if self.service_context and self.service_context.debugger:
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, "LLM Response received.")
                self.service_context.debugger.trace(CoreModule.LLM, DebugLevel.DATA, "LLM Raw Response:", data=response)
            return response
        
        # 如果没有回调，说明配置缺失，抛出错误
        raise InterpreterError(
            "LLM 运行配置缺失：未配置有效的 LLM 调用接口。\n"
            "请确保已导入 'ai' 模块并正确调用了 'ai.set_config'。",
            node,
            error_code=RUN_LLM_ERROR
        )

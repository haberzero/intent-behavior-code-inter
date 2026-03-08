import re
import json
from typing import Any, List, Optional, Dict, Union
from core.foundation.interfaces import LLMExecutor, RuntimeContext, ServiceContext
from core.domain import ast as ast
from core.domain.exceptions import InterpreterError, LLMUncertaintyError
from core.support.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR
from core.foundation.capabilities import ILLMProvider
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.foundation.kernel import IbObject

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

    def execute_llm_function(self, node: ast.LLMFunctionDef, receiver: IbObject, args: List[IbObject], context: RuntimeContext) -> IbObject:
        """
        处理 llm 声明式函数定义 (LLMFunctionDef)。
        """
        from core.foundation.builtins import IbNone
        context.enter_scope()
        try:
            self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Executing LLM function '{node.name}' with {len(args)} args")

            # 绑定 self (如果是方法调用)
            if not isinstance(receiver, IbNone):
                context.define_variable("self", receiver)
            
            # 绑定参数
            formal_params = node.args
            # 如果第一个形参是 explicit 'self'，跳过它，因为上面已经绑定了 receiver
            if formal_params and formal_params[0].arg == "self":
                formal_params = formal_params[1:]

            for i, arg_def in enumerate(formal_params):
                if i < len(args):
                    context.define_variable(arg_def.arg, args[i])
                    # 兼容性：如果参数名为 self 或 text，自动映射到 __self / __text
                    if arg_def.arg == 'self':
                        context.define_variable('__self', args[i])
                    elif arg_def.arg == 'text':
                        context.define_variable('__text', args[i])
                    self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Bound arg '{arg_def.arg}' = {args[i]}")

            # 1. 提取并评估结构化 Prompt
            sys_prompt = self._evaluate_segments(node.sys_prompt, context)
            user_prompt = self._evaluate_segments(node.user_prompt, context)
            
            self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Evaluated segments for LLM function '{node.name}'")
            
            # 2. 注入意图增强 (三层架构合并)
            merged_intents = self._merge_intents(None, context)
            if merged_intents:
                self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting merged intents into sys_prompt")
                intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in merged_intents)
                sys_prompt += intent_block
                
            # 3. 处理返回类型提示注入
            type_name = self._resolve_type_name(node.returns)
            ai_module = None
            if self.service_context and self.service_context.interop:
                ai_module = self.service_context.interop.get_package("ai")
                
            if ai_module and hasattr(ai_module, "get_return_type_prompt"):
                type_prompt = ai_module.get_return_type_prompt(type_name)
                if type_prompt:
                    self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Injecting return type prompt for '{type_name}'")
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
            
            # 5. 结果解析
            return self._parse_result(raw_res, type_name, node)
            
        finally:
            context.exit_scope()


    def _merge_intents(self, call_intent: Optional[ast.IntentInfo], context: RuntimeContext, captured_intents: Optional[List[ast.IntentInfo]] = None) -> List[str]:
        """
        合并 Global, Block, Call 三层意图。
        支持 @+, @!, @- 等修饰符逻辑。
        """
        # 1. 基础收集
        global_intents = context.get_global_intents()
        active_intents = context.get_active_intents()
        if captured_intents:
            active_intents = self._unique_merge_nodes(captured_intents, active_intents)
            
        # 2. 处理模式 (Mode) 逻辑：Block 层级的 Exclusive (!)
        resolved_block_intents = []
        is_exclusive = False
        for i in reversed(active_intents):
            content = self._resolve_intent_content(i, context)
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
        if call_intent:
            mode = call_intent.mode
            content = self._resolve_intent_content(call_intent, context)
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

    def _resolve_intent_content(self, intent: ast.IntentInfo, context: RuntimeContext) -> str:
        """Resolve dynamic variables in intent content."""
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

    def _unique_merge_nodes(self, *lists: List[ast.IntentInfo]) -> List[ast.IntentInfo]:
        result = []
        seen = set()
        for l in lists:
            for item in l:
                # 使用内容作为去重键（简化处理）
                key = (item.mode, item.content)
                if key not in seen:
                    result.append(item)
                    seen.add(key)
        return result

    def _evaluate_segments(self, segments: Optional[List[Union[str, ast.Expr]]], context: RuntimeContext) -> str:
        """评估结构化提示词片段"""
        if not segments:
            return ""
        
        from core.foundation.kernel import IbObject
        content_parts = []
        for segment in segments:
            if isinstance(segment, str):
                content_parts.append(segment)
            elif isinstance(segment, ast.Expr):
                if self.service_context and self.service_context.interpreter:
                    val = self.service_context.interpreter.visit(segment)
                    
                    # --- __to_prompt__ Protocol ---
                    if isinstance(val, IbObject):
                        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Applying __to_prompt__ protocol for {val}")
                        # 优先尝试通过 Ib 消息发送调用 __to_prompt__
                        # 但为了性能和简单，直接调用 Python 层的 __to_prompt__ 
                        # 因为 IbObject.__to_prompt__ 默认逻辑已经包含了多态支持
                        content_parts.append(val.__to_prompt__())
                    else:
                        content_parts.append(str(val))
                else:
                    raise InterpreterError("Interpreter not initialized in LLMExecutor", segment, error_code=RUN_GENERIC_ERROR)
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

    def _parse_result(self, raw_res: str, type_name: str, node: ast.ASTNode) -> IbObject:
        clean_res = raw_res.strip()
        from core.foundation.builtins import IbInteger, IbString, IbList
        
        if type_name == "str":
            return IbString(raw_res)
        
        self.debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, f"Parsing LLM response to type '{type_name}'")

        try:
            if type_name == "int":
                match = re.search(r'-?\d+', clean_res)
                if match:
                    val = int(match.group())
                    return IbInteger.from_native(val)
                raise ValueError(f"No integer found in response: {clean_res}")
            elif type_name == "list":
                match = re.search(r'\[[\s\S]*\]', clean_res)
                if match:
                    json_str = match.group()
                    if json_str.startswith("```"):
                        json_str = re.sub(r'^```(json)?\n?|\n?```$', '', json_str, flags=re.MULTILINE).strip()
                    val = json.loads(json_str)
                    interpreter = self.service_context.interpreter
                    return IbList([interpreter._box_native(i) for i in val])
                raise ValueError(f"No JSON list found in response: {clean_res}")
            elif type_name == "dict":
                match = re.search(r'\{[\s\S]*\}', clean_res)
                if match:
                    json_str = match.group()
                    if json_str.startswith("```"):
                        json_str = re.sub(r'^```(json)?\n?|\n?```$', '', json_str, flags=re.MULTILINE).strip()
                    val = json.loads(json_str)
                    interpreter = self.service_context.interpreter
                    return interpreter._box_native(val)
                raise ValueError(f"No JSON dict found in response: {clean_res}")
            
            return IbString(raw_res)

        except Exception as e:
            self.debugger.trace(CoreModule.LLM, DebugLevel.BASIC, f"Failed to parse LLM response: {str(e)}")
            raise InterpreterError(
                f"LLM 返回值类型转换失败：期望 {type_name}，但解析出错。\n原始返回: {raw_res}\n详细错误: {str(e)}",
                node,
                error_code=RUN_LLM_ERROR
            )

    def execute_behavior_expression(self, node: ast.BehaviorExpr, context: RuntimeContext, captured_intents: Optional[List[ast.IntentInfo]] = None) -> IbObject:
        """
        处理行为描述行 (即时、匿名的 LLM 调用)。
        """
        # 0. 准备环境
        ai_module = None
        if self.service_context and self.service_context.interop:
            ai_module = self.service_context.interop.get_package("ai")

        # 1. 评估段式插值
        content = self._evaluate_segments(node.segments, context)
        
        # 2. 收集与合并意图
        all_intents = []
        auto_intent = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_intent = ai_module._config.get("auto_intent_injection", True)
        
        if auto_intent:
            all_intents = self._merge_intents(node.intent, context, captured_intents=captured_intents)
        elif node.intent:
            all_intents = [self._resolve_intent_content(node.intent, context)]
            
        # 3. 确定场景与提示词
        scene = node.scene_tag
        sys_prompt = "你是一个意图行为代码执行器。"
        
        current_retry_hint = self.retry_hint
        if ai_module:
            if not current_retry_hint and hasattr(ai_module, "_retry_hint"):
                current_retry_hint = ai_module._retry_hint
            
        if ai_module and hasattr(ai_module, "get_scene_prompt"):
            scene_prompt = ai_module.get_scene_prompt(scene.name.lower())
            if scene_prompt:
                sys_prompt = scene_prompt

        # 注入预期类型约束
        injected_type = None
        auto_type = True
        if ai_module and hasattr(ai_module, "_config"):
            auto_type = ai_module._config.get("auto_type_constraint", True)

        if auto_type and self._expected_type_stack:
            injected_type = self._expected_type_stack[-1]
            if injected_type != "var" and injected_type != "callable":
                sys_prompt += f"\n预期返回类型：{injected_type}。请确保输出内容可以直接解析或转换为该类型。"
        
        if all_intents:
            sys_prompt += "\n当前执行意图约束：\n" + "\n".join(f"- {i}" for i in all_intents)
            
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
            
        if "MOCK_UNCERTAIN_RESPONSE" in response:
            raise LLMUncertaintyError(
                f"LLM 返回了明确的不确定性信号：{response}",
                node,
                raw_response=response
             )
 
        # 5. 严格场景校验
        from core.foundation.builtins import IbString, IbInteger
        if scene in (ast.Scene.BRANCH, ast.Scene.LOOP):
            clean_res = response.strip().lower()
            
            decision_map = {
                "1": "1", "0": "0", "true": "1", "false": "0", "yes": "1", "no": "0"
            }
            if ai_module and hasattr(ai_module, "get_decision_map"):
                # 合并默认决策图与用户自定义图
                custom_map = ai_module.get_decision_map()
                if custom_map:
                    decision_map.update(custom_map)
            
            if clean_res in decision_map:
                self.retry_hint = None
                return IbInteger.from_native(int(decision_map[clean_res]))
            
            # 如果是循环/分支场景但没能匹配到决策结果，则认为是输出格式有问题，抛出不确定异常触发 fallback/retry
            raise LLMUncertaintyError(
                f"LLM 决策响应格式非法：期望 0/1 (或 mapped 决策值)，但返回了: {response}",
                node,
                raw_response=response
            )

        # 6. 普通场景结果转换 (对齐 LLM 函数解析逻辑)
        if injected_type:
            try:
                result = self._parse_result(response, injected_type, node)
                self.retry_hint = None
                return result
            except InterpreterError:
                # 如果是强转失败，且有 fallback 逻辑，则由外层捕获
                raise
            except Exception as e:
                # 包装为不确定异常，允许 fallback 处理
                raise LLMUncertaintyError(str(e), node, raw_response=response)

        self.retry_hint = None
        return IbString(response)


    def _call_llm(self, sys_prompt: str, user_prompt: str, node: ast.ASTNode, scene: str = "general") -> str:
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
            node,
            error_code=RUN_LLM_ERROR
        )

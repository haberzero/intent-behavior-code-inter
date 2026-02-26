import re
from typing import Any, List, Optional, Dict
from .interfaces import LLMExecutor, RuntimeContext, ServiceContext
from core.types import parser_types as ast
from core.types.exception_types import InterpreterError, LLMUncertaintyError
from core.support.diagnostics.codes import RUN_LLM_ERROR, RUN_GENERIC_ERROR

class LLMExecutorImpl:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
    """
    def __init__(self, service_context: Optional[ServiceContext] = None, llm_callback: Optional[Any] = None):
        """
        service_context: 注入容器
        llm_callback: 实际的 LLM 调用接口 (底层)。
        """
        self.service_context = service_context
        self.llm_callback = llm_callback
        self.retry_hint: Optional[str] = None

    def execute_llm_function(self, node: ast.LLMFunctionDef, args: List[Any], context: RuntimeContext) -> str:
        """
        执行命名的 llm 函数定义块。
        """
        # 1. 提取基础 Prompt
        sys_prompt = node.sys_prompt.value if node.sys_prompt else ""
        user_prompt = node.user_prompt.value if node.user_prompt else ""
        
        # 2. 注入意图增强 (来自当前解释器的意图栈)
        active_intents = context.get_active_intents()
        if active_intents:
            intent_block = "\n你还需要特别额外注意的是：\n" + "\n".join(f"- {i}" for i in active_intents)
            sys_prompt += intent_block
            
        # 3. 处理参数占位符 $__param__ 的替换
        arg_map = {arg_def.arg: str(args[i]) for i, arg_def in enumerate(node.args) if i < len(args)}
        
        def replace_placeholder(match):
            param_name = match.group(1)
            return arg_map.get(param_name, match.group(0))

        # 使用正则替换 $__name__
        placeholder_pattern = re.compile(r'\$__(\w+)__')
        sys_prompt = placeholder_pattern.sub(replace_placeholder, sys_prompt)
        user_prompt = placeholder_pattern.sub(replace_placeholder, user_prompt)
        
        # 4. 调用底层模型
        return self._call_llm(sys_prompt, user_prompt, node)

    def execute_behavior_expression(self, node: ast.BehaviorExpr, context: RuntimeContext) -> str:
        """
        处理双波浪号包裹的 ~~行为描述行~~ (即时、匿名的 LLM 调用)。
        """
        content_parts = []
        
        # 1. 处理段式插值
        for segment in node.segments:
            if isinstance(segment, str):
                content_parts.append(segment)
            elif isinstance(segment, (ast.Name, ast.Attribute, ast.Subscript, ast.Expr)):
                # 使用统一的 Evaluator 进行求值
                if self.service_context and self.service_context.evaluator:
                    val = self.service_context.evaluator.evaluate_expr(segment, context)
                    content_parts.append(str(val))
                else:
                    raise InterpreterError("Evaluator not initialized in LLMExecutor", node, error_code=RUN_GENERIC_ERROR)
            else:
                content_parts.append(str(segment))
        
        content = "".join(content_parts)
        
        # 2. 收集意图
        all_intents = context.get_active_intents()
        if node.intent:
            all_intents.append(node.intent)
            
        # 3. 确定场景与提示词
        scene = node.scene_tag
        sys_prompt = "你是一个意图行为代码执行器。"
        
        # 获取场景特定的系统提示词 (通过 ai 组件配置)
        ai_module = None
        if self.service_context and self.service_context.interop:
            ai_module = self.service_context.interop.get_package("ai")
            
        if ai_module and hasattr(ai_module, "get_scene_prompt"):
            scene_prompt = ai_module.get_scene_prompt(scene.name.lower())
            if scene_prompt:
                sys_prompt = scene_prompt

        if all_intents:
            sys_prompt += "\n当前执行意图约束：\n" + "\n".join(f"- {i}" for i in all_intents)
            
        # 注入 retry_hint (如果有)
        if self.retry_hint:
            sys_prompt += f"\n\n注意：这是重试请求。之前的回答不符合要求，请参考此修正提示：{self.retry_hint}"
            
        # 4. 执行
        # Try to pass scene if the callback supports it, otherwise fallback to old signature
        try:
            response = self.llm_callback(sys_prompt, content, scene=scene.name.lower())
        except TypeError:
            response = self.llm_callback(sys_prompt, content)
            
        # 成功执行后清除 retry_hint (或者在 retry 逻辑中控制)
        # 注意：如果是 LLMUncertaintyError，可能会再次进入 retry 流程设置新的 hint
        self.retry_hint = None
        
        # 5. 严格场景校验
        if scene in (ast.Scene.BRANCH, ast.Scene.LOOP):
            clean_res = response.strip().lower()
            if clean_res in ("1", "0"):
                return clean_res
            # 尝试宽松匹配
            if "1" in clean_res and "0" not in clean_res: return "1"
            if "0" in clean_res and "1" not in clean_res: return "0"
            
            raise LLMUncertaintyError(
                f"LLM 返回值在 {scene.name} 场景下不明确，期望 0 或 1，实际收到: {response}",
                node,
                raw_response=response
            )
            
        return response

    def _call_llm(self, sys_prompt: str, user_prompt: str, node: ast.ASTNode) -> str:
        if self.llm_callback:
            return self.llm_callback(sys_prompt, user_prompt)
        
        # 如果没有回调，说明配置缺失，抛出错误
        raise InterpreterError(
            "LLM 运行配置缺失：未配置有效的 LLM 调用接口。\n"
            "请确保已导入 'ai' 模块并正确调用了 'ai.set_config'。",
            node,
            error_code=RUN_LLM_ERROR
        )

import re
from typing import Any, List, Optional, Dict
from .interfaces import LLMExecutor, RuntimeContext
from typedef import parser_types as ast
from typedef.exception_types import InterpreterError

class LLMExecutorImpl:
    """
    LLM 执行核心：处理提示词构建、参数插值和意图注入逻辑。
    """
    def __init__(self, llm_callback: Optional[Any] = None):
        """
        llm_callback: 实际的 LLM 调用接口 (底层)。
        """
        self.llm_callback = llm_callback

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
        if self.llm_callback:
            return self.llm_callback(sys_prompt, user_prompt)
            
        return f"[MOCK LLM] {node.name}\nSYS: {sys_prompt}\nUSER: {user_prompt}"

    def execute_behavior_expression(self, node: ast.BehaviorExpr, context: RuntimeContext) -> str:
        """
        处理双波浪号包裹的 ~~行为描述行~~ (即时、匿名的 LLM 调用)。
        """
        content_parts = []
        
        # 1. 处理段式插值
        for segment in node.segments:
            if isinstance(segment, str):
                content_parts.append(segment)
            elif isinstance(segment, ast.Name):
                try:
                    val = context.get_variable(segment.id)
                    content_parts.append(str(val))
                except (KeyError, NameError):
                    raise InterpreterError(f"Variable '{segment.id}' in behavior expression is not defined.", segment)
        
        content = "".join(content_parts)
        
        # 2. 收集意图：包括节点自带意图 (Parser 注入) 和 全局活动意图栈
        all_intents = context.get_active_intents()
        if node.intent:
            all_intents.append(node.intent)
            
        sys_prompt = "你是一个意图行为代码执行器。"
        if all_intents:
            sys_prompt += "\n当前执行意图约束：\n" + "\n".join(f"- {i}" for i in all_intents)
            
        # 3. 执行
        if self.llm_callback:
            return self.llm_callback(sys_prompt, content)
            
        return f"[MOCK BEHAVIOR] {content}\n(INTENTS: {len(all_intents)})"

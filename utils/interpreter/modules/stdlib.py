import json
import math
import time
import os
from typing import Any
from ..interfaces import InterOp, LLMExecutor, ServiceContext

def register_stdlib(context: ServiceContext):
    """
    注册 ibc-inter 的第一方标准库组件。
    这些组件是利用 Python 原生能力实现的。
    """
    interop = context.interop
    llm_executor = context.llm_executor
    permission_manager = context.permission_manager
    
    # 1. json 组件
    class JSONLib:
        @staticmethod
        def parse(s: str):
            return json.loads(s)
        
        @staticmethod
        def stringify(obj: Any):
            return json.dumps(obj, ensure_ascii=False)
            
    interop.register_package("json", JSONLib)

    # 2. math 组件
    # 直接注册 math 模块即可，InterOp 会处理映射
    interop.register_package("math", math)

    # 3. time 组件
    class TimeLib:
        @staticmethod
        def sleep(seconds: float):
            time.sleep(seconds)
            
        @staticmethod
        def now() -> float:
            return time.time()
            
    interop.register_package("time", TimeLib)

    # 4. file 组件 (基本的文件交互)
    class FileLib:
        @staticmethod
        def read(path: str) -> str:
            permission_manager.validate_path(path, "read")
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        @staticmethod
        def write(path: str, content: str):
            permission_manager.validate_path(path, "write")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        @staticmethod
        def exists(path: str) -> bool:
            # exists check usually doesn't require strict sandbox? 
            # But let's be safe and validate if we want to prevent info leaking.
            permission_manager.validate_path(path, "check existence")
            return os.path.exists(path)

    interop.register_package("file", FileLib)

    # 5. llm 组件 (配置管理与状态联动)
    class LLMHandler:
        def __init__(self, executor: LLMExecutor):
            self.executor = executor
            self.config = {
                "url": None,
                "key": None,
                "model": None,
                "retry": 0,
                "timeout": 30.0
            }
            self.scene_prompts = {
                "general": "你是一个助人为乐的助手。",
                "branch": "你是一个逻辑判断专家。请分析用户提供的意图和内容，如果符合要求请仅返回数字 1，否则返回 0。禁止输出任何其他解释文字。",
                "loop": "你是一个循环控制专家。请分析内容，如果循环应当继续请返回 1，应当停止请返回 0。"
            }
            # 建立跨模块联动：将自己设为执行器的回调
            if hasattr(self.executor, 'llm_callback'):
                self.executor.llm_callback = self

        def set_config(self, url: str, key: str, model: str):
            self.config["url"] = url
            self.config["key"] = key
            self.config["model"] = model
            
        def set_retry(self, count: int):
            self.config["retry"] = count
            
        def set_timeout(self, seconds: float):
            self.config["timeout"] = seconds

        def set_general_prompt(self, prompt: str):
            self.scene_prompts["general"] = prompt

        def set_branch_prompt(self, prompt: str):
            self.scene_prompts["branch"] = prompt

        def set_loop_prompt(self, prompt: str):
            self.scene_prompts["loop"] = prompt

        def set_scene_config(self, scene: str, config: dict):
            if "prompt" in config:
                self.scene_prompts[scene] = config["prompt"]
            # 可以在这里扩展更多配置，如针对特定场景的模型

        def get_scene_prompt(self, scene: str) -> str:
            return self.scene_prompts.get(scene, self.scene_prompts["general"])

        def set_retry_hint(self, hint: str):
            if hasattr(self.executor, 'retry_hint'):
                self.executor.retry_hint = hint

        def __call__(self, sys_prompt: str, user_prompt: str, scene: str = "general") -> str:
            """
            作为 LLMExecutor 的回调执行真实/虚拟调用。
            
            [TESTONLY 模拟指令规范]:
            在 TESTONLY 模式下，可以通过在行为描述行 (~~...~~) 中包含以下指令来精确操控模拟块：
            1. "MOCK:FAIL" -> 模拟 LLM 返回无法解析的内容，触发 llmexcept。
            2. "MOCK:TRUE" / "MOCK:1" -> 在逻辑场景下强制返回 1。
            3. "MOCK:FALSE" / "MOCK:0" -> 在逻辑场景下强制返回 0。
            4. "MOCK:REPAIR" -> 模拟需要“维修”的逻辑。第一次调用返回 MOCK:FAIL，
                             如果 detect 到 retry_hint 已设置，则第二次返回 MOCK:TRUE。
            """
            # 1. 检查配置完备性
            is_test_mode = (
                self.config["url"] == "TESTONLY" or 
                os.environ.get("IBC_TEST_MODE") == "1"
            )

            if not is_test_mode:
                if not self.config["key"] or not self.config["url"] or not self.config["model"]:
                    from typedef.exception_types import InterpreterError
                    raise InterpreterError(
                        "LLM 运行配置缺失：在执行 AI 行为前，必须先配置 LLM 访问参数。\n"
                        "建议修复方案：\n"
                        "1. 在 IBCI 代码顶部增加 'import ai'\n"
                        "2. 调用 'ai.set_config(url, key, model)' 设置正确的 API 信息\n"
                        "   例如：ai.set_config(\"https://api.openai.com\", \"your-key\", \"gpt-4\")\n"
                        "   或者在测试环境中使用 \"TESTONLY\" 作为魔法值。"
                    )

            # 2. 检查 TESTONLY 模拟逻辑
            if is_test_mode:
                # 预处理用户提示词以识别模拟指令
                u_upper = user_prompt.upper()
                
                # 场景 A: 模拟维修/重试闭环 (MOCK:REPAIR)
                if "MOCK:REPAIR" in u_upper:
                    has_hint = hasattr(self.executor, 'retry_hint') and self.executor.retry_hint is not None
                    if not has_hint:
                        # 第一次调用，没有维修提示，模拟失败
                        return "MOCK_UNCERTAIN_RESPONSE"
                    else:
                        # 第二次调用，已有维修提示，模拟成功
                        return "1" if scene in ("branch", "loop") else f"[MOCK] Repaired using hint: {self.executor.retry_hint}"

                # 场景 B: 强制失败指令
                if "MOCK:FAIL" in u_upper:
                    return "MOCK_UNCERTAIN_RESPONSE_TRIGGERING_EXCEPT"

                # 场景 C: 强制布尔结果
                if scene in ("branch", "loop"):
                    if "MOCK:FALSE" in u_upper or "MOCK:0" in u_upper:
                        return "0"
                    if "MOCK:TRUE" in u_upper or "MOCK:1" in u_upper:
                        return "1"
                    # 默认逻辑场景返回 1
                    return "1"

                # 场景 D: 常规文本模拟
                return f"[MOCK] Simulated response for: {user_prompt} (INTENTS: {sys_prompt})"
            
            # 3. 正常执行路径 (带重试逻辑)
            retry_count = self.config.get("retry", 0)
            last_error = None
            
            for attempt in range(retry_count + 1):
                try:
                    # TODO: 实现真实的 LLM API 调用
                    return f"[AI Response using {self.config['model']}] Received: {user_prompt}"
                except Exception as e:
                    last_error = e
                    if attempt < retry_count:
                        continue
            
            raise last_error or Exception("LLM call failed after retries")

    interop.register_package("ai", LLMHandler(llm_executor))

    # 6. sys 组件 (系统控制与权限)
    class SysLib:
        @staticmethod
        def request_external_access():
            """
            请求开启跨工作目录的文件访问权限。
            在原型阶段，直接开启。未来可能增加交互确认。
            """
            permission_manager.enable_external_access()
            
        @staticmethod
        def is_sandboxed() -> bool:
            return not permission_manager.is_external_access_enabled()

    interop.register_package("sys", SysLib)

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

        def __call__(self, sys_prompt: str, user_prompt: str) -> str:
            """
            作为 LLMExecutor 的回调执行真实/虚拟调用
            """
            # 1. 检查配置完备性
            is_test_mode = (
                self.config["url"] == "TESTONLY" and 
                self.config["key"] == "TESTONLY" and 
                self.config["model"] == "TESTONLY"
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

            # 2. 检查 TESTONLY 魔法触发器
            if is_test_mode:
                return f"[TESTONLY MODE] {user_prompt} (INTENTS: {sys_prompt})"
            
            # 3. 正常执行路径 (带重试逻辑)
            retry_count = self.config.get("retry", 0)
            last_error = None
            
            for attempt in range(retry_count + 1):
                try:
                    # TODO: 实现真实的 LLM API 调用，并使用 self.config["timeout"]
                    # 目前仅作为占位符
                    return f"[AI Response using {self.config['model']}] Received: {user_prompt}"
                except Exception as e:
                    last_error = e
                    if attempt < retry_count:
                        # 指数退避或简单等待可以加在这里
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

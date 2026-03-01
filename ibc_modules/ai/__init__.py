import os
import time
from typing import Any, Optional, Dict
from core.runtime.ext.capabilities import ExtensionCapabilities, ILLMProvider

class AILib(ILLMProvider):
    def __init__(self):
        self._capabilities: Optional[ExtensionCapabilities] = None
        self._retry_hint: Optional[str] = None
        self._last_call_info: Dict[str, Any] = {}
        self._client = None
        self._config = {
            "url": None,
            "key": None,
            "model": None,
            "retry": 0,
            "timeout": 30.0
        }
        self._scene_prompts = {
            "general": "你是一个助人为乐的助手。",
            "branch": "你是一个逻辑判断专家。请分析用户提供的意图和内容，判断当前条件是否满足。如果条件满足请返回 1，否则请返回 0。禁止输出任何其他解释文字。",
            "loop": "你是一个循环控制专家。请分析用户提供的意图和内容，判断当前循环条件是否满足。如果条件满足应当继续循环请返回 1，否则（已达到停止条件或不再需要继续）请返回 0。禁止输出任何其他解释文字。"
        }
        self._return_type_prompts = {
            "int": "请仅返回一个整数作为回答，禁止包含任何其他解释文字。",
            "float": "请仅返回一个浮点数作为回答，禁止包含任何其他解释文字。",
            "list": "请仅返回一个合法的 JSON 数组（List）作为回答，禁止包含 Markdown 代码块标记（如 ```json）或任何其他解释文字。",
            "dict": "请仅返回一个合法的 JSON 对象（Dict）作为回答，禁止包含 Markdown 代码块标记（如 ```json）或任何其他解释文字。"
        }

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        # 核心：将自己注册为内核的 LLM Provider
        if self._capabilities.llm_provider is None:
             self._capabilities.llm_provider = self
        
        # 为了向后兼容，如果内核还持有旧的 executor 引用，也可以尝试设置其回调
        # 但在新的 IES 架构中，loader 会负责同步 capabilities 到内核组件

    def _init_client(self):
        is_test_mode = (
            self._config["url"] == "TESTONLY" or 
            os.environ.get("IBC_TEST_MODE") == "1"
        )
        if is_test_mode:
            self._client = "MOCK_CLIENT"
            return

        if self._config["url"] and self._config["key"]:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url=self._config["url"],
                    api_key=self._config["key"],
                    timeout=self._config["timeout"]
                )
            except ImportError:
                pass

    def set_config(self, url: str, key: str, model: str) -> None:
        self._config["url"] = url
        self._config["key"] = key
        self._config["model"] = model
        self._init_client()
        
    def set_retry(self, count: int) -> None:
        self._config["retry"] = count
        
    def set_timeout(self, seconds: float) -> None:
        self._config["timeout"] = seconds
        self._init_client()

    def set_general_prompt(self, prompt: str) -> None:
        self._scene_prompts["general"] = prompt

    def set_branch_prompt(self, prompt: str) -> None:
        self._scene_prompts["branch"] = prompt

    def set_loop_prompt(self, prompt: str) -> None:
        self._scene_prompts["loop"] = prompt

    def set_scene_config(self, scene: str, config: Dict[str, Any]) -> None:
        if "prompt" in config:
            self._scene_prompts[scene] = config["prompt"]

    def get_scene_prompt(self, scene: str) -> str:
        return self._scene_prompts.get(scene, self._scene_prompts["general"])

    def set_return_type_prompt(self, type_name: str, prompt: str) -> None:
        self._return_type_prompts[type_name] = prompt

    def get_return_type_prompt(self, type_name: str) -> Optional[str]:
        return self._return_type_prompts.get(type_name)

    def set_retry_hint(self, hint: str) -> None:
        self._retry_hint = hint

    def get_last_call_info(self) -> Dict[str, Any]:
        return self._last_call_info

    def __call__(self, sys_prompt: str, user_prompt: str, scene: str = "general") -> str:
        is_test_mode = (
            self._config["url"] == "TESTONLY" or 
            os.environ.get("IBC_TEST_MODE") == "1"
        )

        if not is_test_mode:
            if not self._config["key"] or not self._config["url"] or not self._config["model"]:
                from core.types.exception_types import InterpreterError
                raise InterpreterError(
                    "LLM 运行配置缺失：在执行 AI 行为前，必须先配置 LLM 访问参数。\n"
                    "建议修复方案：\n"
                    "1. 在 IBCI 代码顶部增加 'import ai'\n"
                    "2. 调用 'ai.set_config(url, key, model)' 设置正确的 API 信息\n"
                    "   例如：ai.set_config(\"https://api.openai.com\", \"your-key\", \"gpt-4\")\n"
                    "   或者在测试环境中使用 \"TESTONLY\" 作为魔法值。"
                )

        if is_test_mode:
            u_upper = user_prompt.upper()
            if "MOCK:RESPONSE:" in u_upper:
                res = user_prompt.split("MOCK:RESPONSE:")[1].strip()
                self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
                return res

            if "MOCK:REPAIR" in u_upper:
                has_hint = self._retry_hint is not None
                if not has_hint:
                    res = "MOCK_UNCERTAIN_RESPONSE"
                else:
                    res = "1" if scene in ("branch", "loop") else f"[MOCK] Repaired using hint: {self._retry_hint}"
                self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
                return res
            
            if "MOCK:FAIL" in u_upper:
                res = "MOCK_UNCERTAIN_RESPONSE_TRIGGERING_EXCEPT"
                self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
                return res

            res = "1"
            if scene in ("branch", "loop"):
                if "MOCK:FALSE" in u_upper or "MOCK:0" in u_upper:
                    res = "0"
                elif "MOCK:TRUE" in u_upper or "MOCK:1" in u_upper:
                    res = "1"
            else:
                res = f"[MOCK] Simulated response for: {user_prompt} (INTENTS: {sys_prompt})"
            
            self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
            return res
        
        retry_count = self._config.get("retry", 0)
        last_error = None
        
        for attempt in range(retry_count + 1):
            try:
                if not self._client:
                    self._init_client()
                
                if not self._client:
                    raise Exception("Failed to initialize OpenAI client. Please check your configuration.")

                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                response = self._client.chat.completions.create(
                    model=self._config["model"],
                    messages=messages,
                    temperature=0.1 if scene in ("branch", "loop") else 0.7
                )
                
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                if attempt < retry_count:
                    time.sleep(1)
                    continue
        
        from core.types.exception_types import InterpreterError
        raise InterpreterError(f"LLM call failed after {retry_count + 1} attempts: {str(last_error)}")

def create_implementation():
    return AILib()

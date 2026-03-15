import os
import time
from typing import Any, Optional, Dict, List
from core.foundation.interfaces import ExtensionCapabilities, ILLMProvider

class AIPlugin(ILLMProvider):
    """
    AI 2.0: LLM 供应者。
    实现职责下放：通过 capabilities.box() 自行转换复杂对象。
    """
    def __init__(self):
        # [IES 2.0] 状态隔离：每个实例必须持有自己的能力引用
        self._capabilities: Optional[ExtensionCapabilities] = None
        self._retry_hint: Optional[str] = None
        self._last_call_info: Dict[str, Any] = {}
        self._client = None
        self._config = {
            "url": None,
            "key": None,
            "model": None,
            "retry": 0,
            "timeout": 30.0,
            "auto_type_constraint": True,
            "auto_intent_injection": True,
            "decision_map": {
                "1": "1", "true": "1", "yes": "1", "ok": "1",
                "0": "0", "false": "0", "no": "0", "fail": "0"
            }
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

    def set_config(self, url: str, key: str, model: str, **kwargs) -> None:
        self._config["url"] = url
        self._config["key"] = key
        self._config["model"] = model
        
        if "auto_type_constraint" in kwargs:
            self._config["auto_type_constraint"] = bool(kwargs["auto_type_constraint"])
        if "auto_intent_injection" in kwargs:
            self._config["auto_intent_injection"] = bool(kwargs["auto_intent_injection"])
            
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

    def set_decision_map(self, decision_map: Dict[str, str]) -> None:
        self._config["decision_map"] = decision_map

    def get_decision_map(self) -> Dict[str, str]:
        return self._config.get("decision_map", {})

    # --- Global Intent Management ---
    def set_global_intent(self, intent: str) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.set_global_intent(intent)

    def clear_global_intents(self) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.clear_global_intents()

    def remove_global_intent(self, intent: str) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.remove_global_intent(intent)

    def mask(self, tag_pattern: str) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.push_intent("", mode="-", tag=tag_pattern)

    def get_global_intents(self) -> List[str]:
        if self._capabilities and self._capabilities.intent_manager:
            return self._capabilities.intent_manager.get_global_intents()
        return []

    def get_current_intent_stack(self) -> List[str]:
        if self._capabilities and self._capabilities.intent_manager:
            global_ints = self._capabilities.intent_manager.get_global_intents()
            active_infos = self._capabilities.intent_manager.get_active_intents()
            active_ints = [i.content for i in active_infos]
            res = []
            seen = set()
            for i in global_ints + active_ints:
                if i not in seen:
                    res.append(i)
                    seen.add(i)
            return res
        return []

    def __call__(self, sys_prompt: str, user_prompt: str, scene: str = "general") -> str:
        # LLM 调用逻辑保持不变...
        is_test_mode = (
            self._config["url"] == "TESTONLY" or 
            os.environ.get("IBC_TEST_MODE") == "1"
        )

        if not is_test_mode:
            if not self._config["key"] or not self._config["url"] or not self._config["model"]:
                from core.domain.issue import InterpreterError
                raise InterpreterError("LLM 运行配置缺失")

        if is_test_mode:
            # Mock 逻辑简化
            res = "1"
            if scene in ("branch", "loop"):
                res = "1"
            else:
                res = f"[MOCK] {user_prompt}"
            self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
            return res
        
        # 实际调用逻辑...
        return "[REAL_LLM_NOT_IMPLEMENTED_IN_CORE]"

    def get_vtable(self) -> Dict[str, Any]:
        """[IES 2.0] 显式虚表映射"""
        return {
            "set_config": self.set_config,
            "set_retry_hint": self.set_retry_hint,
            "set_retry": self.set_retry,
            "set_timeout": self.set_timeout,
            "set_general_prompt": self.set_general_prompt,
            "set_branch_prompt": self.set_branch_prompt,
            "set_loop_prompt": self.set_loop_prompt,
            "set_return_type_prompt": self.set_return_type_prompt,
            "get_return_type_prompt": self.get_return_type_prompt,
            "set_decision_map": self.set_decision_map,
            "get_decision_map": self.get_decision_map,
            "get_last_call_info": self.get_last_call_info,
            "get_scene_prompt": self.get_scene_prompt,
            "set_scene_config": self.set_scene_config,
            "set_global_intent": self.set_global_intent,
            "clear_global_intents": self.clear_global_intents,
            "remove_global_intent": self.remove_global_intent,
            "get_global_intents": self.get_global_intents,
            "get_current_intent_stack": self.get_current_intent_stack,
            "mask": self.mask,
        }

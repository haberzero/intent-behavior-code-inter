import os
import time
from typing import Any, Optional, Dict, List
from core.base.interfaces import ILLMProvider
from core.extension.ibcext import ExtensionCapabilities


class AIPlugin(ILLMProvider):
    """
    [IES 2.2] AI LLM 供应者插件。
    核心级插件，必须继承 ILLMProvider 以与解释器深度绑定。
    """
    def __init__(self):
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
                "1": 1, "true": 1, "yes": 1, "ok": 1,
                "0": 0, "false": 0, "no": 0, "fail": 0
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
        self._retry_prompts = {
            "IbIf": "此处的逻辑判断存在歧义。请严格基于事实，返回 1 (条件成立) 或 0 (条件不成立)。",
            "IbWhile": "循环条件判断模糊。请确认当前任务是否已完成：返回 0 表示完成（跳出循环），返回 1 表示继续。",
            "IbExprStmt": "当前行为描述执行失败或结果不明确。请尝试以更直接、更具确定性的方式重新执行。",
            "IbAssign": "目标值计算模糊。请确保返回的内容能被清晰地识别并赋值给变量。"
        }
        self._capabilities: Optional[ExtensionCapabilities] = None
        self._mock_state: Dict[str, int] = {}
        self._mock_retry_counts: Dict[str, int] = {}

    def reset_mock_state(self) -> None:
        """重置Mock状态，用于测试隔离"""
        self._mock_state.clear()
        self._mock_retry_counts.clear()

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        # [IES 2.2] 向能力注册表注册自己为 LLM Provider
        capabilities.expose("llm_provider", self)

    def _init_client(self):
        """初始化 OpenAI 客户端 (单例/复用模式)"""
        is_test_mode = (
            self._config["url"] == "TESTONLY" or
            os.environ.get("IBC_TEST_MODE") == "1"
        )
        if is_test_mode:
            self._client = "MOCK_CLIENT"
            return

        try:
            from openai import OpenAI
            
            base_url = self._config["url"]
            # [IES 2.2 Fix] 自动补充 /v1 后缀，如果用户没写且不是特殊本地服务
            if base_url and "/v1" not in base_url and ("127.0.0.1" in base_url or "localhost" in base_url):
                base_url = f"{base_url.rstrip('/')}/v1"
            
            if base_url and self._config["key"]:
                self._client = OpenAI(
                    api_key=self._config["key"],
                    base_url=base_url,
                    timeout=self._config["timeout"]
                )
        except ImportError:
            self._client = None
        except Exception:
            self._client = None

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

    def get_retry_prompt(self, node_type: str) -> Optional[str]:
        return self._retry_prompts.get(node_type)

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
        is_test_mode = (
            self._config["url"] == "TESTONLY" or
            os.environ.get("IBC_TEST_MODE") == "1"
        )

        # [IES 2.2] 强化决策场景的 User Prompt 约束
        scene_str = str(scene).lower()
        if any(keyword in scene_str for keyword in ("branch", "loop", "decision", "choice")):
            user_prompt += "\n\n### 强制回答要求 ###\n- 你必须【仅】返回数字 0 或 1。\n- 如果条件成立/满足/继续，你必须且仅能返回 1。\n- 如果条件不成立/不满足/停止，你必须且仅能返回 0。\n- 严禁包含任何其他字符（包括解释、Markdown、引号等）。"

        if not is_test_mode:
            if not self._config["key"] or not self._config["url"] or not self._config["model"]:
                raise RuntimeError("LLM 运行配置缺失")
            
            # [IES 2.2 Real LLM] 优先使用预初始化的客户端 (单例复用)
            if not self._client or self._client == "MOCK_CLIENT":
                self._init_client()
            
            if not self._client or self._client == "MOCK_CLIENT":
                raise RuntimeError("未安装 'openai' 库或客户端初始化失败，请运行 'pip install openai'。")
            
            # [IES 2.2 Strict Mode] 决策场景下，限制 max_tokens 以减少噪音
            is_decision = any(keyword in scene_str for keyword in ("branch", "loop", "decision", "choice"))
            
            try:
                completion = self._client.chat.completions.create(
                    model=self._config["model"],
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=10 if is_decision else 1024
                )
                
                if not completion or not hasattr(completion, 'choices') or not completion.choices:
                    raise RuntimeError(f"LLM 返回异常响应: {completion}")

                res = completion.choices[0].message.content.strip()
                self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "raw_response": res, "scene": scene}
                return res
            except Exception as e:
                raise RuntimeError(f"LLM 调用失败: {str(e)}")

        if is_test_mode:
            res = self._handle_mock_response(user_prompt, scene)
            self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
            return res

        return "[REAL_LLM_NOT_IMPLEMENTED_IN_CORE]"

    def _handle_mock_response(self, user_prompt: str, scene: str) -> str:
        """
        [IES 2.2 Mock Testing] 处理 MOCK 前缀指令。
        MOCK:FAIL - 触发 llmexcept
        MOCK:TRUE - 返回 "1"
        MOCK:FALSE - 返回 "0"
        MOCK:REPAIR - 首次返回模糊值，重试后返回确定值
        """
        if not user_prompt.startswith("MOCK:"):
            if scene in ("branch", "loop"):
                return "1"
            return f"[MOCK] {user_prompt}"

        parts = user_prompt[5:].split(" ", 1)
        mock_cmd = parts[0].upper() if parts else ""
        mock_content = parts[1] if len(parts) > 1 else ""

        if mock_cmd == "FAIL":
            self._mock_state[mock_content] = -1
            return "MAYBE_YES_MAYBE_NO_this_is_ambiguous"

        if mock_cmd == "TRUE":
            self._mock_state[mock_content] = 1
            return "1"

        if mock_cmd == "FALSE":
            self._mock_state[mock_content] = 0
            return "0"

        if mock_cmd == "REPAIR":
            retry_key = f"_repair_{mock_content}"
            if retry_key not in self._mock_retry_counts:
                self._mock_retry_counts[retry_key] = 0

            if self._mock_retry_counts[retry_key] == 0:
                self._mock_retry_counts[retry_key] = 1
                self._mock_state[mock_content] = -1
                return "MAYBE_YES_MAYBE_NO_this_is_ambiguous"
            else:
                self._mock_retry_counts[retry_key] = 0
                self._mock_state[mock_content] = 1
                return "1"

        if scene in ("branch", "loop"):
            return "1"
        return f"[MOCK] {user_prompt}"


def create_implementation():
    return AIPlugin()

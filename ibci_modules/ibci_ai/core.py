import os
import time
from typing import Any, Optional, Dict, List
from core.base.interfaces import ILLMProvider
from core.extension.ibcext import ExtensionCapabilities


class AIPlugin(ILLMProvider):
    """
    AI LLM 供应者插件。
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
            "retry": 3,
            "timeout": 30.0,
            "auto_type_constraint": True,
            "auto_intent_injection": True
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
        
        # [NEW] 模型能力策略缓存
        self._model_capabilities = {
            "probed": False,          # 是否已经探测过
            "is_reasoning": False,    # 是否是强制推理模型
            "supports_system": True,  # 是否支持 System 角色
            "extract_strategy": "standard" # 提取策略: standard, tag_based, keyword_based
        }

    def reset_mock_state(self) -> None:
        """重置Mock状态，用于测试隔离"""
        self._mock_state.clear()
        self._mock_retry_counts.clear()

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        # 向能力注册表注册自己为 LLM Provider
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
            # 自动补充 /v1 后缀，如果用户没写且不是特殊本地服务
            if base_url and "/v1" not in base_url and ("127.0.0.1" in base_url or "localhost" in base_url):
                base_url = f"{base_url.rstrip('/')}/v1"
            
            if base_url and self._config["key"]:
                self._client = OpenAI(
                    api_key=self._config["key"],
                    base_url=base_url,
                    timeout=self._config["timeout"]
                )
        except ImportError:
            raise RuntimeError("未安装 'openai' 库，请运行 'pip install openai'。")
        except Exception as e:
            raise RuntimeError(f"OpenAI 客户端初始化失败: {str(e)}")

    def set_config(self, url: str, key: str, model: str, **kwargs) -> None:
        self._config["url"] = url
        self._config["key"] = key
        self._config["model"] = model

        if "auto_type_constraint" in kwargs:
            self._config["auto_type_constraint"] = bool(kwargs["auto_type_constraint"])
        if "auto_intent_injection" in kwargs:
            self._config["auto_intent_injection"] = bool(kwargs["auto_intent_injection"])

        # 如果切换了模型，重置探测状态
        self._model_capabilities["probed"] = False
        self._init_client()

    def has_api_key(self) -> bool:
        """检查是否已配置 API 密钥"""
        key = self._config.get("key", "")
        url = self._config.get("url", "")
        model = self._config.get("model", "")
        return bool(key and url and model)

    def probe_model(self) -> str:
        """
        模型能力探针 (Model Capability Probe)
        通过发送特定的测试请求，动态检测模型是否属于"强制推理模型" (Reasoning/CoT Model)，
        并在内部缓存探测结果以指导后续所有的工作流调用策略。
        """
        is_test_mode = (self._config["key"] == "MOCK_KEY" or self._config["url"] == "TESTONLY")
        if is_test_mode:
            self._model_capabilities.update({
                "probed": True, "is_reasoning": False, "extract_strategy": "standard"
            })
            return "MOCK_PROBE_SUCCESS"

        if not self._client:
            self._init_client()

        print(f"\n[AI Probe] 正在探测模型 {self._config['model']} 的响应特征...")
        
        # 探测 Prompt：要求极简回答，禁止思考
        sys_prompt = "You are a direct assistant. Answer the following question with ONLY ONE WORD ('YES' or 'NO'). DO NOT output any reasoning, thinking process, or explanation."
        user_prompt = "Is the sky blue?"
        
        try:
            # 缩短超时，并且限制 max_tokens
            completion = self._client.chat.completions.create(
                model=self._config["model"],
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,
                timeout=15.0
            )
            print("    -> [System] Called llm once (Probe).")
            
            raw_content = completion.choices[0].message.content
            reasoning = getattr(completion.choices[0].message, "reasoning", None)
            if reasoning is None and hasattr(completion.choices[0].message, "reasoning_content"):
                reasoning = completion.choices[0].message.reasoning_content
                
            if raw_content is None:
                raw_content = ""
                
            # 记录调用信息以便调试
            self._last_call_info = {
                "sys_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "response": raw_content,
                "raw_response": raw_content,
                "scene": "probe"
            }

            is_reasoning = False
            # 判定条件：
            # 1. 有专用的 reasoning 字段
            # 2. content 里面包含了明显的 Thinking 标识
            # 3. 不听指令，返回了长篇大论 (字数过多)
            if reasoning:
                is_reasoning = True
                print("  => 探测到专用 reasoning 字段，判定为 [强制推理模型]。")
            elif "Thinking Process:" in raw_content or "<think>" in raw_content:
                is_reasoning = True
                print("  => 探测到 Thinking 特征字符串，判定为 [强制推理模型]。")
            elif len(raw_content.split()) > 10:
                is_reasoning = True
                print("  => 模型无视了 'ONLY ONE WORD' 指令，输出啰嗦内容，保守判定为 [强制推理模型]。")
            else:
                print("  => 模型遵循了极简指令，判定为 [标准指令模型]。")
                
            self._model_capabilities.update({
                "probed": True,
                "is_reasoning": is_reasoning,
                "extract_strategy": "tag_based" if is_reasoning else "standard"
            })
            
            return "REASONING_MODEL" if is_reasoning else "STANDARD_MODEL"
            
        except Exception as e:
            print(f"  => [!警告] 探测失败 ({e})，将使用安全回退策略 (当作推理模型处理)。")
            self._model_capabilities.update({
                "probed": True,
                "is_reasoning": True,
                "extract_strategy": "tag_based"
            })
            return "PROBE_FAILED_FALLBACK_REASONING"

    def set_retry(self, count: int) -> None:
        self._config["retry"] = count

    def get_retry(self) -> int:
        return self._config.get("retry", 3)

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
        
        # 统一对输入内容进行清洗
        user_prompt = user_prompt.strip()

        # 在注入约束后缀前，先检查 Mock 指令
        if is_test_mode:
            res = self._handle_mock_response(user_prompt, scene)
            self._last_call_info = {"sys_prompt": sys_prompt, "user_prompt": user_prompt, "response": res, "scene": scene}
            return res

        # 强化决策场景的 User Prompt 约束
        scene_str = str(scene).lower()
        if any(keyword in scene_str for keyword in ("branch", "loop", "decision", "choice")):
            user_prompt += "\n\n(重要：只允许返回 0 或 1。如果条件成立则返回 1，不成立则返回 0。)"
            
        if not is_test_mode:
            if not self._config["key"] or not self._config["url"] or not self._config["model"]:
                raise RuntimeError("LLM 运行配置缺失")
            
            # 优先使用预初始化的客户端 (单例复用)
            if not self._client or self._client == "MOCK_CLIENT":
                self._init_client()
            
            if not self._client or self._client == "MOCK_CLIENT":
                raise RuntimeError("未安装 'openai' 库或客户端初始化失败，请运行 'pip install openai'。")
            
            # 决策场景下限制 max_tokens
            is_decision = any(keyword in scene_str for keyword in ("branch", "loop", "decision", "choice"))
            
            # 如果没有主动探测过，可以在这里触发一次懒加载探测，或者直接使用默认策略
            if not self._model_capabilities["probed"]:
                # 为避免隐式延迟，这里默认回退到保守的推理策略，
                # 但推荐用户在脚本中显式调用 ai.probe_model()
                is_reasoning_model = True
            else:
                is_reasoning_model = self._model_capabilities["is_reasoning"]
            
            # 动态调整策略：
            if is_reasoning_model:
                # 强制推理模型：放宽 Token 限制，并要求用 ANSWER 标签包裹最终结果
                decision_max_tokens = 4096
                enhanced_sys_prompt = sys_prompt + "\nIMPORTANT: You are a reasoning model. You MUST output your final, conclusive, and brief answer at the very end of your response, starting with 'ANSWER:'."
            else:
                # 标准指令模型：严格限制 Token 以防噪音，直接使用原 Prompt
                decision_max_tokens = 10
                enhanced_sys_prompt = sys_prompt

            try:
                completion = self._client.chat.completions.create(
                    model=self._config["model"],
                    messages=[
                        {"role": "system", "content": enhanced_sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=decision_max_tokens if is_decision else 4096
                )
                
                # 调试输出，偶尔会使用。注释并保留
                # print("    -> [System] Called llm once.")
                
                if not completion or not hasattr(completion, 'choices') or not completion.choices:
                    raise RuntimeError(f"LLM 返回异常响应: {completion}")

                raw_content = completion.choices[0].message.content
                
                # 兼容性处理：尝试提取 Reasoning 字段
                reasoning = getattr(completion.choices[0].message, "reasoning", None)
                if reasoning is None and hasattr(completion.choices[0].message, "reasoning_content"):
                    reasoning = completion.choices[0].message.reasoning_content
                
                # 如果 content 为空且 reasoning 有值，说明这是强制推理模型把结果都放进 reasoning 里了
                if (raw_content is None or raw_content.strip() == "") and reasoning:
                    raw_content = reasoning
                
                if raw_content is None:
                    res = ""
                else:
                    raw_content = raw_content.strip()
                    # === 核心改造：后处理提取器 ===
                    # 1. 尝试匹配 ANSWER: 前缀
                    if "ANSWER:" in raw_content:
                        res = raw_content.split("ANSWER:")[-1].strip()
                    elif "Answer:" in raw_content:
                        res = raw_content.split("Answer:")[-1].strip()
                    else:
                        # 2. 回退处理：如果模型没写前缀，但是写了 Thinking Process 或思考过程
                        # 我们假定思考过程结束后的最后一段文字就是答案
                        
                        # 剔除可能存在的 Thinking Process 块
                        if "Thinking Process:" in raw_content:
                            parts = raw_content.split("Thinking Process:")
                            raw_content = parts[-1]
                        
                        # 按行分割，过滤掉看起来像推理步骤的行
                        lines = [line.strip() for line in raw_content.split('\n') if line.strip()]
                        valid_lines = []
                        import re
                        for line in lines:
                            if not re.match(r'^[\d\-\*\s]+(Analyze|Consider|Think|Hypothesis|Wait|Wait,|Let\'s|Actually|Alternative|Decision|Correction|Hypothesis \d+|So|Since)', line, re.IGNORECASE):
                                valid_lines.append(line)
                        
                        if valid_lines:
                            # 取最后一行作为结论
                            res = valid_lines[-1]
                        else:
                            res = raw_content

                self._last_call_info = {"sys_prompt": enhanced_sys_prompt, "user_prompt": user_prompt, "response": res, "raw_response": raw_content, "scene": scene}
                return res
            except Exception as e:
                raise RuntimeError(f"LLM 调用失败: {str(e)}")

        return "[REAL_LLM_NOT_IMPLEMENTED_IN_CORE]"

    def _handle_mock_response(self, user_prompt: str, scene: str) -> str:
        """
        处理 MOCK 前缀指令。
        MOCK:FAIL - 触发 llmexcept
        MOCK:TRUE - 返回 "1"
        MOCK:FALSE - 返回 "0"
        MOCK:REPAIR - 首次返回模糊值，重试后返回确定值
        MOCK:[...] - 直接返回列表内容
        MOCK:{...} - 直接返回字典内容
        
        [二级 Mock 指令]
        MOCK:INT:<value> - 返回整数，如 MOCK:INT:42
        MOCK:STR:<value> - 返回字符串，如 MOCK:STR:"hello"
        MOCK:FLOAT:<value> - 返回浮点数，如 MOCK:FLOAT:3.14
        MOCK:BOOL:TRUE/FALSE - 返回布尔值，如 MOCK:BOOL:TRUE
        MOCK:LIST:<json> - 返回列表，如 MOCK:LIST:[1,2,3]
        MOCK:DICT:<json> - 返回字典，如 MOCK:DICT:{"key":"value"}
        """
        if not user_prompt.startswith("MOCK:"):
            if scene in ("branch", "loop"):
                return "1"
            return f"[MOCK] {user_prompt}"

        content_after_mock = user_prompt[5:].strip()
        
        # 1. 检查结构化直接返回 (MOCK:[...] 或 MOCK:{...})
        if content_after_mock.startswith('[') or content_after_mock.startswith('{'):
            return content_after_mock

        # 2. 处理二级类型指令 (MOCK:INT:xxx, MOCK:STR:xxx, etc.)
        if ':' in content_after_mock:
            type_parts = content_after_mock.split(':', 2)
            if len(type_parts) >= 2:
                mock_type = type_parts[0].upper()
                mock_value = type_parts[1] if len(type_parts) == 2 else ':'.join(type_parts[1:])
                
                if mock_type == "INT":
                    return str(int(mock_value))
                elif mock_type == "STR":
                    return mock_value
                elif mock_type == "FLOAT":
                    return str(float(mock_value))
                elif mock_type == "BOOL":
                    return "1" if mock_value.upper() == "TRUE" else "0"
                elif mock_type == "LIST":
                    return f"[{mock_value}]"
                elif mock_type == "DICT":
                    return f"{{{mock_value}}}"

        # 3. 处理命名指令
        parts = content_after_mock.split(" ", 1)
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
                return "__MOCK_REPAIR__"
            else:
                self._mock_retry_counts[retry_key] = 0
                self._mock_state[mock_content] = 1
                return "1"

        # [Enum Hook] 支持自定义返回值
        # MOCK:HAPPY -> 返回 "HAPPY"
        # MOCK:HAPPY 请回复 -> 返回 "HAPPY"
        if not mock_content:
            return mock_cmd

        if scene in ("branch", "loop"):
            return "1"
        return f"[MOCK] {user_prompt}"


def create_implementation():
    return AIPlugin()

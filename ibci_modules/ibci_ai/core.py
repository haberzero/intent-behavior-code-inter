import os
import time
from typing import Any, Optional, Dict, List, Union
from core.extension.ibcext import ExtensionCapabilities, IbStatefulPlugin

from ibci_modules.ibci_ai.mock_scenario import MockScenarioEngine

# MOCK 模式判定与哨兵常量（统一字面量，供配置比对）
MOCK_CONFIG_URL = "TESTONLY"
MOCK_CONFIG_KEY = "MOCK_KEY"
MOCK_CLIENT_SENTINEL = "MOCK_CLIENT"
_MOCK_TEST_MODE_ENV = "IBC_TEST_MODE"


class AIPlugin(IbStatefulPlugin):
    """
    AI LLM 供应者插件。
    通过 capabilities.expose("llm_provider", self) 向内核注册 LLM provider。

    实现 IbStatefulPlugin 协议：LLM 配置、提示词定制等均为跨断点状态，
    断点保存/恢复时由 HostService 负责持久化与恢复。
    """
    def __init__(self):
        self._client = None
        self._config = {
            "url": None,
            "key": None,
            "model": None,
            "retry": 3,
            "timeout": 30.0,
            "auto_intent_injection": True
        }
        # 命名模型注册表：用于 @NAME~ 语法的模型路由
        # 格式: { "NAME": {"url": ..., "key": ..., "model": ..., "timeout": ...} }
        self._model_registry: Dict[str, Dict[str, Any]] = {}
        # 命名模型的已初始化客户端缓存
        self._named_clients: Dict[str, Any] = {}
        self._return_type_prompts = {
            "int": "请仅返回一个整数作为回答，禁止包含任何其他解释文字。",
            "float": "请仅返回一个浮点数作为回答，禁止包含任何其他解释文字。",
            "list": "请仅返回一个合法的 JSON 数组（List）作为回答，禁止包含 Markdown 代码块标记（如 ```json）或任何其他解释文字。",
            "dict": "请仅返回一个合法的 JSON 对象（Dict）作为回答，禁止包含 Markdown 代码块标记（如 ```json）或任何其他解释文字。"
        }
        self._capabilities: Optional[ExtensionCapabilities] = None
        # MOCK 指令语言单点实现（线程安全；seq/retry 状态由引擎持有）
        self._mock_engine = MockScenarioEngine()
        
        # [NEW] 模型能力策略缓存
        self._model_capabilities = {
            "probed": False,          # 是否已经探测过
            "is_reasoning": False,    # 是否是强制推理模型
            "supports_system": True,  # 是否支持 System 角色
            "extract_strategy": "standard" # 提取策略: standard, tag_based, keyword_based
        }

    @staticmethod
    def _is_test_config(url: Optional[str], key: Optional[str]) -> bool:
        """TESTONLY / MOCK 模式统一判定。"""
        return (
            url == MOCK_CONFIG_URL
            or key == MOCK_CONFIG_KEY
            or os.environ.get(_MOCK_TEST_MODE_ENV) == "1"
        )

    def _is_test_mode(self) -> bool:
        """当前默认配置是否处于 MOCK 测试模式。"""
        return self._is_test_config(self._config.get("url"), self._config.get("key"))

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        # 向能力注册表注册自己为 LLM Provider
        capabilities.expose("llm_provider", self)

    def hydrate(self, service_context):
        """
        在 registry hooks（llm_executor / host_service / stack_inspector / state_reader）
        全部注入后调用。当前主要重新确认 LLM Provider 注册；未来可在此捕获
        host_service / llm_executor 等引用供 save/restore 使用。
        """
        if self._capabilities is not None:
            self._capabilities.expose("llm_provider", self)

    def _init_client(self):
        """初始化 OpenAI 客户端 (单例/复用模式)"""
        is_test_mode = self._is_test_mode()
        if is_test_mode:
            self._client = MOCK_CLIENT_SENTINEL
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

        if "auto_intent_injection" in kwargs:
            self._config["auto_intent_injection"] = bool(kwargs["auto_intent_injection"])

        # 如果切换了模型，重置探测状态
        self._model_capabilities["probed"] = False
        self._init_client()

    def register_model(self, name: str, url: str, key: str, model: str, **kwargs) -> None:
        """注册命名模型配置，用于 @NAME~ 语法的模型路由。

        Args:
            name: 模型标识名（对应 @NAME~ 中的 NAME，大小写敏感，必须与使用时完全一致）
            url: API endpoint URL
            key: API key
            model: 模型名称
            **kwargs: 其他可选配置（timeout 等）

        Example (IBCI code):
            ai.register_model("GPT4o", "https://api.openai.com/v1", "sk-...", "gpt-4o")
            str answer = @GPT4o~ 请解释量子力学 ~
        """
        config = {
            "url": url,
            "key": key,
            "model": model,
            "timeout": kwargs.get("timeout", 30.0),
        }
        self._model_registry[name] = config
        # 清除缓存的客户端以便下次使用时重新初始化
        self._named_clients.pop(name, None)

    def _get_named_client(self, name: str):
        """获取或创建命名模型的 OpenAI 客户端。"""
        if name in self._named_clients:
            return self._named_clients[name]

        config = self._model_registry.get(name)
        if not config:
            raise RuntimeError(
                f"未注册的命名模型 '{name}'。请先使用 ai.register_model(\"{name}\", url, key, model) 注册。"
            )

        is_test_mode = self._is_test_config(config["url"], config["key"])
        if is_test_mode:
            self._named_clients[name] = MOCK_CLIENT_SENTINEL
            return MOCK_CLIENT_SENTINEL

        try:
            from openai import OpenAI
            base_url = config["url"]
            if base_url and "/v1" not in base_url and ("127.0.0.1" in base_url or "localhost" in base_url):
                base_url = f"{base_url.rstrip('/')}/v1"
            client = OpenAI(
                api_key=config["key"],
                base_url=base_url,
                timeout=config["timeout"]
            )
            self._named_clients[name] = client
            return client
        except ImportError:
            raise RuntimeError("未安装 'openai' 库，请运行 'pip install openai'。")
        except Exception as e:
            raise RuntimeError(f"命名模型 '{name}' 的 OpenAI 客户端初始化失败: {str(e)}")

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
        is_test_mode = self._is_test_mode()
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
                timeout=15.0,
                extra_body={
                    "enable_thinking": False,
                    "chat_template_kwargs": {"enable_thinking": False}
                }
            )
            print("    -> [System] Called llm once (Probe).")
            
            raw_content = completion.choices[0].message.content
            reasoning = getattr(completion.choices[0].message, "reasoning", None)
            if reasoning is None and hasattr(completion.choices[0].message, "reasoning_content"):
                reasoning = completion.choices[0].message.reasoning_content
                
            if raw_content is None:
                raw_content = ""

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

    def set_return_type_prompt(self, type_name: str, prompt: str) -> None:
        self._return_type_prompts[type_name] = prompt

    def get_return_type_prompt(self, type_name: str) -> Optional[str]:
        return self._return_type_prompts.get(type_name)

    def get_current_call_info(self) -> Dict[str, Any]:
        """获取最近一次 resolve 的调用信息（委托内核 LLM 执行器的主线程单写槽）。"""
        kr = self._capabilities.kernel_registry if self._capabilities else None
        if kr is not None:
            executor = kr.get_llm_executor()
            if executor is not None:
                return dict(executor.get_current_call_info())
        return {}

    def run_batch(self, behavior: Any, items: List[Any]) -> List[Any]:
        """并发批量执行行为对象（`ai.run_batch`）。

        对参数化 fn 行为（``fn f = lambda(str x) -> str: @~ ... $x ... ~``）
        逐项并发执行，保序返回结果列表。任一项 parse 失败抛 ``LLMParseError``。
        """
        kr = self._capabilities.kernel_registry if self._capabilities else None
        if kr is None:
            raise RuntimeError("run_batch: LLM executor not available")
        executor = kr.get_llm_executor()
        if executor is None:
            raise RuntimeError("run_batch: LLM executor does not support batch execution")
        from core.runtime.frame import get_current_execution_context

        ec = get_current_execution_context() or getattr(behavior, "_execution_context", None)
        if ec is None:
            raise RuntimeError("run_batch: no execution context available")
        return executor.run_batch(behavior, list(items), ec)

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

    def __call__(self, sys_prompt: str, user_prompt: "Union[str, List]", scene: str = "general", *, target_model: str = "") -> str:
        """LLM 调用入口（ILLMProvider 协议）。

        ``scene`` 为协议兼容保留参数（当前恒为 ``"general"``，未使用）。
        """
        is_test_mode = self._is_test_mode()
        
        # 多模态内容：将 List 转换为纯文本用于 MOCK 或传递给 API
        # 对于 MOCK 模式和纯文本路径，需要将 List 展平为 str
        user_prompt_text = user_prompt if isinstance(user_prompt, str) else self._flatten_content_parts(user_prompt)

        # 统一对输入内容进行清洗
        user_prompt_text = user_prompt_text.strip()

        # 在注入约束后缀前，先检查 Mock 指令
        if is_test_mode:
            return self._handle_mock_response(user_prompt_text)

        # 命名模型路由：@NAME~ 语法
        if target_model:
            if target_model not in self._model_registry:
                raise RuntimeError(
                    f"未注册的命名模型 '{target_model}'。"
                    f"请先使用 ai.register_model(\"{target_model}\", url, key, model) 注册。"
                )
            named_config = self._model_registry[target_model]
            active_client = self._get_named_client(target_model)
            active_model = named_config["model"]
        else:
            # 默认模型路径
            if not self._config["key"] or not self._config["url"] or not self._config["model"]:
                raise RuntimeError("LLM 运行配置缺失")

            # 优先使用预初始化的客户端 (单例复用)
            if not self._client or self._client == MOCK_CLIENT_SENTINEL:
                self._init_client()

            if not self._client or self._client == MOCK_CLIENT_SENTINEL:
                raise RuntimeError("未安装 'openai' 库或客户端初始化失败，请运行 'pip install openai'。")

            active_client = self._client
            active_model = self._config["model"]

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
            enhanced_sys_prompt = sys_prompt + "\nIMPORTANT: You are a reasoning model. You MUST output your final, conclusive, and brief answer at the very end of your response, starting with 'ANSWER:'."
        else:
            # 标准指令模型：直接使用原 Prompt
            enhanced_sys_prompt = sys_prompt

        try:
            # 构建 messages：支持纯文本和多模态两种路径
            user_content = self._build_user_content(user_prompt, user_prompt_text)
            completion = active_client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": enhanced_sys_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=4096,
                extra_body={
                    "enable_thinking": False,
                    "chat_template_kwargs": {"enable_thinking": False}
                }
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

            return res
        except Exception as e:
            raise RuntimeError(f"LLM 调用失败: {str(e)}")


    @staticmethod
    def _flatten_content_parts(parts: "List") -> str:
        """将多模态 content parts 列表展平为纯文本表示。
        
        用于 MOCK 模式和需要纯文本回退的场景。
        str 片段直接拼接，dict 片段用占位符表示。
        """
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                part_type = part.get("type", "unknown")
                text_parts.append(f"[{part_type}]")
            else:
                text_parts.append(str(part))
        return "".join(text_parts)

    @staticmethod
    def _build_user_content(user_prompt: "Union[str, List]", user_prompt_text: str) -> "Union[str, List[Dict[str, Any]]]":
        """构建 OpenAI API messages 中的 user content 字段。
        
        - 纯文本路径：直接返回 user_prompt_text (str)
        - 多模态路径：将 List[Union[str, dict]] 转换为 OpenAI multimodal content format
          即 List[{"type": "text", "text": "..."} | {"type": "image_url", ...}]
        """
        if isinstance(user_prompt, str):
            return user_prompt_text
        
        # 多模态路径：构建 OpenAI content blocks
        content_blocks = []
        for part in user_prompt:
            if isinstance(part, str):
                if part.strip():  # 跳过空文本块
                    content_blocks.append({"type": "text", "text": part})
            elif isinstance(part, dict):
                # 已经是结构化 content block，直接传递
                content_blocks.append(part)
        
        # 如果转换后为空（不应发生），回退到纯文本
        if not content_blocks:
            return user_prompt_text
        
        return content_blocks

    def _handle_mock_response(self, user_prompt: str) -> str:
        """处理 MOCK 指令（委托 :class:`MockScenarioEngine` 单点实现）。

        指令语言定义见 ``ibci_modules/ibci_ai/mock_scenario.py``。
        内联路径忽略传输层控制（``SLEEP`` 延迟），但 ``ERROR`` 指令在此
        模拟 provider 基础设施失败（raise），使 ``_call_llm`` 的
        ``ThrownException`` 路径不经 HTTP 即可被测试覆盖。
        """
        result = self._mock_engine.handle(user_prompt)
        if result.error_status is not None:
            raise RuntimeError(f"MOCK:ERROR injected ({result.error_status})")
        return result.content

    # ------------------------------------------------------------------
    # IbStatefulPlugin 协议：断点保存/恢复
    # ------------------------------------------------------------------

    def save_plugin_state(self) -> dict:
        """
        导出插件状态快照，用于 HostService 断点保存。

        保存内容：
        - _config：LLM 连接配置（url/key/model/timeout 等）
        - _return_type_prompts：用户自定义的返回类型提示词
        注意：_client 为外部连接对象，不可序列化，恢复后由 _init_client() 重建。
        注意：全局意图由 capabilities.intent_manager 管理，不在此处保存。
        """
        return {
            "config": dict(self._config),
            "return_type_prompts": dict(self._return_type_prompts),
        }

    def restore_plugin_state(self, state: dict) -> None:
        """
        从断点快照恢复插件状态。

        此方法在 setup(capabilities) 之后被调用，capabilities 已可用。
        恢复 config 后会重新初始化 LLM 客户端连接。
        """
        if "config" in state:
            self._config.update(state["config"])
        if "return_type_prompts" in state:
            self._return_type_prompts.update(state["return_type_prompts"])
        # 重建 LLM 客户端（连接对象无法序列化，必须在恢复后重建）
        self._client = None
        self._model_capabilities["probed"] = False
        if self._config.get("url") and self._config.get("key"):
            self._init_client()


def create_implementation():
    return AIPlugin()

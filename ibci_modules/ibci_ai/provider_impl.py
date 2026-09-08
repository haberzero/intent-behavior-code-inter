"""``provider_impl`` —— 推荐 LLM provider 实现（内置默认，纯 provider，kernel-free）。

:class:`RecommendedProvider` 是 IBCI 的**内置默认 provider 实现**：实现供应商无关契约
:class:`LLMProvider`（``core.base.llm_protocol``），把一次 :class:`LLMCallRequest`
组装为 OpenAI 兼容 payload（LM Studio + Qwen 思考抑制适配），并把供应商响应解析
为 :class:`LLMCallResult`。

定位：

- 本文件是 **kernel-free** 的单一实现：只依赖 ``core.base.llm_protocol``
  （最底层契约）与同目录 kernel-free 模块（``mock_scenario`` / ``config_normalize``），
  **不导入** ``core.kernel`` / ``core.runtime`` / ``core.extension``。
- 它作为**内置默认 provider**：未经 ``ai.set_provider`` 注册自定义 provider 时生效。
- **用户自定义 LLM 底层**的正式通道 = 宿主绑定：用户自写实现 :class:`LLMProvider`
  契约的 provider 类，经 ``import python "<mod>" as lib: bind provider`` + 
  ``ai.set_provider(lib.provider)`` 注册为激活 provider（覆盖本默认实现）。写作参考
  `docs/howto/custom_provider_host_binding.md`。
- IBCI 模块胶水（``run_batch`` / ``stream_call`` / ``stream_channel`` / 意图方法 /
  断点状态 / 配置加载入口）在宿主 ``ibci_modules/ibci_ai/core.py`` 的
  ``AIPlugin(RecommendedProvider, IbStatefulPlugin)``——不改本文件。

思考抑制说明：本推荐实现面向开发试用基线（OpenAI 兼容端点 + Qwen 非思考模式）
固定发送 payload 思考抑制字段（顶层 ``enable_thinking=false`` 与
``chat_template_kwargs.enable_thinking=false`` 双形态，多后端兼容）；模型声明
（``api_config.json`` 的 ``reasoning`` 字段 → ``ModelSpec.thinking_mode``）驱动能力判定
（``is_reasoning``）；``LLMCallRequest.thinking_mode`` 是供应商无关的**远期接口位**
（各供应商字段映射在各自 provider 实现内完成，见 PT-DECIDE-2）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from core.base.llm_protocol import (
    LLMProvider,
    LLMCallRequest,
    LLMCallResult,
    OutputContract,
)
from core.base.llm_protocol.recommended import assemble_system_prompt

from ibci_modules.ibci_ai.mock_scenario import MockScenarioEngine
from ibci_modules.ibci_ai.config_normalize import (
    _DEFAULT_TIMEOUT,
    _DEFAULT_RETRY,
    _DEFAULT_AUTO_INTENT,
    to_llm_config,
    _TEMPERATURE_RANGE,
    _TOP_P_RANGE,
)

# 单次生成 token 上限的内置默认（可被 api_config 模型条目 max_tokens 覆盖）
_MAX_TOKENS_DEFAULT = 4096

# 标准生成参数的发送通道路由（provider 职责：vendor 适配层把标准字段集
# 解释进请求面——与 thinking_mode → probe 语义映射同形）。
# SDK 直传 kwarg（OpenAI 标准协议参数）：
_SDK_KWARG_PARAMS = ("temperature", "top_p", "seed")
# vendor 扩展参数（OpenAI 标准协议无此参数，经 extra_body 通道透传）：
_VENDOR_EXTRA_BODY_PARAMS = ("top_k",)


class LLMProviderError(RuntimeError):
    """provider 层契约违约（携带诊断码——失败语义 → 码单点权威源；
    原生函数边界经 code 属性原码透传，不落 RUN_GENERIC_ERROR）。"""

    def __init__(self, message: str, code: str = "RUN_LLM_ERROR"):
        super().__init__(message)
        self.code = code

# MOCK 模式哨兵（仅显式声明进入：_config["mock"]=True，经 set_mock_mode/apply_config
# defaults.mock；不嗅探 url/key，不读隐式环境变量——避免环境开关静默压过显式配置）
MOCK_CLIENT_SENTINEL = "MOCK_CLIENT"

# openai 为可选依赖（与 ibci_net 的 HAS_REQUESTS 同构）。错误收窄覆盖
# provider 层失败契约：openai SDK 全家族基类 + 本仓约定的 provider 失败信号
# RuntimeError（含 mock/第三方 provider）+ 响应格式 ValueError；TypeError /
# AttributeError 等内部代码缺陷原样传播（fail-fast），不被误标为 LLM 调用失败。
try:
    import openai
    _PROVIDER_ERRORS = (openai.OpenAIError, RuntimeError, ValueError)
except ImportError:  # pragma: no cover - 未安装时仅走 MOCK / 配置错误路径
    openai = None  # type: ignore[assignment]
    _PROVIDER_ERRORS = (RuntimeError, ValueError)


class RecommendedProvider(LLMProvider):
    """
    推荐 LLM provider 实现（OpenAI 兼容 / LM Studio + Qwen 思考抑制）。

    - **契约**：实现 :class:`LLMProvider`——内核经 ``call(request)`` /
      ``stream(request)`` 调 LLM 抽象动作，本实现负责把供应商无关的
      ``LLMCallRequest`` 组装成 OpenAI 兼容 payload，并把响应解析为
      ``LLMCallResult``。
    - **用户自定义**：近期分发路径 = 修改/替换本文件（保持 :class:`LLMProvider`
      契约方法 + 宿主依赖的配置应用面），实现自定义 API 格式 / 配置格式 /
      思考参数映射。
    - **kernel-free**：本类不导入任何 kernel / runtime / extension 模块。
    """

    def __init__(self):
        self._client = None
        self._config = {
            "url": None,
            "key": None,
            "model": None,
            "retry": _DEFAULT_RETRY,
            "timeout": _DEFAULT_TIMEOUT,
            "auto_intent_injection": _DEFAULT_AUTO_INTENT,
            "mock": False,
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
        # MOCK 指令语言单点实现（线程安全；seq/retry 状态由引擎持有）
        self._mock_engine = MockScenarioEngine()

        # 模型能力决策缓存（probe / reasoning 声明 / mock 写入，调用路径消费）
        self._model_capabilities = {
            "probed": False,          # 是否已探测/声明模型类别
            "is_reasoning": False,    # 是否是强制推理模型
        }
        # 未 probe 告警去重：仅首次未探测调用告警一次，避免热路径刷屏
        self._unprobed_warned = False
        # 思考禁用失败告警去重：请求已带 enable_thinking=false 但模型仍输出思考 → 警告一次
        self._thinking_suppress_failed_warned = False
        # 最近一次调用信息本地槽（供 get_current_call_info 兜底读取）
        self._last_call_info: Dict[str, Any] = {}

    @staticmethod
    def _extract_reasoning(message: Any) -> Optional[str]:
        """从 provider 消息对象提取推理字段（reasoning / reasoning_content）。

        不同 provider 的 SDK 消息字段名各异——这是对第三方 SDK 对象的合法适配
        探测（非 IBCI 内部对象私有穿透）。probe 与调用两路径共用，消除重复。
        """
        reasoning = getattr(message, "reasoning", None)
        if reasoning is None and hasattr(message, "reasoning_content"):
            reasoning = message.reasoning_content
        return reasoning

    @staticmethod
    def _extract_usage(completion: Any) -> Optional[Dict[str, int]]:
        """从响应提取 usage（token 计数）——OpenAI 兼容标准字段。

        供预算核算面（api_config budget 节 tokens 维度）；provider 未上报
        usage = None（调用方以 calls/wall 兜底，tokens 记 0）。
        """
        u = getattr(completion, "usage", None)
        if u is None:
            return None
        return {
            "input_tokens": getattr(u, "prompt_tokens", None),
            "output_tokens": getattr(u, "completion_tokens", None),
            "total_tokens": getattr(u, "total_tokens", None),
        }

    def _warn_thinking_suppress_failed(self, config_declared_non_reasoning: bool = False) -> None:
        """思考禁用失败告警（一次性去重）。

        请求已带 ``enable_thinking=false`` 抑制思考，但模型响应仍含 ``reasoning``——
        该模型在所用后端强制思考，API 参数无法关闭。这是 IBCI 的**待完善覆盖缺口**
        （供应商感知的思考禁用机制）。提示用户联系开发者 / 提交 issue，附供应商文档
        说明——**不引导用户改配置绕开**（那是掩盖而非解决）。本警告属推荐 provider
        的适配行为，用户可自定义 provider 覆盖。
        """
        if self._thinking_suppress_failed_warned:
            return
        self._thinking_suppress_failed_warned = True
        model = self._config.get("model", "?")
        if config_declared_non_reasoning:
            print(
                f"[警告] 模型 '{model}' 输出思考内容，但配置声明 reasoning:false（非思考）。\n"
                "        尝试的思考抑制参数（enable_thinking=false /"
                " chat_template_kwargs.enable_thinking=false）对该模型无效（后端强制思考）。\n"
                "        这是 IBCI 待完善的覆盖缺口（供应商感知的思考禁用），请联系开发者或\n"
                "        提交 issue，并附供应商文档说明。"
            )
        else:
            print(
                f"[警告] 探测到模型 '{model}' 输出思考内容（reasoning），尽管已请求启用思考抑制\n"
                "        （enable_thinking=false / chat_template_kwargs.enable_thinking=false）\n"
                "        ——API 参数对该模型无效（后端强制思考）。\n"
                "        这是 IBCI 待完善的覆盖缺口（供应商感知的思考禁用），请联系开发者或\n"
                "        提交 issue，并附供应商文档说明。"
            )

    def _is_test_mode(self) -> bool:
        """当前是否处于 MOCK 测试模式（仅显式声明：``_config["mock"]``）。"""
        return bool(self._config.get("mock", False))

    # ------------------------------------------------------------------ #
    # LLMProvider 协议实现（内核 / 用户经 call/stream 调 LLM 抽象动作）
    # ------------------------------------------------------------------ #

    def call(self, request: LLMCallRequest) -> LLMCallResult:
        """执行一次 LLM 调用并解析为供应商无关结果（LLMProvider 协议）。"""
        is_test_mode = self._is_test_mode()
        user_prompt_text = request.user_prompt if isinstance(request.user_prompt, str) else self._flatten_content_parts(request.user_prompt)
        user_prompt_text = user_prompt_text.strip()

        # 未显式探测/声明时的回退策略（与旧路径语义一致）
        if not self._model_capabilities["probed"]:
            if not self._unprobed_warned:
                print("[AI Probe] 警告：未调用 ai.probe_model()，按推理模型保守处理。建议显式探测以选用直接输出模式。")
                self._unprobed_warned = True
            is_reasoning_model = True
        else:
            is_reasoning_model = self._model_capabilities["is_reasoning"]

        # 始终优先组装系统提示词（供 MOCK / 真实两路径共享，并回填 call_info）
        sys_prompt = self._assemble_provider_sys_prompt(request, is_reasoning_model)

        # 在组装约束后检查 Mock 指令（仍报告已组装的 sys_prompt）
        if is_test_mode:
            return self._handle_mock_call(request, user_prompt_text,
                                          provider_meta={"sys_prompt": sys_prompt})

        try:
            client, model = self._resolve_client(request.target_model, require=True)
            messages = self._build_messages(request, sys_prompt, user_prompt_text)
            gen_params = self._resolve_generation_params(request.target_model)
            extra_body = self._resolve_extra_body(request.target_model)
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=self._resolve_max_tokens(request.target_model),
                **gen_params,
                **({"extra_body": extra_body} if extra_body else {}),
            )
            if not completion or not hasattr(completion, 'choices') or not completion.choices:
                raise RuntimeError(f"LLM 返回异常响应: {completion}")

            raw_content = completion.choices[0].message.content
            reasoning = self._extract_reasoning(completion.choices[0].message)
            thinking_detected = reasoning is not None
            finish_reason = getattr(completion.choices[0], "finish_reason", None)
            usage = self._extract_usage(completion)

            if reasoning:
                self._warn_thinking_suppress_failed(
                    config_declared_non_reasoning=not is_reasoning_model
                )

            # 空内容确定性处理：content 空且 reasoning 非空 = 模型只思考未作答
            #（思考抑制失效或行为形态异常）——显式诊断，不再静默以 reasoning
            # 替代 content（可审计性纪律："模型只想了没答"是确定运行状态）。
            if (raw_content is None or raw_content.strip() == "") and reasoning:
                raise LLMProviderError(
                    "LLM 返回空内容（仅有思考内容、无最终答案——思考抑制对该模型"
                    "无效或模型行为形态异常）。请显式声明 reasoning 模式"
                    "（api_config model 条目 reasoning: true）或改用非思考模型端点。",
                    code="RUN_LLM_EMPTY_CONTENT",
                )

            raw_str = raw_content if raw_content is not None else ""
            content = self._post_process_answer(raw_str)

            # 观测面（采样姿态审计闭环）：finish_reason（截断检测面）+
            # generation（有效值——call_info 记录；未声明字段缺省 =
            # "未指定(vendor 默认)"本身即可记录的答案）经 provider_meta
            # 单通道回填（内核 _call_info merge 面），provider 本地槽同步。
            meta = {"sys_prompt": sys_prompt}
            if finish_reason is not None:
                meta["finish_reason"] = finish_reason
            # reasoning（思考内容）非空即记录——强制思考场景（思考抑制
            # 对该模型无效）的可观测面：调试时可见模型实际思考过程
            #（此前仅告警、思考内容丢弃）。provider_meta 为瞬态观测面
            #（不持久化），记录无 token 成本。
            if reasoning:
                meta["reasoning"] = reasoning
            # usage（token 核算/预算面）：OpenAI 兼容标准字段；provider 未
            # 上报 = 缺省（预算面以 calls/wall 兜底，tokens 记 0）
            if usage:
                meta["usage"] = usage
            meta["generation"] = {**gen_params,
                                  "max_tokens": self._resolve_max_tokens(request.target_model)}
            self._record_call_info(
                request, content, raw_str,
                finish_reason=finish_reason, gen_params=gen_params,
            )
            return LLMCallResult(
                content=content,
                raw_response=raw_str,
                reasoning=reasoning,
                thinking_detected=thinking_detected,
                finish_reason=finish_reason,
                provider_meta=meta,
            )
        except _PROVIDER_ERRORS as e:
            # 携带诊断码的契约违约（code 属性 = 失败语义单点权威源）原样
            # 上抛（码透传机制）；其余失败包装为泛化调用失败。
            if isinstance(e, LLMProviderError):
                raise
            raise RuntimeError(f"LLM 调用失败: {str(e)}")

    def stream(self, request: LLMCallRequest):
        """流式执行一次 LLM 调用，返回增量迭代器（逐步产出 str 增量）。"""
        is_test_mode = self._is_test_mode()
        user_prompt_text = request.user_prompt if isinstance(request.user_prompt, str) else self._flatten_content_parts(request.user_prompt)
        user_prompt_text = user_prompt_text.strip()

        if is_test_mode:
            result = self._mock_engine.handle(user_prompt_text)
            if result.error_status is not None:
                raise RuntimeError(f"MOCK:ERROR injected ({result.error_status})")
            # MOCK:STREAM 指令分块模拟增量流式（与 mock_service HTTP 路径同构）；
            # 无分块时按整块文本迭代（保持 stream_call 语义不变）。
            # 生成器形态（IbStreamHandle producer 契约：协作式取消经 gen.close()）。
            chunks = result.chunks if result.chunks else [result.content]
            return (c for c in chunks)

        client, model = self._resolve_client(request.target_model, require=True)
        sys_prompt = self._assemble_provider_sys_prompt(request, is_reasoning_model=False)

        user_content = self._build_user_content(request.user_prompt, user_prompt_text)

        def _gen():
            stream_resp = None
            try:
                gen_params = self._resolve_generation_params(request.target_model)
                extra_body = self._resolve_extra_body(request.target_model)
                stream_resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    stream=True,
                    max_tokens=self._resolve_max_tokens(request.target_model),
                    **gen_params,
                    **({"extra_body": extra_body} if extra_body else {}),
                )
                for chunk in stream_resp:
                    if not chunk or not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    piece = getattr(delta, "content", None)
                    if piece:
                        yield piece
            except _PROVIDER_ERRORS as e:
                if isinstance(e, LLMProviderError):
                    raise
                raise RuntimeError(f"LLM 流式调用失败: {str(e)}")
            finally:
                # 资源闭环：生成器无论被耗尽 / 放弃 / 协作式关闭（gen.close()），
                # HTTP 流都必须释放——连接悬挂会在共享端点积压并扩大退出竞态窗口。
                if stream_resp is not None:
                    stream_resp.close()

        return _gen()

    def get_retry(self) -> int:
        return self._config.get("retry", _DEFAULT_RETRY)

    def is_auto_intent_injection_enabled(self) -> bool:
        return self._config.get("auto_intent_injection", True)

    def get_current_call_info(self) -> Dict[str, Any]:
        """最近一次调用的诊断信息（provider 本地槽）。

        宿主（AIPlugin）会覆盖本方法以优先读内核 LLM 执行器的主线程单写槽；
        无执行器上下文时回退到本本地实现。
        """
        return dict(self._last_call_info)

    def probe(self) -> str:
        """探测模型能力并返回类别标签（LLMProvider 协议）。

        探测的发送方式与判定逻辑是供应商专属适配（OpenAI/LM Studio + Qwen），
        本实现即"推荐 provider"的探测。
        """
        is_test_mode = self._is_test_mode()
        if is_test_mode:
            self._model_capabilities.update({"probed": True, "is_reasoning": False})
            return "MOCK_PROBE_SUCCESS"

        if not self._client:
            self._init_client()

        print(f"\n[AI Probe] 正在探测模型 {self._config['model']} 的响应特征...")

        sys_prompt = "You are a direct assistant. Answer the following question with ONLY ONE WORD ('YES' or 'NO'). DO NOT output any reasoning, thinking process, or explanation."
        user_prompt = "Is the sky blue?"

        try:
            completion = self._client.chat.completions.create(
                model=self._config["model"],
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,
                timeout=15.0,
            )
            print("    -> [System] Called llm once (Probe).")

            raw_content = completion.choices[0].message.content
            reasoning = self._extract_reasoning(completion.choices[0].message)

            if raw_content is None:
                raw_content = ""

            is_reasoning = False
            if reasoning:
                is_reasoning = True
                print("  => 探测到专用 reasoning 字段，判定为 [强制推理模型]。")
                self._warn_thinking_suppress_failed()
            elif "Thinking Process:" in raw_content or "<think>" in raw_content:
                is_reasoning = True
                print("  => 探测到 Thinking 特征字符串，判定为 [强制推理模型]。")
            elif len(raw_content.split()) > 10:
                is_reasoning = True
                print("  => 模型无视了 'ONLY ONE WORD' 指令，输出啰嗦内容，保守判定为 [强制推理模型]。")
            else:
                print("  => 模型遵循了极简指令，判定为 [标准指令模型]。")

            self._model_capabilities.update({"probed": True, "is_reasoning": is_reasoning})
            return "REASONING_MODEL" if is_reasoning else "STANDARD_MODEL"
        except _PROVIDER_ERRORS as e:
            print(f"  => [!警告] 探测失败 ({e})，将使用安全回退策略 (当作推理模型处理)。")
            self._model_capabilities.update({"probed": True, "is_reasoning": True})
            return "PROBE_FAILED_FALLBACK_REASONING"

    # ------------------------------------------------------------------ #
    # Provider 内部：请求→payload 组装 + 响应→result 解析
    # ------------------------------------------------------------------ #

    def _resolve_max_tokens(self, target_model: str) -> int:
        """活动模型单次生成上限：命名模型注册项 > 默认配置 > 内置默认。"""
        if target_model and target_model in self._model_registry:
            return self._model_registry[target_model].get("max_tokens") or _MAX_TOKENS_DEFAULT
        return self._config.get("max_tokens") or _MAX_TOKENS_DEFAULT

    def _resolve_generation_field(self, target_model: str, field: str):
        """活动模型的单个生成参数有效值：命名模型注册项 > 默认配置 > None。

        None = 未声明（采样姿态 = vendor 默认——可审计的缺省语义）。
        """
        reg = self._model_registry.get(target_model)
        if reg is not None:
            v = reg.get(field)
            if v is not None:
                return v
        return self._config.get(field)

    def _resolve_generation_params(self, target_model: str) -> Dict[str, Any]:
        """标准生成参数（SDK 直传 kwarg 通道）：仅含已声明字段。

        缺省 = 不发送（采样姿态由 vendor 默认；call_info 记录有效值）。
        """
        return {
            k: self._resolve_generation_field(target_model, k)
            for k in _SDK_KWARG_PARAMS
            if self._resolve_generation_field(target_model, k) is not None
        }

    def _resolve_extra_body(self, target_model: str) -> Dict[str, Any]:
        """vendor 特定参数透传口子（extra_body 通道）：配置声明原样合并
        + vendor 扩展标准参数（top_k 路由——OpenAI 标准协议无此参数）。

        空 = 不发送（代码对 vendor 零意见）。
        """
        reg = self._model_registry.get(target_model)
        eb: Dict[str, Any] = {}
        if reg is not None:
            eb.update(reg.get("extra_body") or {})
        else:
            eb.update(self._config.get("extra_body") or {})
        for k in _VENDOR_EXTRA_BODY_PARAMS:
            v = self._resolve_generation_field(target_model, k)
            if v is not None:
                eb[k] = v
        return eb

    def _resolve_client(self, target_model: str, require: bool = True):
        """按 target_model 路由客户端；无路由时用默认客户端。

        返回 ``(client, model)``。``require=True`` 时配置缺失 fail-fast。
        """
        if target_model:
            if target_model not in self._model_registry:
                raise RuntimeError(
                    f"未注册的命名模型 '{target_model}'。"
                    f"请先使用 ai.register_model(\"{target_model}\", url, key, model) 注册。"
                )
            named_config = self._model_registry[target_model]
            return self._get_named_client(target_model), named_config["model"]
        if require:
            if not self._config["key"] or not self._config["url"] or not self._config["model"]:
                raise RuntimeError(
                    "LLM 运行配置缺失：请先调用 ai.load_project_config() 加载项目 "
                    "api_config.json，或 ai.set_config(url, key, model) 显式配置。"
                )
            if not self._client or self._client == MOCK_CLIENT_SENTINEL:
                self._init_client()
            if not self._client or self._client == MOCK_CLIENT_SENTINEL:
                raise RuntimeError("未安装 'openai' 库或客户端初始化失败，请运行 'pip install openai'。")
            return self._client, self._config["model"]

    def _assemble_provider_sys_prompt(self, request: LLMCallRequest, is_reasoning_model: bool) -> str:
        """把供应商无关 request 组装为最终系统提示词（推荐模板 + 本 provider 适配）。

        推荐模板处理用户 __sys__（LLM 函数）+ 意图栈 + 输出类型约束；随后
        provider 施加自己的适配（返回类型提示 / 推理模型 ANSWER 约束）。
        """
        # 本 provider 的返回类型提示作为 provider_type_prompt 注入（优先于通用声明）
        provider_type_prompt = None
        if request.output_contract.expected_type:
            provider_type_prompt = self.get_return_type_prompt(
                request.output_contract.expected_type
            )
        sys_prompt = assemble_system_prompt(
            intents=request.intents,
            output_contract=request.output_contract,
            extra_slots=list(request.prompt_slots),
            provider_type_prompt=provider_type_prompt,
        ) or ""

        # 推理模型适配（与旧路径语义一致）：放宽 Token 限制 + ANSWER 标签
        if is_reasoning_model:
            sys_prompt = sys_prompt + (
                "\nIMPORTANT: You are a reasoning model. You MUST output your final, "
                "conclusive, and brief answer at the very end of your response, "
                "starting with 'ANSWER:'."
            )
        return sys_prompt

    def _build_messages(self, request: LLMCallRequest, sys_prompt: str, user_prompt_text: str):
        """构建 messages：支持纯文本和多模态两种路径；重试历史追加到首轮之后。"""
        user_content = self._build_user_content(request.user_prompt, user_prompt_text)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
        ]
        if request.message_history:
            messages.extend(request.message_history)
        return messages

    def _handle_mock_response(self, user_prompt: str) -> str:
        """处理 MOCK 指令（委托 :class:`MockScenarioEngine` 单点实现）。

        返回指令解析出的内容字符串；``ERROR`` 指令在此模拟 provider 基础设施
        失败（raise），使 ``_call_llm`` 的 ``ThrownException`` 路径不经 HTTP
        即可被覆盖。
        """
        result = self._mock_engine.handle(user_prompt)
        if result.error_status is not None:
            raise RuntimeError(f"MOCK:ERROR injected ({result.error_status})")
        return result.content

    def _handle_mock_call(self, request: LLMCallRequest, user_prompt_text: str,
                          provider_meta: Optional[Dict[str, Any]] = None) -> LLMCallResult:
        """进程内 MOCK：经 :meth:`_handle_mock_response` 处理，返回供应商无关结果。

        观测面机制同构：provider_meta 补 generation（max_tokens 有效值——
        mock 无真实采样姿态，字段结构与真实路径一致，仅值面差异）。
        """
        content = self._handle_mock_response(user_prompt_text)
        meta = dict(provider_meta or {})
        meta.setdefault(
            "generation",
            {"max_tokens": self._resolve_max_tokens(request.target_model)},
        )
        return LLMCallResult(
            content=content,
            raw_response=content,
            provider_meta=meta,
        )

    def _record_call_info(
        self, request: LLMCallRequest, content: str, raw: str,
        finish_reason: Optional[str] = None, gen_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录最近一次调用信息到 provider 本地槽（供 get_current_call_info 兜底）。

        采样姿态审计闭环：生成参数记录**有效值**（已声明字段；未声明 =
        字段缺省——"未指定(vendor 默认)"本身即可记录的答案），finish_reason
        透传（截断检测面：length ≠ 解析失败）。
        """
        d = request.as_dict()
        d["response"] = content
        d["raw_response"] = raw
        if finish_reason is not None:
            d["finish_reason"] = finish_reason
        generation = dict(gen_params or {})
        generation["max_tokens"] = self._resolve_max_tokens(request.target_model)
        d["generation"] = generation
        self._last_call_info = d

    @staticmethod
    def _post_process_answer(raw_content: str) -> str:
        """应答后处理（Qwen 适配：剥离 ANSWER:/Thinking Process 前缀，取结论行）。

        属推荐 provider 的适配逻辑——用户自定义 provider 可完全替换。
        """
        raw_content = raw_content.strip()
        if "ANSWER:" in raw_content:
            return raw_content.split("ANSWER:")[-1].strip()
        if "Answer:" in raw_content:
            return raw_content.split("Answer:")[-1].strip()
        if "Thinking Process:" in raw_content:
            parts = raw_content.split("Thinking Process:")
            raw_content = parts[-1]
        lines = [line.strip() for line in raw_content.split('\n') if line.strip()]
        valid_lines = []
        for line in lines:
            if not re.match(
                r'^[\d\-\*\s]+(Analyze|Consider|Think|Hypothesis|Wait|Wait,|Let\'s|Actually|Alternative|Decision|Correction|Hypothesis \d+|So|Since)',
                line, re.IGNORECASE,
            ):
                valid_lines.append(line)
        if valid_lines:
            return valid_lines[-1]
        return raw_content

    # ------------------------------------------------------------------ #
    # 配置 / 客户端 / MOCK / 命名模型（用户 API 层）
    # ------------------------------------------------------------------ #

    def _init_client(self):
        """初始化 OpenAI 客户端 (单例/复用模式)"""
        is_test_mode = self._is_test_mode()
        if is_test_mode:
            self._client = MOCK_CLIENT_SENTINEL
            return

        base_url = self._config["url"]
        key = self._config["key"]
        if not base_url or not key:
            raise RuntimeError(
                "LLM 配置缺失：未提供 base_url / api_key。请先调用 "
                "ai.load_project_config() 加载项目 api_config.json，或 "
                "ai.set_config(url, key, model) 显式配置，或 ai.set_mock_mode()。"
            )

        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=key,
                base_url=base_url,
                timeout=self._config["timeout"]
            )
        except ImportError:
            raise RuntimeError("未安装 'openai' 库，请运行 'pip install openai'。")
        except _PROVIDER_ERRORS as e:
            raise RuntimeError(f"OpenAI 客户端初始化失败: {str(e)}")

    def set_config(
        self, url: str, key: str, model: str,
        timeout: Optional[float] = None, retry: Optional[int] = None,
        max_tokens: Optional[int] = None, temperature: Optional[float] = None,
        top_p: Optional[float] = None, top_k: Optional[int] = None,
        seed: Optional[int] = None, extra_body: Optional[Dict[str, Any]] = None,
        auto_intent_injection: Optional[bool] = None,
    ) -> None:
        """显式配置默认模型（参数面显式声明；未知参数 fail-fast——不静默吞参）。

        生成参数缺省 None = 不发送（采样姿态 vendor 默认，可审计）；
        参数类型/范围违约 = TypeError（运行时 fail-fast，消息指明参数名）。
        """
        self._config["url"] = url
        self._config["key"] = key
        self._config["model"] = model
        self._config["mock"] = False  # 显式 set_config 退出 mock 模式
        self._validate_generation_kwargs(
            "set_config", timeout=timeout, retry=retry, max_tokens=max_tokens,
            temperature=temperature, top_p=top_p, top_k=top_k, seed=seed,
            extra_body=extra_body, auto_intent_injection=auto_intent_injection,
        )

        # 如果切换了模型，重置探测状态
        self._model_capabilities["probed"] = False
        self._unprobed_warned = False
        self._init_client()

    def _validate_generation_kwargs(
        self, context: str, *,
        timeout: Optional[float] = None, retry: Optional[int] = None,
        max_tokens: Optional[int] = None, temperature: Optional[float] = None,
        top_p: Optional[float] = None, top_k: Optional[int] = None,
        seed: Optional[int] = None, extra_body: Optional[Dict[str, Any]] = None,
        auto_intent_injection: Optional[bool] = None,
        target: Optional[str] = None,
    ) -> None:
        """生成参数面 fail-fast 校验 + 落地（set_config/register_model 同链）。

        缺省 None = 不发送（不落地——采样姿态 vendor 默认）；
        非 None 须通过类型/范围校验（违约 = TypeError 指明参数名）。
        落地目标：``target`` 给定 → 命名模型注册项，否则默认配置。
        """
        dest = self._model_registry[target] if target else self._config
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
                raise TypeError(f"{context} timeout 须为正数（收到 {timeout!r}）")
            dest["timeout"] = float(timeout)
        if retry is not None:
            if not isinstance(retry, int) or isinstance(retry, bool) or retry < 0:
                raise TypeError(f"{context} retry 须为非负整数（收到 {retry!r}）")
            dest["retry"] = retry
        if max_tokens is not None:
            if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0:
                raise TypeError(f"{context} max_tokens 须为正整数（收到 {max_tokens!r}）")
            dest["max_tokens"] = max_tokens
        if temperature is not None:
            if not isinstance(temperature, (int, float)) or isinstance(temperature, bool) or not (_TEMPERATURE_RANGE[0] <= temperature <= _TEMPERATURE_RANGE[1]):
                raise TypeError(f"{context} temperature 须为 [0, 2] 内数字（收到 {temperature!r}）")
            dest["temperature"] = float(temperature)
        if top_p is not None:
            if not isinstance(top_p, (int, float)) or isinstance(top_p, bool) or not (_TOP_P_RANGE[0] <= top_p <= _TOP_P_RANGE[1]):
                raise TypeError(f"{context} top_p 须为 [0, 1] 内数字（收到 {top_p!r}）")
            dest["top_p"] = float(top_p)
        if top_k is not None:
            if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
                raise TypeError(f"{context} top_k 须为正整数（收到 {top_k!r}）")
            dest["top_k"] = top_k
        if seed is not None:
            if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
                raise TypeError(f"{context} seed 须为非负整数（收到 {seed!r}）")
            dest["seed"] = seed
        if extra_body is not None:
            if not isinstance(extra_body, dict):
                raise TypeError(f"{context} extra_body 须为 dict（收到 {type(extra_body).__name__}）")
            dest["extra_body"] = dict(extra_body)
        if auto_intent_injection is not None:
            if not isinstance(auto_intent_injection, bool):
                raise TypeError(f"{context} auto_intent_injection 须为 bool（收到 {auto_intent_injection!r}）")
            dest["auto_intent_injection"] = auto_intent_injection

    def set_mock_mode(self, enable: bool = True) -> None:
        """显式进入/退出 MOCK 测试模式（对称开关）。"""
        if enable:
            self._config["mock"] = True
            self._client = MOCK_CLIENT_SENTINEL
            self._model_capabilities["probed"] = True
            self._model_capabilities["is_reasoning"] = False
            self._unprobed_warned = False
            return
        self._config["mock"] = False
        self._model_capabilities["probed"] = False
        self._unprobed_warned = False
        self._init_client()

    def apply_config(self, config, mock: bool = False) -> None:
        """应用逻辑配置（``LLMConnectionConfig`` 或旧 ``ApiConfig.validate`` dict）。

        - ``LLMConnectionConfig``：来自 :class:`ConfigSourceAdapter`（loader 产出）。
        - 旧 dict：含 ``defaults`` / ``default_model`` / ``models`` 键，经
          :func:`config_normalize.to_llm_config` 归一。
        - ``mock``：provider 测试模式（来自文件 schema 的 ``defaults.mock``，非
          逻辑配置字段，单独传入）。

        思考模式映射：``default_model.thinking_mode == "on"`` → 强制推理模型；
        否则按标准指令模型处理。
        """
        if isinstance(config, dict):
            if mock is False and isinstance(config.get("defaults"), dict):
                mock = bool(config["defaults"].get("mock", False)) or mock
            config = to_llm_config(config)

        defaults = config.defaults
        self._config["retry"] = defaults.retry
        self._config["auto_intent_injection"] = defaults.auto_intent_injection

        # 命名模型注册表始终落地（供 @NAME~ 路由，mock 与真实模式皆可用）
        for name, model in config.models.items():
            self.register_model(
                name, model.endpoint, model.auth, model.model_id,
                timeout=model.timeout or _DEFAULT_TIMEOUT,
                max_tokens=model.max_tokens,
                temperature=model.temperature,
                top_p=model.top_p,
                top_k=model.top_k,
                seed=model.seed,
                extra_body=dict(model.extra_body or {}),
            )

        dm = config.default_model
        self._config["timeout"] = dm.timeout if dm.timeout is not None else _DEFAULT_TIMEOUT
        self._config["model"] = dm.model_id
        self._config["max_tokens"] = dm.max_tokens
        # 默认模型生成参数面落地（None = 不发送，不落地——vendor 默认）
        for _f in ("temperature", "top_p", "top_k", "seed"):
            _v = getattr(dm, _f, None)
            if _v is not None:
                self._config[_f] = _v
        if getattr(dm, "extra_body", None):
            self._config["extra_body"] = dict(dm.extra_body)

        if mock:
            self.set_mock_mode()
            return

        self.set_config(dm.endpoint, dm.auth, dm.model_id)
        self._model_capabilities["probed"] = True
        self._model_capabilities["is_reasoning"] = (dm.thinking_mode == "on")
        self._unprobed_warned = False

    def register_model(
        self, name: str, url: str, key: str, model: str,
        timeout: Optional[float] = None, max_tokens: Optional[int] = None,
        temperature: Optional[float] = None, top_p: Optional[float] = None,
        top_k: Optional[int] = None, seed: Optional[int] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> None:
        """注册命名模型配置（@NAME~ 语法模型路由；参数面显式声明）。

        注册即声明变体（endpoint/model/超时/生成参数按变体不同）——
        变化 = 声明的数据（注册点可见、单源、不可变），非隐藏状态；
        未知参数 fail-fast（不静默吞参）。
        """
        config = {
            "url": url,
            "key": key,
            "model": model,
            "timeout": _DEFAULT_TIMEOUT,
        }
        self._model_registry[name] = config
        self._validate_generation_kwargs(
            f"register_model({name!r})", timeout=timeout, max_tokens=max_tokens,
            temperature=temperature, top_p=top_p, top_k=top_k, seed=seed,
            extra_body=extra_body, target=name,
        )
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

        try:
            from openai import OpenAI
            base_url = config["url"]
            client = OpenAI(
                api_key=config["key"],
                base_url=base_url,
                timeout=config["timeout"]
            )
            self._named_clients[name] = client
            return client
        except ImportError:
            raise RuntimeError("未安装 'openai' 库，请运行 'pip install openai'。")
        except _PROVIDER_ERRORS as e:
            raise RuntimeError(f"命名模型 '{name}' 的 OpenAI 客户端初始化失败: {str(e)}")

    def has_api_key(self) -> bool:
        """检查是否已配置 API 密钥（MOCK 模式视为已就绪）。"""
        if self._config.get("mock", False):
            return True
        return bool(self._config.get("key") and self._config.get("url") and self._config.get("model"))

    def probe_model(self) -> str:
        """模型能力探针（用户 API；委托 :meth:`probe`）。"""
        return self.probe()

    def set_retry(self, count: int) -> None:
        self._config["retry"] = count

    def set_timeout(self, seconds: float) -> None:
        self._config["timeout"] = seconds
        self._init_client()

    def set_return_type_prompt(self, type_name: str, prompt: str) -> None:
        self._return_type_prompts[type_name] = prompt

    def get_return_type_prompt(self, type_name: str) -> Optional[str]:
        """返回注册的类型提示；泛型类型按基名回退（list[int] -> list）。"""
        prompt = self._return_type_prompts.get(type_name)
        if prompt is not None:
            return prompt
        if type_name and "[" in type_name:
            base_name = type_name.split("[", 1)[0].strip()
            return self._return_type_prompts.get(base_name)
        return None

    # ------------------------------------------------------------------ #
    # 断点状态（IbStatefulPlugin 协议：save/restore，宿主 AIPlugin 继承）
    # ------------------------------------------------------------------ #

    def save_plugin_state(self) -> dict:
        return {
            "config": dict(self._config),
            "return_type_prompts": dict(self._return_type_prompts),
            # 命名模型注册表（@NAME~ 路由）= 活配置状态的一部分（运行时
            # register_model 可漂移，快照须含）
            "model_registry": {k: dict(v) for k, v in self._model_registry.items()},
        }

    def restore_plugin_state(self, state: dict) -> None:
        if "config" in state:
            self._config.update(state["config"])
        if "return_type_prompts" in state:
            self._return_type_prompts.update(state["return_type_prompts"])
        if "model_registry" in state:
            self._model_registry.update(state["model_registry"])
            # 命名模型客户端缓存绑定旧上下文，整体重置（按配置惰性重建）
            self._named_clients = {}
        self._client = None
        self._model_capabilities["probed"] = False
        self._unprobed_warned = False
        if self._config.get("url") and self._config.get("key"):
            self._init_client()

    @staticmethod
    def _flatten_content_parts(parts: "List") -> str:
        """将多模态 content parts 列表展平为纯文本表示。"""
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
        """构建 OpenAI API messages 中的 user content 字段。"""
        if isinstance(user_prompt, str):
            return user_prompt_text

        content_blocks = []
        for part in user_prompt:
            if isinstance(part, str):
                if part.strip():
                    content_blocks.append({"type": "text", "text": part})
            elif isinstance(part, dict):
                content_blocks.append(part)
        if not content_blocks:
            return user_prompt_text
        return content_blocks
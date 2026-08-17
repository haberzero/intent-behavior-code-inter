"""``core.base.llm_protocol.provider`` —— LLM 调用服务的抽象契约（供应商无关）。

定义内核与外部 LLM 调用服务（AI 插件）之间的**服务契约**：:class:`LLMProvider`
把一次 :class:`~core.base.llm_protocol.llm_call.LLMCallRequest` 转换为实际供应商
调用，并返回供应商无关的 :class:`~core.base.llm_protocol.llm_call.LLMCallResult`。

设计立场（对应"LLM 调用层插件化"主线）：

- 内核只通过本协议调用 LLM（抽象动作），不触碰 openai / anthropic / ollama 等
  任何具体 SDK 或字段。供应商适配完全在实现方。
- provider 实现是**可插拔**的：用户可自写 Python 实现本协议（自定义 API 格式、
  自定义 api_config.json 解析、自定义思考抑制字段映射）。
- 系统提供"推荐 provider"（如 OpenAI 兼容 / Anthropic / LLM Studio + Qwen 思考
  抑制模板），但它们都是本协议的**实现**，不是契约的一部分。

本模块只定义协议接口（类型），不含任何供应商逻辑、无副作用。
"""

from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from core.base.llm_protocol.llm_call import LLMCallRequest, LLMCallResult


class LLMProvider(abc.ABC):
    """LLM 调用服务抽象（供应商无关协议，V2 目标契约）。

    实现方（插件）持有具体的连接/客户端/请求组装与响应解析逻辑；内核只调用
    本协议方法，看不到任何供应商细节。
    """

    @abc.abstractmethod
    def call(self, request: LLMCallRequest) -> LLMCallResult:
        """执行一次 LLM 调用并把供应商响应解析为供应商无关结果。

        失败应抛可定位的异常（含供应商错误），不返回错误值、不静默回退。
        """

    @abc.abstractmethod
    def stream(self, request: LLMCallRequest):
        """流式执行一次 LLM 调用，返回增量迭代器（逐步产出 str 增量）。

        供流式调用（``stream_call`` / ``stream_channel``）消费；非流式场景
        不应调用本方法。
        """

    # ------------------------------------------------------------------ #
    # 供应商无关的横向配置读取（供内核 / llmexcept 循环使用）
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def get_retry(self) -> int:
        """最大 LLM 重试次数（llmexcept 重试循环读取，默认 3）。"""

    @abc.abstractmethod
    def is_auto_intent_injection_enabled(self) -> bool:
        """自动意图注入开关（prompt 拼装前读取；默认 True）。"""

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def get_current_call_info(self) -> Dict[str, Any]:
        """最近一次调用/解析的诊断信息（供 idbg / call_info 内省）。"""

    # ------------------------------------------------------------------ #
    # 能力协商（供应商感知的思考/探测下沉到实现方）
    # ------------------------------------------------------------------ #

    def probe(self) -> str:
        """（可选）探测模型能力并返回类别标签。

        由实现方决定探测的发送方式与判定逻辑（这是供应商专属适配的一部分，
        不再由内核硬编码 qwen 探测/判定）。无自定义探测的实现可抛
        ``NotImplementedError``，由内核按保守策略处理。
        """
        raise NotImplementedError

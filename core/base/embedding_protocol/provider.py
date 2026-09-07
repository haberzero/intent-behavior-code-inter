"""``core.base.embedding_protocol.provider`` —— embedding 调用服务的抽象契约（供应商无关）。

定义内核与外部 embedding 服务（provider 插件）之间的**服务契约**：
:class:`EmbeddingProvider` 把一次
:class:`~core.base.embedding_protocol.embedding_call.EmbeddingRequest`
转换为实际供应商调用，并返回供应商无关的
:class:`~core.base.embedding_protocol.embedding_call.EmbeddingResult`。

设计立场（机制同构基准 = :class:`core.base.llm_protocol.LLMProvider`）：

- 内核只通过本协议调用 embedding（抽象动作），不触碰任何具体 SDK 或字段。
  供应商适配完全在实现方。
- provider 实现是**可插拔**的：用户可自写 Python 实现本协议（自定义 API
  格式、自定义配置解析、确定性 mock 向量生成等）。
- 系统提供"推荐 provider"（OpenAI 兼容 ``/v1/embeddings`` 默认实现 +
  ``MOCK:VEC`` 确定性 mock），它们是本协议的**实现**，不是契约的一部分。
- embedding 无意图/重试语义：``get_retry`` 保留与 LLMProvider 同构的横向
  读取面（默认最小值），不做意图注入/思考协商。

本模块只定义协议接口（类型），不含任何供应商逻辑、无副作用。
"""

from __future__ import annotations

import abc
from typing import Any, Dict

from core.base.embedding_protocol.embedding_call import EmbeddingRequest, EmbeddingResult


class EmbeddingProvider(abc.ABC):
    """embedding 调用服务抽象（供应商无关协议）。

    实现方（插件）持有具体的连接/客户端/请求组装与响应解析逻辑；内核只调用
    本协议方法，看不到任何供应商细节。
    """

    @abc.abstractmethod
    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """执行一次 embedding 调用并把供应商响应解析为供应商无关结果。

        批量保序（结果 ``vectors[i]`` 对应 ``request.texts[i]``）；失败应抛
        可定位的异常（含供应商错误），不返回错误值、不静默回退（fail-fast）。
        """

    # ------------------------------------------------------------------ #
    # 供应商无关的横向配置读取（与 LLMProvider 同构）
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def get_retry(self) -> int:
        """最大重试次数（embedding 无意图重试语义，默认最小值 2）。"""

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def get_current_call_info(self) -> Dict[str, Any]:
        """最近一次调用的诊断信息（供 idbg / call_info 内省）。

        观测面：最近一次嵌入的输入数/维度/时延。
        """

    # ------------------------------------------------------------------ #
    # 能力探测
    # ------------------------------------------------------------------ #

    def probe(self) -> str:
        """（可选）探测服务/模型能力并返回类别标签（含实际维度）。

        由实现方决定探测方式。无自定义探测的实现可抛 ``NotImplementedError``，
        由调用方按保守策略处理（对齐 LLMProvider.probe 的可选形态）。
        """
        raise NotImplementedError

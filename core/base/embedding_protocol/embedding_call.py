"""``core.base.embedding_protocol.embedding_call`` —— embedding 调用结构化契约（供应商无关）。

契约定位于 ``core/base``（最底层，只出不进），是内核 / runtime 与
外部 embedding 服务（provider 插件）之间**唯一**的请求/响应数据契约。

设计立场（机制同构基准 = :mod:`core.base.llm_protocol`）：

- 内核只关心"嵌入这个抽象动作"，**不**关心具体供应商的请求格式。
  :class:`EmbeddingRequest` 只承载供应商无关的原始信息（文本批 / 目标模型 /
  可选维度），**不**含任何供应商字段名。
- provider 实现负责把 :class:`EmbeddingRequest` 组装成所属供应商的真实
  API payload，并把供应商响应解析回供应商无关的 :class:`EmbeddingResult`。
- 向量在契约层以 ``List[float]`` 承载（一等 ``vector`` 值类型属批 2 决策——
  本契约不预设其落地形态）。

本模块只定义纯数据结构，不访问 runtime / registry / provider，无任何副作用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 请求
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmbeddingRequest:
    """一次 embedding 调用的供应商无关请求。

    - ``texts``：待嵌入的文本批（批量保序的输入面；单文本 = 长度 1 的批）。
    - ``target_model``：目标 embedding 模型名（``None`` = provider 默认模型）。
    - ``dimensions``：请求的输出维度（``None`` = 供应商/模型默认）。
      供应商无关声明位——具体供应商如何映射（如 OpenAI 系 ``dimensions``
      参数）由 provider 实现。
    - ``user``：可选的终端用户标识（供应商侧审计位，原样透传）。
    """

    texts: List[str] = field(default_factory=list)
    target_model: Optional[str] = None
    dimensions: Optional[int] = None
    user: Optional[str] = None


# ---------------------------------------------------------------------------
# 响应
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmbeddingResult:
    """一次 embedding 调用的供应商无关结果。

    - ``vectors``：与请求 ``texts`` **按序对应**的向量列表（``List[float]``）；
      ``len(vectors) == len(texts)``（保序由 provider 实现保证——响应项含
      ``index`` 字段时按其排序，否则按返回顺序）。
    - ``dim``：本批向量的维度（批内一致；不一致为契约违约，provider 应 fail-fast）。
    - ``model``：实际生效的模型名（供应商回显或请求目标）。
    - ``latency_seconds``：本次调用耗时（观测位，可选）。
    - ``usage``：供应商用量回显（如 token 数；无则 ``None``）。
    """

    vectors: List[List[float]] = field(default_factory=list)
    dim: int = 0
    model: str = ""
    latency_seconds: Optional[float] = None
    usage: Optional[Dict] = None

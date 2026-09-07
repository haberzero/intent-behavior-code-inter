"""``core.base.embedding_protocol.recommended`` —— 推荐 embedding provider 实现。

OpenAI 兼容 ``/v1/embeddings`` 默认实现 + ``MOCK:VEC`` 确定性 mock。

实现纪律（机制同构 = 上游 LLM provider 实现层）：

- 显式 ``set_config`` / ``set_mock_mode`` 开关（对称）；配置缺失 **fail-fast**
  （抛可定位异常，不静默回退）。
- 批量保序：响应项含 ``index`` 时按其排序，否则按返回顺序；长度/维度不一致
  为契约违约，fail-fast。
- 观测面：最近一次调用的 n_texts/dim/model/latency/mock 记入 call_info。
- mock 向量 = ``sha256(f"{seed}|{text}")`` 派生的确定性 L2 单位向量：
  同输入同输出（断言可判定）、不同输入互异、L2 归一（相似度行为可测）。
  派生键 = ``{seed}|{text}``——对传入的 text 整体派生；按批对齐的序号前缀
  （如 ``vec:{i}``）由 mock 场景引擎在调用本函数前自行拼入 text，本函数
  不承担序号职责（两层职责分离）。
- 失败语义 → 诊断码：抛出的 :class:`EmbeddingProviderError` 携带 ``code``
  属性（``EMB_`` 域，``core.base.diagnostics.codes`` 单一权威源）——语言层
  接线时同码复用。
"""

from __future__ import annotations

import hashlib
import math
import time
from typing import Any, Dict, List, Optional

from core.base.diagnostics.codes import (
    EMB_BATCH_ORDER,
    EMB_CONFIG_MISSING,
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
    EMB_SERVICE_ERROR,
    EMB_ZERO_NORM,
)
from core.base.embedding_protocol.embedding_call import EmbeddingRequest, EmbeddingResult
from core.base.embedding_protocol.provider import EmbeddingProvider

# mock 默认维度（真实维度由 live 供应商决定；mock 可经 dimensions 覆盖）
MOCK_DEFAULT_DIM = 128
# embedding 最小重试（无意图重试语义）
DEFAULT_RETRY = 2


class EmbeddingProviderError(RuntimeError):
    """embedding 契约/服务失败的定位异常（fail-fast，不静默回退）。

    ``code`` 属性 = 失败语义的诊断码（``EMB_`` 域；默认 ``EMB_SERVICE_ERROR``）。
    """

    def __init__(self, message: str, code: str = EMB_SERVICE_ERROR):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# 确定性 mock 向量（MOCK:VEC 语义：哈希派生 + 种子 + L2 归一）
# --------------------------------------------------------------------------- #


def mock_vector(text: str, dim: int, seed: int = 0) -> List[float]:
    """由 ``sha256(f"{seed}|{text}")`` 派生确定性 L2 单位向量。

    同 (text, dim, seed) 输入 → 逐元素相等（断言可判定）；不同文本 → 互异。
    实现：逐 4 字节块映射到 ``[-1, 1)``，末块不足 4 字节按整数组补齐，
    最后 L2 归一；零范数退化（实际不可达）为契约违约，fail-fast
    （``EMB_ZERO_NORM``，不设兜底向量）。
    """
    digest = hashlib.sha256(f"{seed}|{text}".encode("utf-8")).digest()
    # 循环扩展哈希块直到覆盖 dim 个 float
    buf = b""
    counter = 0
    while len(buf) < dim * 4:
        buf += hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
        counter += 1
    vals = []
    for i in range(dim):
        chunk = buf[i * 4:(i + 1) * 4]
        v = int.from_bytes(chunk, "big") / float(2 ** 32)  # [0, 1)
        vals.append(2.0 * v - 1.0)                          # [-1, 1)
    norm = math.sqrt(sum(x * x for x in vals))
    if norm == 0.0:
        raise EmbeddingProviderError(
            f"mock 向量派生零范数（dim={dim}，契约违约——余弦未定义，fail-fast）。",
            code=EMB_ZERO_NORM,
        )
    return [x / norm for x in vals]


class RecommendedEmbeddingProvider(EmbeddingProvider):
    """OpenAI 兼容 ``/v1/embeddings`` 推荐实现（+ MOCK:VEC 确定性 mock）。"""

    def __init__(self) -> None:
        self._base_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._model: Optional[str] = None
        self._timeout: float = 30.0
        self._mock: bool = False
        self._seed: int = 0
        self._mock_dim: int = MOCK_DEFAULT_DIM
        self._client = None
        self._call_info: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # 配置（显式，fail-fast；配置单源由调用方保证——api_config 同机制）
    # ------------------------------------------------------------------ #

    def set_config(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        mock_dim: int = MOCK_DEFAULT_DIM,
        seed: int = 0,
    ) -> None:
        """显式配置后退出 mock 模式（对称 LLM set_config 语义）。"""
        if not base_url or not api_key or not model:
            raise EmbeddingProviderError(
                "embedding 配置缺失：base_url / api_key / model 均必填。",
                code=EMB_CONFIG_MISSING,
            )
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._mock_dim = int(mock_dim)
        self._seed = int(seed)
        self._mock = False
        self._client = None

    def set_mock_mode(self, enable: bool = True) -> None:
        """显式进入/退出 MOCK 模式（MOCK:VEC 确定性向量，断言可判定）。"""
        self._mock = bool(enable)

    # ------------------------------------------------------------------ #
    # 契约动作
    # ------------------------------------------------------------------ #

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        if request is None or len(request.texts) == 0:
            raise EmbeddingProviderError(
                "EmbeddingRequest.texts 为空批（契约违约）。",
                code=EMB_INVALID_INPUT,
            )

        if self._mock:
            t0 = time.time()
            dim = int(request.dimensions or self._mock_dim)
            vectors = [
                mock_vector(text, dim, self._seed) for text in request.texts
            ]
            info: Dict[str, Any] = {
                "n_texts": len(vectors),
                "dim": dim,
                "model": "mock",
                "mock": True,
                "latency_seconds": time.time() - t0,
            }
        else:
            t0 = time.time()
            vectors, model = self._embed_live(request)
            info = {
                "n_texts": len(vectors),
                "dim": len(vectors[0]),
                "model": model,
                "mock": False,
                "latency_seconds": time.time() - t0,
            }
        self._call_info = info
        return EmbeddingResult(
            vectors=vectors,
            dim=len(vectors[0]),
            model=info["model"],
            latency_seconds=info["latency_seconds"],
            usage=None,
        )

    # ------------------------------------------------------------------ #
    # live 路径（OpenAI 兼容）
    # ------------------------------------------------------------------ #

    def _embed_live(self, request: EmbeddingRequest):
        client, model = self._resolve_client(request.target_model)
        kwargs: Dict[str, Any] = {"model": model, "input": list(request.texts)}
        if request.dimensions is not None:
            kwargs["dimensions"] = int(request.dimensions)
        if request.user is not None:
            kwargs["user"] = request.user
        try:
            resp = client.embeddings.create(**kwargs)
        except EmbeddingProviderError:
            raise
        except Exception as e:  # 供应商/网络错误 → fail-fast 定位
            raise EmbeddingProviderError(
                f"embedding 服务调用失败: {e}", code=EMB_SERVICE_ERROR
            ) from e

        items = list(resp.data)
        # 保序：响应项含 index 时按其排序（OpenAI 兼容语义），否则按返回顺序
        if items and getattr(items[0], "index", None) is not None:
            items = sorted(items, key=lambda it: int(it.index))
        vectors = [list(map(float, it.embedding)) for it in items]

        # 契约校验（fail-fast）
        if len(vectors) != len(request.texts):
            raise EmbeddingProviderError(
                f"embedding 响应数量不一致：请求 {len(request.texts)}，返回 {len(vectors)}。",
                code=EMB_BATCH_ORDER,
            )
        dims = {len(v) for v in vectors}
        if len(dims) != 1:
            raise EmbeddingProviderError(
                f"embedding 批内维度不一致：{sorted(dims)}。",
                code=EMB_DIMENSION_MISMATCH,
            )
        return vectors, model

    def _resolve_client(self, target_model: Optional[str]):
        if not self._base_url or not self._api_key or not self._model:
            raise EmbeddingProviderError(
                "embedding 配置缺失：未提供 base_url / api_key / model。"
                "请调用 set_config(...)，或 set_mock_mode() 进入 MOCK 模式。",
                code=EMB_CONFIG_MISSING,
            )
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise EmbeddingProviderError(
                    "未安装 'openai' 库，请运行 'pip install openai'。",
                    code=EMB_CONFIG_MISSING,
                ) from None
            try:
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                )
            except Exception as e:
                raise EmbeddingProviderError(
                    f"OpenAI 客户端初始化失败: {e}", code=EMB_SERVICE_ERROR
                ) from e
        model = target_model or self._model
        return self._client, model

    # ------------------------------------------------------------------ #
    # 横向读取 / 内省 / 探测
    # ------------------------------------------------------------------ #

    def get_retry(self) -> int:
        return DEFAULT_RETRY

    def get_current_call_info(self) -> Dict[str, Any]:
        return dict(self._call_info)

    def probe(self) -> str:
        """探测服务并返回类别标签（含实际维度）：mock 直接返回，live 发最小批。"""
        if self._mock:
            return f"embedding,mock,dim={self._mock_dim}"
        result = self.embed(EmbeddingRequest(texts=["探测"]))
        return f"embedding,{result.model},dim={result.dim}"

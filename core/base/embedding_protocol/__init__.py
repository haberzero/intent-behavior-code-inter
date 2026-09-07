"""``core.base.embedding_protocol`` —— embedding 调用层插件化的供应商无关契约包。

把 embedding 组件与内核解耦的核心契约层，位于 ``core/base``（最底层，只出不进）：

- :mod:`core.base.embedding_protocol.embedding_call` —— ``EmbeddingRequest`` /
  ``EmbeddingResult``：一次完整 embedding 调用请求/响应的结构化数据契约
  （不含供应商字段）。
- :mod:`core.base.embedding_protocol.provider`     —— ``EmbeddingProvider``：
  内核调 embedding 的抽象动作协议（供应商无关），实现对供应商细节封装。
- :mod:`core.base.embedding_protocol.recommended`   —— ``RecommendedEmbeddingProvider``：
  OpenAI 兼容 ``/v1/embeddings`` 推荐实现 + ``MOCK:VEC`` 确定性 mock（哈希派生
  向量，断言可判定）。
- :mod:`core.base.embedding_protocol.retrieval`     —— 检索最小闭包
  （``cosine`` + list 线性 top-k；语料/语域级候选召回，非单句判定）。
- :mod:`core.base.embedding_protocol.mock_scenario` —— ``MOCK:VEC`` 指令语言
  引擎（FIFO 场景队列 + 耗尽回落哈希派生，与 LLM mock 场景引擎同构）。

机制同构基准 = :mod:`core.base.llm_protocol`（五层：契约包 / provider 实现 /
模块面 / 配置单源 / 执行路径）。失败语义 → 诊断码：本包异常携带 ``code``
属性（``EMB_`` 域，``core.base.diagnostics.codes`` 单一权威源），语言层接线
时同码复用。
"""

from core.base.embedding_protocol.embedding_call import (
    EmbeddingRequest,
    EmbeddingResult,
)
from core.base.embedding_protocol.provider import EmbeddingProvider
from core.base.embedding_protocol.recommended import (
    DEFAULT_RETRY,
    MOCK_DEFAULT_DIM,
    EmbeddingProviderError,
    RecommendedEmbeddingProvider,
    mock_vector,
)
from core.base.embedding_protocol.retrieval import (
    RetrievalError,
    RetrievalHit,
    cosine,
    linear_topk,
    linear_topk_texts,
)
from core.base.embedding_protocol.mock_scenario import (
    EmbeddingMockEngine,
    EmbeddingMockScenario,
)

__all__ = [
    # embedding_call
    "EmbeddingRequest",
    "EmbeddingResult",
    # provider
    "EmbeddingProvider",
    # recommended
    "RecommendedEmbeddingProvider",
    "EmbeddingProviderError",
    "mock_vector",
    "MOCK_DEFAULT_DIM",
    "DEFAULT_RETRY",
    # retrieval（最小闭包：cosine + list 线性 top-k）
    "linear_topk",
    "linear_topk_texts",
    "cosine",
    "RetrievalHit",
    "RetrievalError",
    # mock_scenario（MOCK:VEC 指令语言）
    "EmbeddingMockEngine",
    "EmbeddingMockScenario",
]

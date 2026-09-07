"""``embedding_impl`` —— ai 模块的 embedding 服务面（宿主胶水 + 推荐实现包装）。

把 :class:`core.base.embedding_protocol` 推荐实现（批 ① 契约包）接入 ai 模块
用户面：配置（显式 / 命名模型 / api_config ``kind: "embedding"`` 条目）、
mock（``MOCK:VEC`` 确定性向量）、embed（str → vector / list → list[vector]
动态重载）、retrieve（检索最小闭包——线性 top-k）、内省（call_info）。

机制同构 = LLM 面（:mod:`provider_impl`）：
- 配置单源 = api_config（经 :class:`LLMConnectionConfig.embedding_models` 落地）；
- 显式 ``set_embedding_config`` / ``set_embedding_mock`` 对称开关；
- 失败语义 → 诊断码（``EMB_`` 域，契约包异常携带 code，语言层同码复用）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from core.base.diagnostics.codes import (
    EMB_CONFIG_MISSING,
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
)
from core.base.embedding_protocol import (
    EmbeddingMockEngine,
    EmbeddingRequest,
    RecommendedEmbeddingProvider,
    linear_topk,
)
from core.base.llm_protocol.config import LLMConnectionConfig, ModelSpec
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel.base import unbox


class EmbeddingService:
    """ai 模块 embedding 服务面（推荐实现包装 + 配置/mock/检索）。"""

    def __init__(self, registry):
        # registry = 内核 KernelRegistry（vector 值对象构造 + boxing 消费）
        self._registry = registry
        self._provider = RecommendedEmbeddingProvider()
        self._mock_engine = EmbeddingMockEngine()
        # 命名 embedding 模型（api_config embedding_models 条目 / 显式注册）
        self._named: Dict[str, Dict[str, Any]] = {}
        # 当前激活配置（set_embedding_config / set_embedding_model 落地）
        self._active: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ #
    # 配置面
    # ------------------------------------------------------------------ #

    def set_config(self, url: str, key: str, model: str, timeout: float = 30.0) -> None:
        """显式配置 embedding 连接（对称 LLM set_config；退出 mock 模式）。"""
        self._provider.set_config(
            base_url=url, api_key=key, model=model, timeout=timeout
        )
        self._active = {"url": url, "key": key, "model": model, "timeout": timeout}

    def register_model(
        self, name: str, url: str, key: str, model: str, timeout: float = 30.0
    ) -> None:
        """注册命名 embedding 模型（api_config embedding 条目 / 显式注册统一落地）。"""
        self._named[name] = {
            "url": url,
            "key": key,
            "model": model,
            "timeout": timeout,
        }

    def set_model(self, name: str) -> None:
        """选择当前激活的命名 embedding 模型（未注册 fail-fast）。"""
        config = self._named.get(name)
        if config is None:
            raise InterpreterError(
                f"未注册的 embedding 模型 '{name}'。请先经 api_config"
                "（kind: \"embedding\"）或 ai.register_embedding_model 注册。",
                error_code=EMB_CONFIG_MISSING,
            )
        self.set_config(
            config["url"], config["key"], config["model"], config["timeout"]
        )

    def apply_config(self, config: LLMConnectionConfig) -> None:
        """应用逻辑配置的 embedding 面（embedding_models 命名条目统一注册）。"""
        for name, spec in config.embedding_models.items():
            if not spec.endpoint or not spec.auth:
                raise InterpreterError(
                    f"embedding 模型 '{name}' 缺少 base_url/api_key",
                    error_code=EMB_CONFIG_MISSING,
                )
            self.register_model(
                name, spec.endpoint, spec.auth, spec.model_id,
                timeout=spec.timeout or 30.0,
            )

    # ------------------------------------------------------------------ #
    # mock 面（MOCK:VEC 确定性向量——测试断言可判定、零网络、零 key）
    # ------------------------------------------------------------------ #

    def set_mock_mode(self, enable: bool = True, dim: int = 128, seed: int = 0) -> None:
        """显式进入/退出 embedding MOCK 模式（哈希派生确定性向量）。"""
        if enable:
            self._provider.set_config(
                base_url="mock://embedding", api_key="mock", model="mock",
                mock_dim=dim, seed=seed,
            )
            self._provider.set_mock_mode(True)
            self._mock_engine.reset()
        else:
            # 退出 mock 需回到已配置连接（未配置 fail-fast，不静默悬空）
            if self._active is None:
                raise InterpreterError(
                    "embedding 无已配置连接，无法退出 MOCK 模式"
                    "（请先 set_embedding_config）",
                    error_code=EMB_CONFIG_MISSING,
                )
            self._provider.set_config(
                base_url=self._active["url"], api_key=self._active["key"],
                model=self._active["model"], timeout=self._active["timeout"],
            )
            self._provider.set_mock_mode(False)

    # ------------------------------------------------------------------ #
    # 契约动作（embed：str → vector / list → list[vector] 动态重载）
    # ------------------------------------------------------------------ #

    def embed(
        self,
        texts: Any,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> Any:
        """embedding 调用（批量保序；失败 fail-fast 携带 EMB_ 码）。

        - ``str`` 输入 → 单个 ``vector``（单文本 = 长度 1 批的用户面形态）；
        - ``list[str]`` 输入 → ``list[vector]``（批形态，与请求顺序对应）。

        参数形态：vtable 代理边界已拆箱（IbStr → str / IbList → native
        list）；直用 Python 调用时可能为 IbObject 原形——两态统一处理
        （single = 标量 str 输入 → 返回单个 vector）。
        """
        from core.runtime.objects.primitives.collections import IbList
        from core.runtime.objects.primitives.vector import IbVector

        if isinstance(texts, IbList):
            items = [unbox(e) for e in texts.elements]
            single = False
        else:
            nat = unbox(texts)
            if isinstance(nat, str):
                items = [nat]
                single = True
            elif isinstance(nat, (list, tuple)):
                items = list(nat)
                single = False
            else:
                raise InterpreterError(
                    f"TypeError: ai.embed 参数须为 str 或 list（收到 {type(nat).__name__}）",
                    error_code=EMB_INVALID_INPUT,
                )
        for it in items:
            if not isinstance(it, str):
                raise InterpreterError(
                    "TypeError: ai.embed 文本元素须为 str",
                    error_code=EMB_INVALID_INPUT,
                )

        target = model if model else (self._active and self._active.get("model"))
        request = EmbeddingRequest(
            texts=items, target_model=target, dimensions=dimensions
        )
        result = self._provider.embed(request)  # 失败经 EmbeddingProviderError 上抛

        vector_class = self._registry.get_class("vector")
        vectors = [IbVector(v, vector_class) for v in result.vectors]
        return vectors[0] if single else vectors

    # ------------------------------------------------------------------ #
    # 检索最小闭包（线性 top-k——语料/语域级候选召回，非单句判定）
    # ------------------------------------------------------------------ #

    def retrieve(
        self, query: Any, corpus: Any, k: int
    ) -> List[Dict[str, Any]]:
        """线性 top-k 检索（``[{"index": int, "score": float}, ...]``）。

        参数保留 IBCI 值对象原形（模块面 unbox_args=False——vector 的
        to_native 显式违约，unbox 通道不适用于值身份敏感参数）：

        - ``query``：vector（查询向量）；
        - ``corpus``：list[vector]（候选语料向量，经 elements 直读）；
        - ``k``：原生 int（AIPlugin 转发层已拆箱）。
        """
        from core.runtime.objects.primitives.vector import IbVector
        from core.runtime.objects.primitives.collections import IbList

        if not isinstance(query, IbVector):
            raise InterpreterError(
                f"TypeError: ai.retrieve 查询须为 vector（收到 {type(query).__name__}）",
                error_code=EMB_INVALID_INPUT,
            )
        if not isinstance(corpus, IbList):
            raise InterpreterError(
                "TypeError: ai.retrieve 语料须为 list[vector]",
                error_code=EMB_INVALID_INPUT,
            )
        corpus_vecs = list(corpus.elements)
        if not all(isinstance(v, IbVector) for v in corpus_vecs):
            raise InterpreterError(
                "TypeError: ai.retrieve 语料须为 list[vector]（含非 vector 元素）",
                error_code=EMB_INVALID_INPUT,
            )
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            raise InterpreterError(
                f"ai.retrieve k 须为正整数（收到 {k!r}）",
                error_code=EMB_INVALID_INPUT,
            )
        hits = linear_topk(list(query.payload), [list(v.payload) for v in corpus_vecs], k)
        return [
            {"index": hit.index, "score": hit.score} for hit in hits
        ]

    # ------------------------------------------------------------------ #
    # 内省
    # ------------------------------------------------------------------ #

    def get_call_info(self) -> Dict[str, Any]:
        """最近一次 embedding 调用的诊断信息（观测面）。"""
        return self._provider.get_current_call_info()

    def probe(self) -> str:
        """探测 embedding 服务/模型能力（含实际维度）。"""
        return self._provider.probe()

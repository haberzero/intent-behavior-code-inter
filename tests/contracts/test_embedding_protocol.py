"""
tests/contracts/test_embedding_protocol.py

embedding 契约包测试（PT-FEAT-16 批 ①）：契约数据面 + 推荐实现（mock/live
fail-fast）+ MOCK:VEC 指令引擎 + 检索最小闭包。

纪律：

- 全确定性：mock 路径（MOCK:VEC 哈希派生）零网络、零 key、可重复断言；
  live fail-fast 路径仅打 127.0.0.1 不可达端口（无外部流量）。
- 机制同构断言：契约不可变（frozen）、保序、维度一致、观测面、ABC 强制。
- 失败语义 → 诊断码判别：EmbeddingProviderError / RetrievalError 携带
  EMB_ 域码（``core.base.diagnostics.codes`` 单一权威源）。
"""

import math

import pytest

from core.base.diagnostics.codes import (
    EMB_BATCH_ORDER,
    EMB_CONFIG_MISSING,
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
    EMB_SERVICE_ERROR,
    EMB_ZERO_NORM,
)
from core.base.embedding_protocol import (
    EmbeddingMockEngine,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRequest,
    RetrievalError,
    RecommendedEmbeddingProvider,
    cosine,
    linear_topk,
    linear_topk_texts,
    mock_vector,
)


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# 契约数据面
# ---------------------------------------------------------------------------


class TestContractData:
    def test_request_frozen(self):
        r = EmbeddingRequest(texts=["甲", "乙"])
        with pytest.raises(AttributeError):
            r.texts = ["丙"]  # frozen dataclass

    def test_mock_shape(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        res = p.embed(EmbeddingRequest(texts=["甲", "乙", "丙", "丁", "戊"]))
        assert len(res.vectors) == 5, "批量保序：5 文本 → 5 向量"
        assert all(len(v) == 128 for v in res.vectors), "默认 mock 维度 128"
        assert res.dim == 128
        assert res.model == "mock"

    def test_mock_determinism(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        a = p.embed(EmbeddingRequest(texts=["苹果", "修炼"]))
        b = p.embed(EmbeddingRequest(texts=["苹果", "修炼"]))
        assert a.vectors == b.vectors, "同输入逐元素相等（断言可判定）"
        assert abs(_cos(a.vectors[0], b.vectors[0]) - 1.0) < 1e-9, "同向量 cos=1.0"

    def test_mock_order_binding(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        texts = ["第一句", "第二句", "第三句"]
        res = p.embed(EmbeddingRequest(texts=texts))
        for i, t in enumerate(texts):
            expect = mock_vector(t, 128, 0)
            assert res.vectors[i] == expect, f"vectors[{i}] 须对应 texts[{i}]（保序绑定）"

    def test_mock_distinctness(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        res = p.embed(EmbeddingRequest(texts=["苹果", "修炼", "老师"]))
        for i in range(3):
            for j in range(i + 1, 3):
                c = _cos(res.vectors[i], res.vectors[j])
                assert c < 0.999, f"不同文本向量须互异（cos={c}）"

    def test_mock_normalized(self):
        v = mock_vector("归一化检验", 64)
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-9, f"mock 向量须 L2 归一（norm={norm}）"

    def test_mock_dimensions_override(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        res = p.embed(EmbeddingRequest(texts=["维度覆盖"], dimensions=64))
        assert res.dim == 64 and len(res.vectors[0]) == 64

    def test_mock_seed_variants(self):
        p = RecommendedEmbeddingProvider()
        p.set_config("http://example.invalid", "k", "m", seed=1)
        p.set_mock_mode()
        a = p.embed(EmbeddingRequest(texts=["种子"]))
        p2 = RecommendedEmbeddingProvider()
        p2.set_config("http://example.invalid", "k", "m", seed=2)
        p2.set_mock_mode()
        b = p2.embed(EmbeddingRequest(texts=["种子"]))
        assert a.vectors != b.vectors, "不同种子 → 不同确定性向量"


# ---------------------------------------------------------------------------
# 行为契约（fail-fast / 观测面 / ABC / 码面）
# ---------------------------------------------------------------------------


class TestBehaviorContract:
    def test_empty_batch_fail_fast(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        with pytest.raises(EmbeddingProviderError) as exc:
            p.embed(EmbeddingRequest(texts=[]))
        assert exc.value.code == EMB_INVALID_INPUT

    def test_missing_config_fail_fast(self):
        p = RecommendedEmbeddingProvider()  # 未配置、非 mock
        with pytest.raises(EmbeddingProviderError) as exc:
            p.embed(EmbeddingRequest(texts=["x"]))
        assert "配置缺失" in str(exc.value)
        assert exc.value.code == EMB_CONFIG_MISSING

    def test_live_unreachable_fail_fast(self):
        p = RecommendedEmbeddingProvider()
        p.set_config("http://127.0.0.1:1", "test-key", "test-model", timeout=2.0)
        with pytest.raises(EmbeddingProviderError) as exc:
            p.embed(EmbeddingRequest(texts=["探测"]))
        assert exc.value.code == EMB_SERVICE_ERROR

    def test_call_info_observability(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        assert p.get_current_call_info() == {}, "调用前观测面为空"
        p.embed(EmbeddingRequest(texts=["观测面", "观测面二"]))
        info = p.get_current_call_info()
        assert info["n_texts"] == 2
        assert info["dim"] == 128
        assert info["model"] == "mock"
        assert info["mock"] is True
        assert info["latency_seconds"] >= 0.0

    def test_get_retry_default(self):
        p = RecommendedEmbeddingProvider()
        assert p.get_retry() == 2, "embedding 最小重试（无意图重试语义）"

    def test_abc_enforcement(self):
        class Incomplete(EmbeddingProvider):
            def get_retry(self):
                return 0

            def get_current_call_info(self):
                return {}

        with pytest.raises(TypeError):
            Incomplete()

    def test_probe_mock_label(self):
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        label = p.probe()
        assert label.startswith("embedding,mock,dim="), f"探测标签形态异常: {label}"


# ---------------------------------------------------------------------------
# MOCK:VEC 指令引擎
# ---------------------------------------------------------------------------


class TestMockScenarioEngine:
    def test_vec_deterministic(self):
        eng = EmbeddingMockEngine(default_seed=7)
        eng.vec()
        a = eng.next_vectors(3, 64)
        eng.vec()
        b = eng.next_vectors(3, 64)
        assert a == b, "同 seed VEC 场景逐批逐元素相等"

    def test_seq_ordering(self):
        eng = EmbeddingMockEngine()
        vectors = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        eng.seq(vectors)
        first_batch = eng.next_vectors(2, 2)
        second_batch = eng.next_vectors(1, 2)
        assert first_batch == vectors[:2]
        assert second_batch == vectors[2:], "SEQ 按批逐条对齐、跨调用持久"

    def test_seq_json_entry(self):
        eng = EmbeddingMockEngine()
        eng.seq_from_json("[[1.0, 0.0], [0.0, 1.0]]")
        out = eng.next_vectors(2, 2)
        assert out == [[1.0, 0.0], [0.0, 1.0]]

    def test_seq_dim_fail_fast(self):
        eng = EmbeddingMockEngine()
        eng.seq([[1.0, 0.0]])  # dim=2
        with pytest.raises(EmbeddingProviderError) as exc:
            eng.next_vectors(1, 4)  # 请求 dim=4 → 维度失配
        assert exc.value.code == EMB_DIMENSION_MISMATCH

    def test_fail_scenario(self):
        eng = EmbeddingMockEngine()
        eng.fail("注入故障")
        with pytest.raises(EmbeddingProviderError) as exc:
            eng.next_vectors(1, 4)
        assert "注入故障" in str(exc.value)

    def test_exhaustion_fallback(self):
        eng = EmbeddingMockEngine()
        eng.vec()
        a = eng.next_vectors(2, 32)
        b = eng.next_vectors(2, 32)  # 队列已耗尽 → 回落哈希派生默认
        assert a != b, "耗尽后回落 default 前缀派生（与 VEC 场景前缀不同）"

    def test_observability_and_reset(self):
        eng = EmbeddingMockEngine()
        eng.vec()
        eng.vec()
        eng.next_vectors(1, 8)
        assert eng.consumed == 1 and eng.has_pending()
        eng.next_vectors(1, 8)
        assert eng.consumed == 2 and not eng.has_pending()
        eng.vec()
        eng.reset()
        assert eng.consumed == 0 and not eng.has_pending()


# ---------------------------------------------------------------------------
# 检索最小闭包（cosine + 线性 top-k）
# ---------------------------------------------------------------------------


class TestRetrieval:
    def test_cosine_basics(self):
        assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
        assert abs(cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9
        assert abs(cosine([1.0, 0.0], [-1.0, 0.0]) + 1.0) < 1e-9

    def test_cosine_fail_fast(self):
        with pytest.raises(RetrievalError) as exc:
            cosine([1.0], [1.0, 0.0])  # 维度失配
        assert exc.value.code == EMB_DIMENSION_MISMATCH
        with pytest.raises(RetrievalError) as exc:
            cosine([0.0, 0.0], [1.0, 0.0])  # 零范数（fail-fast，非静默 0）
        assert exc.value.code == EMB_ZERO_NORM
        with pytest.raises(RetrievalError) as exc:
            cosine([float("nan")], [1.0])  # 非有限值
        assert exc.value.code == EMB_INVALID_INPUT
        with pytest.raises(RetrievalError) as exc:
            cosine([], [1.0])  # 空向量
        assert exc.value.code == EMB_INVALID_INPUT

    def test_topk_ordering(self):
        query = [1.0, 0.0]
        corpus = [[0.0, 1.0], [1.0, 1.0], [1.0, 0.0]]
        hits = linear_topk(query, corpus, 2)
        assert [h.index for h in hits] == [2, 1], "按 score 降序"
        assert hits[0].score >= hits[1].score

    def test_topk_k_larger_than_n_clamps(self):
        hits = linear_topk([1.0, 0.0], [[1.0, 0.0]], 5)
        assert len(hits) == 1, "k > n 显式钳制为 n"

    def test_topk_tie_stable_by_index(self):
        corpus = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
        hits = linear_topk([1.0, 0.0], corpus, 3)
        assert [h.index for h in hits] == [0, 1, 2], "并列按语料索引升序"

    def test_topk_fail_fast(self):
        with pytest.raises(RetrievalError) as exc:
            linear_topk([1.0, 0.0], [[1.0, 0.0]], 0)
        assert exc.value.code == EMB_INVALID_INPUT
        with pytest.raises(RetrievalError) as exc:
            linear_topk([1.0, 0.0], [], 1)  # 空语料
        assert exc.value.code == EMB_INVALID_INPUT
        with pytest.raises(RetrievalError) as exc:
            linear_topk([1.0, 0.0], [[1.0]], 1)  # 查询/语料维度失配
        assert exc.value.code == EMB_DIMENSION_MISMATCH

    def test_topk_determinism(self):
        corpus = [[0.1, 0.9], [0.9, 0.1], [0.5, 0.5]]
        a = linear_topk([1.0, 0.0], corpus, 2)
        b = linear_topk([1.0, 0.0], corpus, 2)
        assert a == b

    def test_topk_mock_semantic_sanity(self):
        # mock 派生向量的检索行为可测：同文本召回自身（相似度 1.0 居首）
        p = RecommendedEmbeddingProvider()
        p.set_mock_mode()
        res = p.embed(EmbeddingRequest(texts=["苹果", "修炼", "老师"]))
        hits = linear_topk(res.vectors[0], res.vectors, 3)
        assert hits[0].index == 0 and hits[0].score > 0.999

    def test_topk_texts_facade(self):
        corpus = [[1.0, 0.0], [0.0, 1.0]]
        out = linear_topk_texts([1.0, 0.0], corpus, ["甲", "乙"], 2)
        assert out[0] == (0, "甲", pytest.approx(1.0))
        with pytest.raises(RetrievalError) as exc:
            linear_topk_texts([1.0, 0.0], corpus, ["甲"], 1)  # 长度失配
        assert exc.value.code == EMB_INVALID_INPUT

    def test_hit_frozen(self):
        from core.base.embedding_protocol import RetrievalHit

        h = RetrievalHit(index=0, score=1.0)
        with pytest.raises(AttributeError):
            h.index = 1

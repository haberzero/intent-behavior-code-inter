"""
tests/runtime/test_knowledge_embedding.py

knowledge 向量面（词嵌入——内容信号非判定）判别测试（P6 F1）：

- **set_embedding 治理门**（fail-fast 不静默）：词未注册 = KNW_VOCAB_UNREGISTERED
  （复用）；维度与既有嵌入不一致 = KNW_EMB_DIM_MISMATCH；非数值向量 =
  KNW_EMB_DIM_MISMATCH；
- **embedding**：取回词嵌入（vector 值）；未挂 = KNW_EMB_NOT_SET；词未注册 =
  KNW_VOCAB_UNREGISTERED；
- **embed_search**：全嵌入词暴力 cosine 取前 k（内容信号）——排序（score 降序）
  + 确定性 tie-break（平手按词名）+ 同输入同输出（确定性）+ k 非法 =
  KNW_EMB_SEARCH_INVALID + k 超嵌入词数 = 返回全部（截断非违约）+ 无嵌入面 =
  KNW_EMB_NOT_SET；
- **embedding_dim** / **has_embedding**：维度查询 / 是否已挂；
- 嵌入面序列化 round-trip（collect/hydrate 保真）。

注：嵌入 = 内容信号（异常检测/语义对比用），从不做判定（D1：判定走图平面
确定性路径）——与 narrow_model.score 同定位。
"""

import math

import pytest

from core.kernel.issue import InterpreterError
from core.runtime.objects.primitives.knowledge import IbKnowledge
from core.runtime.objects.primitives.vector import IbVector
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


def _code_err(ex):
    assert isinstance(ex, InterpreterError), f"期望 InterpreterError，实际 {type(ex).__name__}"
    return ex.error_code


def _bootstrap(engine):
    engine.run_string("str _x = '1'", silent=True)
    return engine.registry.get_class("knowledge")


def _mk_kb(engine, words=("atom", "proton", "electron")):
    """构造带治理词表的 KB（嵌入面测试夹具）。"""
    kb = IbKnowledge(_bootstrap(engine))
    reg = engine.registry
    kb.register_word("atom", "原子", False, [], {"modern": {"form": "atom", "self_ref": "self"}})
    for w in words[1:]:
        kb.register_word(w, w, False, [], {})
    return kb


def _vec(engine, xs):
    """构造 vector 值（嵌入测试夹具）。"""
    return IbVector(xs, engine.registry.get_class("vector"))


class TestSetEmbeddingGate:
    def test_set_embedding_ok(self, engine):
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0]))
        assert kb.has_embedding("atom") is True

    def test_set_embedding_unregistered_word(self, engine):
        """词未注册 = KNW_VOCAB_UNREGISTERED（复用）。"""
        kb = _mk_kb(engine)
        with pytest.raises(InterpreterError) as exc:
            kb.set_embedding("nope", _vec(engine, [1.0, 0.0]))
        assert _code_err(exc.value) == "KNW_VOCAB_UNREGISTERED"

    def test_set_embedding_dim_mismatch(self, engine):
        """维度与既有嵌入不一致 = KNW_EMB_DIM_MISMATCH。"""
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0]))  # dim=2
        with pytest.raises(InterpreterError) as exc:
            kb.set_embedding("proton", _vec(engine, [1.0, 0.0, 0.0]))  # dim=3
        assert _code_err(exc.value) == "KNW_EMB_DIM_MISMATCH"

    def test_set_embedding_replace(self, engine):
        """挂/换：同词重挂（同维）= 替换（非错误）。"""
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0]))
        kb.set_embedding("atom", _vec(engine, [0.0, 1.0]))  # 替换
        emb = kb.embedding("atom")
        assert list(emb.elements) == [0.0, 1.0]


class TestEmbedding:
    def test_embedding_round_trip(self, engine):
        """embedding 取回 = 所挂向量（vector 值）。"""
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [0.3, 0.4]))
        emb = kb.embedding("atom")
        assert isinstance(emb, IbVector)
        assert list(emb.elements) == [0.3, 0.4]

    def test_embedding_not_set(self, engine):
        """未挂 = KNW_EMB_NOT_SET。"""
        kb = _mk_kb(engine)
        with pytest.raises(InterpreterError) as exc:
            kb.embedding("atom")
        assert _code_err(exc.value) == "KNW_EMB_NOT_SET"

    def test_embedding_unregistered_word(self, engine):
        """词未注册 = KNW_VOCAB_UNREGISTERED。"""
        kb = _mk_kb(engine)
        with pytest.raises(InterpreterError) as exc:
            kb.embedding("nope")
        assert _code_err(exc.value) == "KNW_VOCAB_UNREGISTERED"


class TestEmbedSearch:
    def _loaded(self, engine):
        kb = _mk_kb(engine)
        # atom≈proton（同向），electron 正交
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0]))
        kb.set_embedding("proton", _vec(engine, [0.9, 0.1]))
        kb.set_embedding("electron", _vec(engine, [0.0, 1.0]))
        return kb

    def test_search_ordering(self, engine):
        """cosine 排序：query=atom → atom 自身(1.0) 最相似，proton 次，electron 最远。"""
        kb = self._loaded(engine)
        res = kb.embed_search(_vec(engine, [1.0, 0.0]), 3)
        assert [r["word"] for r in res] == ["atom", "proton", "electron"]
        assert res[0]["score"] > res[1]["score"] > res[2]["score"]

    def test_search_deterministic_tiebreak(self, engine):
        """平手（cosine 相等）按词名升序（确定性 tie-break）。"""
        kb = _mk_kb(engine)
        # 三词同向（cosine 全 = 1.0，平手）→ 按词名升序
        for w in ("atom", "proton", "electron"):
            kb.set_embedding(w, _vec(engine, [1.0, 0.0]))
        res = kb.embed_search(_vec(engine, [1.0, 0.0]), 3)
        assert [r["word"] for r in res] == ["atom", "electron", "proton"]
        assert all(abs(r["score"] - 1.0) < 1e-12 for r in res)

    def test_search_same_input_same_output(self, engine):
        """确定性：同输入同输出（纯算术）。"""
        kb = self._loaded(engine)
        q = _vec(engine, [1.0, 0.0])
        assert kb.embed_search(q, 3) == kb.embed_search(q, 3)

    def test_search_k_exceeds_returns_all(self, engine):
        """k 超嵌入词数 = 返回全部（截断非违约）。"""
        kb = self._loaded(engine)
        assert len(kb.embed_search(_vec(engine, [1.0, 0.0]), 99)) == 3

    def test_search_invalid_k(self, engine):
        """k 非正整数 = KNW_EMB_SEARCH_INVALID。"""
        kb = self._loaded(engine)
        for bad in (0, -1, 1.5, "x", None):
            with pytest.raises(InterpreterError) as exc:
                kb.embed_search(_vec(engine, [1.0, 0.0]), bad)
            assert _code_err(exc.value) == "KNW_EMB_SEARCH_INVALID"

    def test_search_empty_embedding_plane(self, engine):
        """无嵌入面 = KNW_EMB_NOT_SET。"""
        kb = _mk_kb(engine)
        with pytest.raises(InterpreterError) as exc:
            kb.embed_search(_vec(engine, [1.0, 0.0]), 3)
        assert _code_err(exc.value) == "KNW_EMB_NOT_SET"

    def test_search_cosine_value(self, engine):
        """cosine 值正确性（对照手工计算）。"""
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0]))
        kb.set_embedding("electron", _vec(engine, [0.0, 1.0]))  # 正交 → cosine=0
        res = kb.embed_search(_vec(engine, [1.0, 0.0]), 2)
        by_word = {r["word"]: r["score"] for r in res}
        assert abs(by_word["atom"] - 1.0) < 1e-12     # 同向 → cosine=1
        assert abs(by_word["electron"] - 0.0) < 1e-12  # 正交 → cosine=0


class TestDimAndHas:
    def test_embedding_dim(self, engine):
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0, 0.0]))
        assert kb.embedding_dim() == 3

    def test_embedding_dim_empty(self, engine):
        """无嵌入 = KNW_EMB_NOT_SET。"""
        kb = _mk_kb(engine)
        with pytest.raises(InterpreterError) as exc:
            kb.embedding_dim()
        assert _code_err(exc.value) == "KNW_EMB_NOT_SET"

    def test_has_embedding(self, engine):
        kb = _mk_kb(engine)
        assert kb.has_embedding("atom") is False
        kb.set_embedding("atom", _vec(engine, [1.0, 0.0]))
        assert kb.has_embedding("atom") is True


class TestSerialization:
    def test_embedding_round_trip(self, engine):
        """嵌入面序列化 round-trip（collect/hydrate 保真）。"""
        kb = _mk_kb(engine)
        kb.set_embedding("atom", _vec(engine, [0.5, 0.5]))
        kb.set_embedding("proton", _vec(engine, [1.0, 0.0]))
        serializer = RuntimeSerializer(engine.registry)
        uid = serializer._collect_instance(kb)
        assert serializer.instance_pool[uid]["_type"] == "knowledge"
        assert serializer.instance_pool[uid]["embeddings"]["atom"] == [0.5, 0.5]
        deserializer = RuntimeDeserializer(engine.registry)
        deserializer.instance_pool = serializer.instance_pool
        obj = deserializer._get_instance(uid)
        assert isinstance(obj, IbKnowledge)
        assert obj.has_embedding("atom") is True
        # 推理面保真（round-trip 后 embed_search 结果一致）
        assert obj.embed_search(_vec(engine, [1.0, 0.0]), 2) == \
            kb.embed_search(_vec(engine, [1.0, 0.0]), 2)
        assert list(obj.embedding("atom").elements) == [0.5, 0.5]

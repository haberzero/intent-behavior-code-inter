"""
tests/runtime/test_narrow_model_type.py

narrow_model 内核原生值类型（R-D 推理时窄模型 = 冻结 KG 嵌入工件）判别测试：

- 值类型注册：``narrow_model`` 内核类 + 方法面 vtable 绑定（score/topk/元数据面）；
- 推理面算术正确性：``score(s,r,o)`` = TransE 距离（对照手工计算）；
  ``topk(s,r,k)`` = 全部候选按距离升序（确定性 tie-break = (距离, 实体名)）；
- 确定性：同输入同输出（纯算术，零训练）；
- 参考未注册词 fail-fast：s/o 未注册实体 = NAR_ENTITY_UNREGISTERED；
  r 未注册关系 = NAR_RELATION_UNREGISTERED；
- topk 参数门：k 非正整数 = NAR_TOPK_INVALID；k 超候选数 = 返回全部（非错误）；
- 元数据查询面：name/dim/entities/relations/architecture/content_hash；
- 不可变冻结工件：无修改面；deep_clone 引用复用（同 vector/run_result/quoted 纪律）；
- 空白构造 fail-fast（模型必经 world_model.bind_artifact 加载门）；
- to_native：原生结构快照（embedding 向量不共享内部引用）；
- 序列化 round-trip：save/load 全字段保真。

注：narrow_model 仅经 world_model.bind_artifact 水化构造（E2），无语言级构造
字面量——本测试 Python 侧直接构造 IbNarrowModel（载荷直传）验证值类型面。
engine fixture 每测试隔离，registry 首次 run 后 seal——``_bootstrap`` 每测试
仅触发一次。
"""

import math

from core.kernel.issue import InterpreterError
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.objects.primitives.narrow_model import IbNarrowModel
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


def _bootstrap(engine):
    """触发 bootstrap（每 engine 一次），返回 narrow_model 内核类引用。"""
    engine.run_string("str _x = '1'", silent=True)
    return engine.registry.get_class("narrow_model")


def _payload(dim=3):
    """确定性测试工件（TransE；3 实体 + 2 关系）。"""
    return {
        "model_name": "test_model",
        "architecture": "transe",
        "dim": dim,
        "entities": ["a", "b", "c"],
        "entity_embeddings": {
            "a": [1.0, 0.0, 0.0],
            "b": [2.0, 0.0, 0.0],
            "c": [0.0, 1.0, 0.0],
        },
        "relations": ["r1", "r2"],
        "relation_embeddings": {
            "r1": [1.0, 0.0, 0.0],
            "r2": [0.0, 0.0, 1.0],
        },
        "schema_version": 1,
        "content_hash": "0" * 64,
    }


def _mk(engine, cls=None, payload=None):
    """Python 侧构造 IbNarrowModel（载荷直传）。"""
    if cls is None:
        cls = _bootstrap(engine)
    if payload is None:
        payload = _payload()
    return IbNarrowModel(cls, payload=payload)


def _box(engine, v):
    return engine.registry.box(v)


def _transe(es, rr, eo):
    """手工 TransE 距离（测试对照基准）。"""
    return math.sqrt(sum((es[i] + rr[i] - eo[i]) ** 2 for i in range(len(es))))


class TestRegistration:
    def test_class_registered(self, engine):
        cls = _bootstrap(engine)
        assert cls is not None
        assert cls.name == "narrow_model"

    def test_methods_bound_via_vtable(self, engine):
        """方法面经 vtable 绑定（无参方法可分派；需参方法绑定存在）。"""
        nm = _mk(engine)
        # 无参方法直接分派
        assert nm.receive("dim", []).to_native() == 3
        assert nm.receive("name", []).to_native() == "test_model"
        # 需参方法绑定存在（可经 vtable 查得）
        for m in ("score", "topk"):
            method = nm.ib_class.lookup_method(m)
            assert method is not None, f"{m} 未绑定 vtable"


class TestScoreArithmetic:
    def test_score_transE_distance(self, engine):
        nm = _mk(engine)
        p = _payload()
        # score(a, r1, b) = ‖[1,0,0]+[1,0,0]-[2,0,0]‖ = 0
        d = nm.receive("score", [_box(engine, "a"), _box(engine, "r1"),
                                 _box(engine, "b")]).to_native()
        assert d == 0.0
        # score(a, r1, c) = ‖[1,0,0]+[1,0,0]-[0,1,0]‖ = ‖[2,-1,0]‖ = sqrt(5)
        d = nm.receive("score", [_box(engine, "a"), _box(engine, "r1"),
                                 _box(engine, "c")]).to_native()
        assert abs(d - math.sqrt(5)) < 1e-9
        # 对照手工基准（全三元组）
        for s in ("a", "b", "c"):
            for r in ("r1", "r2"):
                for o in ("a", "b", "c"):
                    got = nm.receive("score", [_box(engine, s), _box(engine, r),
                                               _box(engine, o)]).to_native()
                    want = _transe(p["entity_embeddings"][s],
                                   p["relation_embeddings"][r],
                                   p["entity_embeddings"][o])
                    assert abs(got - want) < 1e-9


class TestTopk:
    def test_topk_ordering(self, engine):
        nm = _mk(engine)
        # (a, r1) 下各候选距离：b=0.0, a=1.0, c=sqrt(5)≈2.236
        tk = nm.receive("topk", [_box(engine, "a"), _box(engine, "r1"),
                                 _box(engine, 3)]).to_native()
        assert [e["o"] for e in tk] == ["b", "a", "c"]
        assert abs(tk[0]["score"] - 0.0) < 1e-12
        assert abs(tk[1]["score"] - 1.0) < 1e-9
        assert abs(tk[2]["score"] - math.sqrt(5)) < 1e-9

    def test_topk_k_smaller_than_candidates(self, engine):
        nm = _mk(engine)
        tk = nm.receive("topk", [_box(engine, "a"), _box(engine, "r1"),
                                 _box(engine, 1)]).to_native()
        assert len(tk) == 1
        assert tk[0]["o"] == "b"

    def test_topk_k_exceeds_candidates_returns_all(self, engine):
        nm = _mk(engine)
        tk = nm.receive("topk", [_box(engine, "a"), _box(engine, "r1"),
                                 _box(engine, 99)]).to_native()
        assert len(tk) == 3  # 候选数（非 k=99）

    def test_topk_deterministic_tiebreak(self, engine):
        """距离相同时按实体名升序（确定性 tie-break）。"""
        p = {
            "model_name": "tie", "architecture": "transe", "dim": 2,
            "entities": ["z", "m", "a"],
            "entity_embeddings": {"z": [0.0, 0.0], "m": [0.0, 0.0],
                                  "a": [0.0, 0.0]},
            "relations": ["r"],
            "relation_embeddings": {"r": [0.0, 0.0]},
            "schema_version": 1, "content_hash": "1" * 64,
        }
        nm = _mk(engine, payload=p)
        tk = nm.receive("topk", [_box(engine, "z"), _box(engine, "r"),
                                 _box(engine, 3)]).to_native()
        # 全部距离 = ‖[0,0]+[0,0]-[0,0]‖ = 0（平）→ 按名字升序
        assert [e["o"] for e in tk] == ["a", "m", "z"]
        assert all(abs(e["score"]) < 1e-12 for e in tk)

    def test_topk_same_input_same_output(self, engine):
        """确定性：同输入同输出（纯算术零训练）。"""
        nm = _mk(engine)
        r1 = nm.receive("topk", [_box(engine, "a"), _box(engine, "r2"),
                                 _box(engine, 3)]).to_native()
        r2 = nm.receive("topk", [_box(engine, "a"), _box(engine, "r2"),
                                 _box(engine, 3)]).to_native()
        assert r1 == r2
        s1 = nm.receive("score", [_box(engine, "b"), _box(engine, "r1"),
                                  _box(engine, "a")]).to_native()
        s2 = nm.receive("score", [_box(engine, "b"), _box(engine, "r1"),
                                  _box(engine, "a")]).to_native()
        assert s1 == s2


class TestFailFast:
    def test_unregistered_entity_score(self, engine):
        nm = _mk(engine)
        try:
            nm.receive("score", [_box(engine, "a"), _box(engine, "r1"),
                                 _box(engine, "zzz")])
            raise AssertionError("应 fail-fast")
        except InterpreterError as e:
            assert e.error_code == "NAR_ENTITY_UNREGISTERED"

    def test_unregistered_relation(self, engine):
        nm = _mk(engine)
        try:
            nm.receive("score", [_box(engine, "a"), _box(engine, "zzz"),
                                 _box(engine, "b")])
            raise AssertionError("应 fail-fast")
        except InterpreterError as e:
            assert e.error_code == "NAR_RELATION_UNREGISTERED"

    def test_unregistered_entity_topk_subject(self, engine):
        nm = _mk(engine)
        try:
            nm.receive("topk", [_box(engine, "nope"), _box(engine, "r1"),
                                _box(engine, 2)])
            raise AssertionError("应 fail-fast")
        except InterpreterError as e:
            assert e.error_code == "NAR_ENTITY_UNREGISTERED"

    def test_topk_invalid_k_zero(self, engine):
        nm = _mk(engine)
        for bad in (0, -1, 1.5, "x", None):
            try:
                nm.receive("topk", [_box(engine, "a"), _box(engine, "r1"),
                                    _box(engine, bad)])
                raise AssertionError(f"k={bad!r} 应 fail-fast")
            except InterpreterError as e:
                assert e.error_code == "NAR_TOPK_INVALID"

    def test_blank_construct_fails(self, engine):
        """narrow_model() 空白构造 = fail-fast（必经 bind_artifact 加载门）。"""
        cls = _bootstrap(engine)
        try:
            IbNarrowModel(cls)
            raise AssertionError("应 fail-fast")
        except InterpreterError:
            pass


class TestMetadata:
    def test_metadata_surface(self, engine):
        nm = _mk(engine)
        assert nm.receive("name", []).to_native() == "test_model"
        assert nm.receive("dim", []).to_native() == 3
        assert nm.receive("entities", []).to_native() == ["a", "b", "c"]
        assert nm.receive("relations", []).to_native() == ["r1", "r2"]
        assert nm.receive("architecture", []).to_native() == "transe"
        assert nm.receive("content_hash", []).to_native() == "0" * 64

    def test_entities_returns_copy(self, engine):
        """元数据查询面返回副本（不暴露内部可变引用）。"""
        nm = _mk(engine)
        l1 = nm.receive("entities", []).to_native()
        l2 = nm.receive("entities", []).to_native()
        assert l1 == l2 and l1 is not l2


class TestImmutabilityAndNative:
    def test_no_mutation_surface(self, engine):
        """不可变冻结工件：无修改方法面（方法名不含 set/mut/add/push 等）。"""
        nm = _mk(engine)
        for m in ("set", "add", "mutate", "push", "append", "set_embedding"):
            assert not hasattr(nm, m), f"不应有修改面方法 {m}"

    def test_to_native_snapshot_independent(self, engine):
        """to_native 返回快照（embedding 向量不共享内部引用）。"""
        nm = _mk(engine)
        native = nm.to_native()
        native["entity_embeddings"]["a"][0] = 999.0
        # 内部 payload 不受影响
        assert nm.payload["entity_embeddings"]["a"][0] == 1.0

    def test_deep_clone_reference_reuse(self, engine):
        """不可变值类型：deep_clone = 引用复用（同 vector/run_result/quoted）。"""
        nm = _mk(engine)
        cloned = try_deep_clone(nm)
        assert cloned is nm

    def test_collect_native_structure(self, engine):
        """序列化 collect：_type=narrow_model + 全字段原生结构。"""
        nm = _mk(engine)
        serializer = RuntimeSerializer(engine.registry)
        data = {}
        serializer._collect_narrow_model(nm, data)
        assert data["_type"] == "narrow_model"
        assert data["model_name"] == "test_model"
        assert data["dim"] == 3
        assert data["entities"] == ["a", "b", "c"]
        assert data["entity_embeddings"]["a"] == [1.0, 0.0, 0.0]
        assert data["content_hash"] == "0" * 64

    def test_serialize_round_trip(self, engine):
        """序列化 round-trip：collect → hydrate 全字段保真（推理面一致）。"""
        nm = _mk(engine)
        serializer = RuntimeSerializer(engine.registry)
        uid = serializer._collect_instance(nm)
        assert uid in serializer.instance_pool
        assert serializer.instance_pool[uid]["_type"] == "narrow_model"
        deserializer = RuntimeDeserializer(engine.registry)
        deserializer.instance_pool = serializer.instance_pool
        obj = deserializer._get_instance(uid)
        assert isinstance(obj, IbNarrowModel), "round-trip 后须保真实现类"
        # 推理面保真（round-trip 后 score/topk 结果一致）
        a, b, r1 = _box(engine, "a"), _box(engine, "b"), _box(engine, "r1")
        assert obj.receive("score", [a, r1, b]).to_native() == \
            nm.receive("score", [a, r1, b]).to_native()
        assert obj.receive("topk", [a, r1, _box(engine, 3)]).to_native() == \
            nm.receive("topk", [a, r1, _box(engine, 3)]).to_native()
        assert obj.receive("content_hash", []).to_native() == "0" * 64

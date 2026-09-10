"""
tests/runtime/test_world_model_kb.py

knowledge 世界模型 KB 面（facts 事实日志 + vocab 治理词表 + 派生索引）判别测试
（B1 地基批：词表面 / 事实面 / 治理门 / 索引确定性 / 序列化 / 克隆）：

- **词表面**（register_word/relation/world + 查询）：allowlist 登记 + 重复
  fail-fast（KNW_VOCAB_EXISTS）+ 未注册查询 = null 合法态；
- **事实面**（add_fact/get_fact/facts/fact_len）：fact_id = str(KB seq)
  确定性；记录权威形态（含事件链）；
- **治理门**（内建确定性，零 LLM）：world/relation/s/o 未注册 =
  KNW_VOCAB_UNREGISTERED；重复 active 事实 = KNW_FACT_DUPLICATE；
  参数形态非法 = KNW_VOCAB_MALFORMED；
- **索引**（8 倒排，派生面）：active 视图 + 全日志视图；构造/水化确定性
  重建（同日志 → 同索引）；
- **序列化 round-trip**：facts/vocab 保真（索引不入快照，水化重建等价）；
- **deep_clone 独立**：KB 面深拷贝（克隆 A add_fact 不影响克隆 B）；
- **entries 面零回归**：既有 store/get/amend/history 契约不变。

注：B2（查找/对比/展开面）与 B3（retract/amend_fact 审计面）的判别测试
归后续批次文件段；本文件随批扩展。
"""

import pytest

from core.base.diagnostics.codes import (
    KNW_FACT_DUPLICATE,
    KNW_FACT_NOT_FOUND,
    KNW_VOCAB_EXISTS,
    KNW_VOCAB_MALFORMED,
    KNW_VOCAB_UNREGISTERED,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.primitives.knowledge import IbKnowledge
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


def _bootstrap(engine):
    """触发 bootstrap（每 engine 一次），返回 knowledge 内核类引用。"""
    engine.run_string("str _x = '1'", silent=True)
    return engine.registry.get_class("knowledge")


def _mk_kb(cls):
    """Python 侧构造空 KB。"""
    return IbKnowledge(cls)


def _register_micro_world(kb):
    """注册微型治理词表（测试夹具：1 世界 / 2 关系 / 3 词）。"""
    kb.register_world("modern", "现代物理世界", 3)
    kb.register_relation("composed_of", "组成关系", False, False)
    kb.register_relation("depends_on", "依赖关系", True, True)
    kb.register_word("atom", "原子", False, [], {})
    kb.register_word("proton", "质子", False, [], {})
    kb.register_word("electron", "电子", False, [], {})


def _code_err(ex):
    """提取 InterpreterError 的诊断码。"""
    assert isinstance(ex, InterpreterError), f"期望 InterpreterError，实际 {type(ex).__name__}"
    return ex.error_code


class TestVocabPlane:
    def test_register_and_query(self, engine):
        """词表登记 + 查询：记录形态完整（word/relation/world 面）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        w = kb.word("atom")
        assert w["lexeme"] == "atom" and w["gloss"] == "原子"
        assert w["is_set"] is False and w["members"] == [] and w["entries"] == {}
        r = kb.relation("depends_on")
        assert r["transitive"] is True and r["multi_valued"] is True
        wr = kb.world("modern")
        assert wr["size_rank"] == 3 and wr["description"] == "现代物理世界"

    def test_query_unregistered_is_null_not_error(self, engine):
        """未注册查询 = null 合法态（非错误——查询面与登记面语义分界）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        assert kb.word("quark") is None
        assert kb.relation("excites") is None
        assert kb.world("quantum") is None

    def test_enum_insertion_order_deterministic(self, engine):
        """枚举面确定性序 = 插入序（words/relations/worlds）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        assert kb.words() == ["atom", "proton", "electron"]
        assert kb.relations() == ["composed_of", "depends_on"]
        assert kb.worlds() == ["modern"]

    def test_duplicate_registration_fail_fast(self, engine):
        """词表重复注册 = fail-fast（KNW_VOCAB_EXISTS——词表单一权威源）。"""
        kb = _mk_kb(_bootstrap(engine))
        kb.register_world("modern", "现代物理世界", 3)
        with pytest.raises(InterpreterError) as exc:
            kb.register_world("modern", "现代物理世界", 3)
        assert _code_err(exc.value) == KNW_VOCAB_EXISTS
        kb.register_word("atom", "原子", False)
        with pytest.raises(InterpreterError) as exc2:
            kb.register_word("atom", "重复", False)
        assert _code_err(exc2.value) == KNW_VOCAB_EXISTS

    def test_malformed_args_fail_fast(self, engine):
        """参数形态非法 = fail-fast（KNW_VOCAB_MALFORMED，无静默默认）。"""
        kb = _mk_kb(_bootstrap(engine))
        with pytest.raises(InterpreterError) as exc:
            kb.register_word("", "空词", False)
        assert _code_err(exc.value) == KNW_VOCAB_MALFORMED
        with pytest.raises(InterpreterError) as exc2:
            kb.register_world("modern", "描述", 3.0)
        assert _code_err(exc2.value) == KNW_VOCAB_MALFORMED


class TestFactPlane:
    def test_add_fact_id_is_deterministic_seq(self, engine):
        """fact_id = str(KB seq)——确定性单调序号（同序列同 id）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        f1 = kb.add_fact("modern", "atom", "composed_of", "proton")
        f2 = kb.add_fact("modern", "atom", "composed_of", "electron")
        # seq 1 起（空白 KB 首事件 = 第 1 号）
        assert f1 == "1" and f2 == "2"

    def test_fact_record_authoritative_form(self, engine):
        """get_fact = 权威记录形态（全字段 + 事件链；KB 唯一权威读取口）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        f1 = kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")
        rec = kb.get_fact(f1)
        assert rec["id"] == f1
        assert (rec["world"], rec["s"], rec["r"], rec["o"]) == ("modern", "atom", "composed_of", "proton")
        assert rec["source"] == "v30" and rec["status"] == "active"
        assert rec["events"] == [{"seq": 1, "kind": "add", "reason": "", "new_o": None}]

    def test_get_fact_unknown_id_is_null(self, engine):
        """未知 fact_id = null 合法态（get 面查询语义，非错误）。"""
        kb = _mk_kb(_bootstrap(engine))
        assert kb.get_fact("999") is None

    def test_facts_order_and_len(self, engine):
        """facts() 全日志确定性序 = seq 序；fact_len 计数。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        a = kb.add_fact("modern", "atom", "composed_of", "proton")
        b = kb.add_fact("modern", "atom", "composed_of", "electron")
        assert [f["id"] for f in kb.facts()] == [a, b]
        assert kb.fact_len() == 2

    def test_governance_gate_unregistered_refs(self, engine):
        """治理门（内建确定性）：world/relation/s/o 未注册 = fail-fast。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        for code_arg in [
            ("quantum", "atom", "composed_of", "proton"),   # world 未注册
            ("modern", "atom", "excites", "proton"),        # relation 未注册
            ("modern", "quark", "composed_of", "proton"),   # s 未注册
            ("modern", "atom", "composed_of", "quark"),     # o 未注册
        ]:
            with pytest.raises(InterpreterError) as exc:
                kb.add_fact(*code_arg)
            assert _code_err(exc.value) == KNW_VOCAB_UNREGISTERED

    def test_duplicate_active_fact_fail_fast(self, engine):
        """同 (world,s,r,o) active 重复 = fail-fast（KNW_FACT_DUPLICATE，
        去重机器强制——非静默幂等）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        kb.add_fact("modern", "atom", "composed_of", "proton")
        with pytest.raises(InterpreterError) as exc:
            kb.add_fact("modern", "atom", "composed_of", "proton")
        assert _code_err(exc.value) == KNW_FACT_DUPLICATE
        # 同 (s,r) 不同 o 非重复（multi_valued 与否的矛盾判定归 B2 contradicts）
        other = kb.add_fact("modern", "atom", "composed_of", "electron")
        assert other is not None


class TestDerivedIndexes:
    def test_indexes_active_view_and_audit_view(self, engine):
        """索引形态：6 图索引（active 视图）+ by_source/by_status（全日志）；
        非 active 状态事实不入图索引（active 视图语义）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        f1 = kb.add_fact("modern", "atom", "composed_of", "proton", "src-a", "active")
        f2 = kb.add_fact("modern", "atom", "depends_on", "electron", "src-b", "proposed")
        idx = kb._indexes()
        # active 视图：f2（status=proposed）不在图索引
        assert idx["by_subject"]["atom"] == [f1]
        assert idx["by_pair"]["atom"]["composed_of"] == [f1]
        assert idx["by_triple"]["modern"]["atom"]["composed_of"]["proton"] == [f1]
        assert idx["by_world"]["modern"] == [f1]
        # 审计视图：全日志（含 proposed）
        assert idx["by_source"]["src-a"] == [f1]
        assert idx["by_source"]["src-b"] == [f2]
        assert idx["by_status"]["active"] == [f1]
        assert idx["by_status"]["proposed"] == [f2]

    def test_indexes_rebuild_deterministic_from_log(self, engine):
        """索引 = 日志的确定性派生：从同日志重建 → 同索引（单一权威源
        不变量的直接验证：索引永不独立存活）。"""
        kb = _mk_kb(_bootstrap(engine))
        _register_micro_world(kb)
        kb.add_fact("modern", "atom", "composed_of", "proton")
        kb.add_fact("modern", "atom", "depends_on", "electron")
        live = kb._indexes()
        rebuilt = IbKnowledge._build_indexes_from_facts(kb._facts())
        assert live == rebuilt


class TestSerializationRoundTrip:
    def test_kb_facts_vocab_round_trip(self, engine):
        """KB 面 save/load 保真：facts/vocab 全保真 + 索引水化重建等价
        （索引不入快照——派生面纪律）。"""
        # 经语言面构造 KB（register_*/add_fact 全 IBCI 代码路径；单 run_string
        # ——engine registry 首次 run 后 seal，不二次 run）
        code = (
            "kb = knowledge()\n"
            'kb.register_world("modern", "现代物理世界", 3)\n'
            'kb.register_relation("composed_of", "组成关系", False, False)\n'
            'kb.register_word("atom", "原子", False, [], {})\n'
            'kb.register_word("proton", "质子", False, [], {})\n'
            'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
        )
        engine.run_string(code, silent=True)
        ec = engine.interpreter.execution_context
        orig_ctx = ec.runtime_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            orig_ctx, include_static=False
        )
        restored = RuntimeDeserializer(
            engine.registry, factory=ec.factory
        ).deserialize_context(data)
        orig = orig_ctx.get_variable("kb")
        rest = restored.get_variable("kb")
        assert isinstance(rest, IbKnowledge)
        # KB 面保真（facts + vocab）
        assert rest._facts() == orig._facts()
        assert rest._vocab() == orig._vocab()
        assert rest.payload["seq"] == orig.payload["seq"]
        # 索引水化重建等价（派生面：同日志 → 同索引）
        assert rest._indexes() == orig._indexes()
        # entries 面同保真（零回归）
        assert rest.payload["entries"] == orig.payload["entries"]

    def test_old_snapshot_without_kb_planes_hydrates_as_empty_kb(self, engine):
        """快照缺 facts/vocab 节（KB 面引入前的旧快照）→ 水化为空 KB 面
        （结构性缺省，非兼容 shim——空日志是合法 KB 状态）。"""
        cls = _bootstrap(engine)
        from core.runtime.objects.primitives.knowledge import IbKnowledge
        payload = {"entries": {}, "seq": 7}  # 无 facts/vocab 节
        obj = IbKnowledge(cls, payload=payload)
        assert obj._facts() == {}
        assert obj._vocab() == {"words": {}, "relations": {}, "worlds": {}}
        assert obj._indexes()["by_subject"] == {}


class TestDeepCloneIndependence:
    def test_clone_kb_planes_independent(self, engine):
        """KB 面深拷贝：克隆 A 的 add_fact 不影响克隆 B（可变容器 = 引用
        语义，克隆须独立——facts/vocab 原生结构深拷贝）。"""
        cls = _bootstrap(engine)
        kb = _mk_kb(cls)
        _register_micro_world(kb)
        kb.add_fact("modern", "atom", "composed_of", "proton")
        cloned = try_deep_clone(kb)
        assert cloned is not None
        assert cloned._facts() == kb._facts()
        assert cloned._vocab() == kb._vocab()
        # 克隆 A 登记新事实 → 克隆 B 不变（独立性实证）
        cloned.add_fact("modern", "atom", "composed_of", "electron")
        assert kb.fact_len() == 1
        assert cloned.fact_len() == 2
        # 索引各自派生（A 的图索引含新事实，B 不含）
        assert cloned._indexes()["by_subject"]["atom"] == ["1", "2"]
        assert kb._indexes()["by_subject"]["atom"] == ["1"]


class TestEntriesPlaneZeroRegression:
    def test_store_get_amend_history_unchanged(self, engine):
        """entries 面既有契约零回归（KB 面扩展不改通用登记语义）。"""
        code = (
            "kb = knowledge()\n"
            "func ok(any x) -> bool:\n"
            "    return True\n"
            'kb.store("k1", 42, ok)\n'
            "print(kb.get(\"k1\"))\n"
            "print(kb.len())\n"
            'kb.amend("k1", 43, "更正值")\n'
            "print(kb.get(\"k1\"))\n"
            "print(len(kb.history(\"k1\")))\n"
        )
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        assert lines == ["42", "1", "43", "2"]

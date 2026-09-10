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


def _kb_with_chain(cls):
    """B2 测试夹具：微型 KB（传递链 atom -depends_on-> nucleus -depends_on->
    proton；composed_of 非传递非多值）。返回 (kb, f1..f4 fact_ids)。"""
    kb = IbKnowledge(cls)
    _register_micro_world(kb)
    kb.register_word("nucleus", "原子核", False, [], {})
    f1 = kb.add_fact("modern", "atom", "composed_of", "proton")
    f2 = kb.add_fact("modern", "atom", "composed_of", "electron")
    f3 = kb.add_fact("modern", "nucleus", "depends_on", "proton")
    f4 = kb.add_fact("modern", "atom", "depends_on", "nucleus")
    return kb, f1, f2, f3, f4


class TestLookupPlane:
    def test_lookup_pair_all_o(self, engine):
        """查找 1：s 经 r 指向什么——lookup_pair 返回全部 active 事实
        （确定性序 = seq 序；无事实 = 空 list 合法态）。"""
        cls = _bootstrap(engine)
        kb, f1, f2, _f3, _f4 = _kb_with_chain(cls)
        res = kb.lookup_pair("atom", "composed_of")
        assert [r["id"] for r in res] == [f1, f2]
        assert [r["o"] for r in res] == ["proton", "electron"]
        assert kb.lookup_pair("atom", "excites") == []

    def test_exists_dedup(self, engine):
        """查找 2：事实存在吗（by_triple 成员检查）——去重语义。"""
        cls = _bootstrap(engine)
        kb, f1, _f2, _f3, _f4 = _kb_with_chain(cls)
        assert kb.exists("modern", "atom", "composed_of", "proton") is True
        assert kb.exists("modern", "atom", "composed_of", "neutron") is False
        # 同 (s,r,o) 不同 world 非同一事实（by_triple 含 world 维）
        kb.register_world("quantum", "量子世界", 4)
        kb.add_fact("quantum", "atom", "composed_of", "proton")
        assert kb.exists("quantum", "atom", "composed_of", "proton") is True
        assert kb.exists("modern", "atom", "composed_of", "proton") is True

    def test_all_in_world(self, engine):
        """查找 3：某 world 的全部 active 事实。"""
        cls = _bootstrap(engine)
        kb, _f1, _f2, _f3, _f4 = _kb_with_chain(cls)
        res = kb.all_in_world("modern")
        assert len(res) == 4
        assert all(r["world"] == "modern" for r in res)
        assert kb.all_in_world("quantum") == []

    def test_by_source_audit_full_log(self, engine):
        """查找 4：某来源的全部事实（审计面——全日志视图）。"""
        cls = _bootstrap(engine)
        kb = _mk_kb(cls)
        _register_micro_world(kb)
        a = kb.add_fact("modern", "atom", "composed_of", "proton", "v30")
        b = kb.add_fact("modern", "atom", "composed_of", "electron", "v31")
        assert [f["id"] for f in kb.by_source("v30")] == [a]
        assert [f["id"] for f in kb.by_source("v31")] == [b]
        assert kb.by_source("v30") + kb.by_source("v31")  # 非空断言

    def test_by_subject_derived_not_stored(self, engine):
        """查找 7：关于某词的全部事实（**word.relations 的派生替代**——
        根治双写真相：词关系从不独立存储，只从事实日志派生）。"""
        cls = _bootstrap(engine)
        kb, f1, f2, _f3, f4 = _kb_with_chain(cls)
        res = kb.by_subject("atom")
        assert [r["id"] for r in res] == [f1, f2, f4]

    def test_contradicts_multi_valued_gate(self, engine):
        """查找 5：矛盾检查——同 (s,r) 不同 o 且关系非 multi_valued ⇒ 矛盾；
        multi_valued 关系恒非矛盾（治理词表元数据驱动）。"""
        cls = _bootstrap(engine)
        kb, _f1, _f2, _f3, _f4 = _kb_with_chain(cls)
        # 矛盾语义（试用方规格 §3.3-5）：新事实 (s,r,o') 加入时，by_pair[(s,r)]
        # 已有 o≠o' 且关系非 multi_valued ⇒ 矛盾。
        # composed_of 非 multi_valued，atom 已有 o={proton, electron}：
        # 新 o=neutron ≠ 既有 o → 矛盾
        assert kb.contradicts("atom", "composed_of", "neutron") is True
        # 单 o 的 (s,r) 且候选 o == 既有 o → 无冲突 o' → 非矛盾
        kb.add_fact("modern", "proton", "composed_of", "electron")
        assert kb.contradicts("proton", "composed_of", "electron") is False
        # 无既有事实的 (s,r) → 非矛盾
        assert kb.contradicts("electron", "composed_of", "proton") is False
        # depends_on 为 multi_valued（夹具）→ 恒非矛盾（同 (s,r) 允许多 o）
        assert kb.contradicts("atom", "depends_on", "electron") is False
        # 未注册关系 = fail-fast
        with pytest.raises(InterpreterError) as exc:
            kb.contradicts("atom", "excites", "proton")
        assert _code_err(exc.value) == KNW_VOCAB_UNREGISTERED

    def test_transitive_closure_chain(self, engine):
        """查找 6：传递闭包——沿 transitive 关系链展开（含直接；via =
        中间链；BFS 确定性序；防环）。"""
        cls = _bootstrap(engine)
        kb, _f1, _f2, _f3, _f4 = _kb_with_chain(cls)
        # atom -depends_on-> nucleus -depends_on-> proton（传递链）
        res = kb.transitive("atom", "depends_on")
        # BFS 发现序：直接目标 nucleus 先，再经 nucleus 到 proton
        assert res[0] == {"s": "atom", "r": "depends_on", "o": "nucleus", "via": []}
        assert res[1] == {"s": "atom", "r": "depends_on", "o": "proton", "via": ["nucleus"]}
        # 非传递关系 = 空 list（无传递闭包 = 空，非错误）
        assert kb.transitive("atom", "composed_of") == []
        # 无出边的主语 = 空 list
        assert kb.transitive("electron", "depends_on") == []
        # 未注册关系 = fail-fast
        with pytest.raises(InterpreterError) as exc:
            kb.transitive("atom", "excites")
        assert _code_err(exc.value) == KNW_VOCAB_UNREGISTERED

    def test_transitive_cycle_safe(self, engine):
        """传递闭包防环：环（a→b→a）不死循环，结果确定性。"""
        cls = _bootstrap(engine)
        kb = _mk_kb(cls)
        _register_micro_world(kb)
        kb.register_word("loop_a", "环A", False, [], {})
        kb.register_word("loop_b", "环B", False, [], {})
        kb.add_fact("modern", "loop_a", "depends_on", "loop_b")
        kb.add_fact("modern", "loop_b", "depends_on", "loop_a")
        res = kb.transitive("loop_a", "depends_on")
        # 可达：loop_b（直接）+ loop_a 经环回到自身 = 不入结果面（o == s 排除）
        assert [r["o"] for r in res] == ["loop_b"]
        assert res[0]["via"] == []


class TestCompareExpandPlane:
    def test_expand_deterministic_byte_identical(self, engine):
        """展开确定性：expand 纯派生（不存展开态）——多次调用原生结构
        逐字节一致（同输入同输出）。"""
        cls = _bootstrap(engine)
        kb, f1, _f2, _f3, _f4 = _kb_with_chain(cls)
        e1 = kb.expand(f1)
        e2 = kb.expand(f1)
        assert e1 == e2  # 原生 dict 深比较（全字段 + 嵌套记录 + 事件链）

    def test_expand_full_derivation(self, engine):
        """展开全字段：事实 + 主语/对象词记录 + 跨世界词形 + 关系语义 +
        世界上下文（存定理不存证明——展开态 = 日志 + 词表的确定性函数）。"""
        cls = _bootstrap(engine)
        kb = _mk_kb(cls)
        # 跨世界词形（跨尺度自指面）：atom 的 modern 词形 + self_ref
        kb.register_world("modern", "现代物理世界", 3)
        kb.register_relation("composed_of", "组成关系", False, False)
        kb.register_word("atom", "原子", False, [],
                         {"modern": {"form": "atom", "self_ref": "self"}})
        kb.register_word("proton", "质子", False, [], {})
        f1 = kb.add_fact("modern", "atom", "composed_of", "proton", "v30")
        e = kb.expand(f1)
        assert (e["id"], e["world"], e["s"], e["r"], e["o"]) == (f1, "modern", "atom", "composed_of", "proton")
        assert e["source"] == "v30" and e["status"] == "active"
        assert e["subject"]["gloss"] == "原子"
        assert e["object"]["gloss"] == "质子"
        assert e["subject_form"] == {"form": "atom", "self_ref": "self"}
        assert e["object_form"] == {}
        assert e["relation"]["semantics"] == "组成关系"
        assert e["world_ctx"]["size_rank"] == 3

    def test_expand_unknown_id_fail_fast(self, engine):
        """expand 未知 fact_id = fail-fast（KNW_FACT_NOT_FOUND）。"""
        cls = _bootstrap(engine)
        kb = _mk_kb(cls)
        with pytest.raises(InterpreterError) as exc:
            kb.expand("999")
        assert _code_err(exc.value) == KNW_FACT_NOT_FOUND

    def test_same_word_identity(self, engine):
        """词同一性（层 5）：lexeme 相等且均注册 = 真；未注册 = false
        （非错误——词同一性以治理词表为权威）。"""
        cls = _bootstrap(engine)
        kb = _mk_kb(cls)
        _register_micro_world(kb)
        assert kb.same_word("atom", "atom") is True
        assert kb.same_word("atom", "proton") is False
        assert kb.same_word("quark", "quark") is False  # 未注册 = 非词

    def test_compare_four_layers(self, engine):
        """对比 4 层（1/2/3/5；层 4 语义相似归向量面不预置）：
        exact / contradiction / scale / same_word 各判别。"""
        cls = _bootstrap(engine)
        kb, f1, f2, _f3, _f4 = _kb_with_chain(cls)
        # f1=(modern,atom,composed_of,proton) vs f2=(modern,atom,composed_of,electron)
        c = kb.compare(f1, f2)
        assert c["exact"] is False
        assert c["contradiction"] is True   # 同 (s,r) 不同 o 且非 multi_valued
        assert c["scale"] == "same"         # 同 world
        assert c["same_word"] is True       # s 词同一
        # 自身对比 = exact
        c_self = kb.compare(f1, f1)
        assert c_self["exact"] is True and c_self["contradiction"] is False
        # 跨 world = scale cross
        kb.register_world("quantum", "量子世界", 4)
        f5 = kb.add_fact("quantum", "atom", "composed_of", "proton")
        c_cross = kb.compare(f1, f5)
        assert c_cross["scale"] == "cross"
        assert c_cross["exact"] is False
        # 未知 id = fail-fast
        with pytest.raises(InterpreterError) as exc:
            kb.compare(f1, "999")
        assert _code_err(exc.value) == KNW_FACT_NOT_FOUND


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

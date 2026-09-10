"""
tests/runtime/test_knowledge_to_ibci.py

knowledge 投影面（to_ibci——KB 当前态的确定性 IBCI 代码派生视图）判别测试
（P7 G1）：

- **确定性**：同 KB 两次 to_ibci 逐字节一致（派生视图可复现）；
- **有效性**：投影代码编译 + 执行无错（合法 IBCI）；
- **对拍（R-F 验收面）**：新引擎执行投影代码 → 取回重建 KB → 语义查询结果
  与原 KB 一致（lookup_pair/exists/by_subject/contradicts/transitive/facts
  语义字段 world/s/r/o/source/status）；
- **全词汇/全事实投影**（active + retracted 均含，无 lossy——替代 stopgap 静默
  丢事实）；
- **retracted 事实投影**（status="retracted" 保真——当前态视图）。

注：to_ibci = 派生视图（非存储层）——单一权威源 = 活 KB / artifact；当前态
投影（非全史回放——amend 原始 o 不可恢复）；只读导出无新诊断码。
"""

from core.engine import IBCIEngine
from core.runtime.objects.primitives.knowledge import IbKnowledge


def _bootstrap(engine):
    engine.run_string("str _x = '1'", silent=True)
    return engine.registry.get_class("knowledge")


def _mk_kb_full(engine):
    """构造完整 KB（含 retracted 事实 + 传递关系——对拍夹具）。"""
    kb = IbKnowledge(_bootstrap(engine))
    kb.register_world("modern", "现代物理世界", 3)
    kb.register_relation("composed_of", "组成关系", False, False)
    kb.register_relation("depends_on", "依赖关系", True, False)
    kb.register_word("atom", "原子", False, [],
                     {"modern": {"form": "atom", "self_ref": "self"}})
    kb.register_word("proton", "质子", False, [], {})
    kb.register_word("electron", "电子", False, [], {})
    kb.register_word("nucleus", "原子核", False, [], {})
    # 2 active 事实
    kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")
    kb.add_fact("modern", "atom", "composed_of", "electron", "v30", "active")
    # 1 retracted 事实（当前态含 status=retracted）
    fid = kb.add_fact("modern", "nucleus", "depends_on", "proton", "v29", "active")
    kb.retract(fid, "deprecated")
    return kb


def _execute_projection(engine, code):
    """执行投影代码（新引擎）→ 取回重建 KB。"""
    engine.run_string(code, silent=True)
    return engine.interpreter.execution_context.runtime_context.get_variable("kb")


def _facts_semantic(kb):
    """事实语义视图（world/s/r/o/source/status 集合——忽略 fact_id 回放派生量）。"""
    return sorted(
        (f["world"], f["s"], f["r"], f["o"], f["source"], f["status"])
        for f in kb.facts()
    )


class TestDeterminism:
    def test_same_kb_byte_identical(self, engine):
        """同 KB 两次 to_ibci 逐字节一致（确定性派生视图）。"""
        kb = _mk_kb_full(engine)
        assert kb.to_ibci() == kb.to_ibci()

    def test_across_engines_identical(self, engine):
        """两引擎构造同 KB → to_ibci 逐字节一致。"""
        kb1 = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        kb2 = _mk_kb_full(e2)
        assert kb1.to_ibci() == kb2.to_ibci()


class TestValidity:
    def test_projection_compiles_and_runs(self, engine):
        """投影代码编译 + 执行无错（合法 IBCI）。"""
        kb = _mk_kb_full(engine)
        code = kb.to_ibci()
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, code)
        assert isinstance(restored, IbKnowledge)
        assert restored.fact_len() == kb.fact_len()

    def test_projection_ends_with_kb_value(self, engine):
        """投影代码末尾裸 kb（可求值为重建 KB）。"""
        kb = _mk_kb_full(engine)
        code = kb.to_ibci()
        assert code.strip().splitlines()[-1] == "kb"
        assert code.startswith("kb = knowledge()") or "kb = knowledge()" in code


class TestCrossCheck:
    def test_lookup_pair_matches(self, engine):
        """对拍：lookup_pair 语义结果一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        for s, r in (("atom", "composed_of"), ("nucleus", "depends_on")):
            orig = [(f["world"], f["s"], f["r"], f["o"]) for f in kb.lookup_pair(s, r)]
            rest = [(f["world"], f["s"], f["r"], f["o"])
                    for f in restored.lookup_pair(s, r)]
            assert sorted(orig) == sorted(rest), (s, r)

    def test_exists_matches(self, engine):
        """对拍：exists 语义结果一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        cases = [
            ("modern", "atom", "composed_of", "proton"),
            ("modern", "atom", "composed_of", "electron"),
            ("modern", "nucleus", "depends_on", "proton"),  # retracted → exists False
            ("modern", "atom", "composed_of", "nucleus"),   # 不存在 → False
        ]
        for w, s, r, o in cases:
            assert kb.exists(w, s, r, o) == restored.exists(w, s, r, o), (w, s, r, o)

    def test_by_subject_matches(self, engine):
        """对拍：by_subject 语义结果一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        for s in ("atom", "nucleus"):
            orig = sorted((f["r"], f["o"]) for f in kb.by_subject(s))
            rest = sorted((f["r"], f["o"]) for f in restored.by_subject(s))
            assert orig == rest, s

    def test_contradicts_matches(self, engine):
        """对拍：contradicts 语义结果一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        # atom composed_of 有 proton + electron（多值？composed_of multi_valued=False）
        for s, r, o in (("atom", "composed_of", "proton"),
                        ("atom", "composed_of", "electron")):
            assert kb.contradicts(s, r, o) == restored.contradicts(s, r, o)

    def test_transitive_matches(self, engine):
        """对拍：transitive（depends_on 传递闭包）语义结果一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        for s, r in (("nucleus", "depends_on"), ("atom", "composed_of")):
            orig = sorted((x["o"], tuple(x["via"])) for x in kb.transitive(s, r))
            rest = sorted((x["o"], tuple(x["via"])) for x in restored.transitive(s, r))
            assert orig == rest, (s, r)

    def test_facts_semantic_matches(self, engine):
        """对拍：facts 语义字段（world/s/r/o/source/status）全一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        assert _facts_semantic(kb) == _facts_semantic(restored)

    def test_vocab_matches(self, engine):
        """对拍：词表（words/relations/worlds）一致。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        assert kb.words() == restored.words()
        assert kb.relations() == restored.relations()
        assert kb.worlds() == restored.worlds()


class TestFullProjection:
    def test_retracted_fact_projected(self, engine):
        """retracted 事实投影（当前态含 status=retracted，无 lossy）。"""
        kb = _mk_kb_full(engine)
        code = kb.to_ibci()
        # retracted 事实的 add_fact 以 status="retracted" 投影
        assert '"retracted"' in code
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, code)
        # 重建 KB 含该 retracted 事实（facts 全日志视图）
        sem = _facts_semantic(restored)
        assert ("modern", "nucleus", "depends_on", "proton", "v29", "retracted") in sem

    def test_all_facts_present(self, engine):
        """全事实投影（active + retracted 均含，无 stopgap 静默丢失）。"""
        kb = _mk_kb_full(engine)
        e2 = IBCIEngine(root_dir="tests")
        restored = _execute_projection(e2, kb.to_ibci())
        assert restored.fact_len() == kb.fact_len() == 3

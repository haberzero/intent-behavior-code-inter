"""语言行为层：knowledge 世界模型 KB 面（R3-C7a 迁移——原 test_world_model_kb.py
Vocab/Fact 平面 → 可观察断言面[数据面输出 + 诊断码 + 现场位置]）。

**迁移映射**：词表登记/查询 + 枚举序 + fact_id 确定性 + get_fact 权威形态 +
facts 序 + 治理门（重复登记/参数形态/未注册引用/重复事实——KNW_ 码 + 定位）
→ 数据面 + 诊断码断言。索引/序列化/deep_clone 平面 = 后续切片（C7b）。

注：KB 源经 kb_vec_payload_materialization 角路由 Python（行为测试现 = Python
验证契约；⑦ 终点角移除后 Rust 验证——Rust kb.rs 治理门已对齐[GAP 关闭]）。
"""

from tests.behavior.helpers import assert_error, assert_output

_MICRO = (
    "k = knowledge()\n"
    'k.register_world("modern", "现代物理世界", 3)\n'
    'k.register_relation("composed_of", "组成关系", False, False)\n'
    'k.register_relation("depends_on", "依赖关系", True, True)\n'
    'k.register_word("atom", "原子", False, [], {})\n'
    'k.register_word("proton", "质子", False, [], {})\n'
    'k.register_word("electron", "电子", False, [], {})\n'
)


class TestVocabPlane:
    def test_register_and_query(self):
        """词表登记 + 查询：记录形态完整（word/relation/world 面）。"""
        assert_output(
            _MICRO
            + 'w = k.word("atom")\n'
            "print(w['lexeme'] + '|' + w['gloss'])\n"
            "print(w['is_set'])\n"
            'print(k.relation("composed_of")["transitive"])\n'
            'print(k.relation("depends_on")["multi_valued"])\n'
            'print(k.world("modern")["size_rank"])\n',
            ["atom|原子", "False", "False", "True", "3"],
        )

    def test_query_unregistered_is_null_not_error(self):
        """未注册查询 = null 合法态（查询面与登记面语义分界）。"""
        assert_output(
            _MICRO
            + "print(k.word('quark') == None)\n"
            "print(k.relation('excites') == None)\n"
            "print(k.world('quantum') == None)\n",
            ["True", "True", "True"],
        )

    def test_enum_insertion_order_deterministic(self):
        """枚举面确定性序 = 插入序（words/relations/worlds）。"""
        assert_output(
            _MICRO
            + "print(len(k.words()))\n"
            "print(k.words()[0])\n"
            "print(k.words()[1])\n"
            "print(k.words()[2])\n"
            "print(len(k.relations()))\n"
            "print(k.relations()[0])\n"
            "print(k.relations()[1])\n"
            "print(len(k.worlds()))\n"
            "print(k.worlds()[0])\n",
            ["3", "atom", "proton", "electron", "2", "composed_of", "depends_on", "1", "modern"],
        )

    def test_duplicate_registration_fail_fast(self):
        """词表重复登记 = fail-fast（KNW_VOCAB_EXISTS——词表单一权威源）。"""
        assert_error(
            'k = knowledge()\n'
            'k.register_world("modern", "现代物理世界", 3)\n'
            'k.register_world("modern", "现代物理世界", 3)\n',
            "KNW_VOCAB_EXISTS",
            line=3,
        )
        assert_error(
            'k = knowledge()\n'
            'k.register_word("atom", "原子", False)\n'
            'k.register_word("atom", "重复", False)\n',
            "KNW_VOCAB_EXISTS",
            line=3,
        )

    def test_malformed_args_fail_fast(self):
        """参数形态非法 = fail-fast（KNW_VOCAB_MALFORMED，无静默默认）。"""
        assert_error(
            'k = knowledge()\nk.register_word("", "空词", False)\n',
            "KNW_VOCAB_MALFORMED",
            line=2,
        )


class TestFactPlane:
    def test_add_fact_id_is_deterministic_seq(self):
        """fact_id = str(KB seq)——确定性单调序号（同序列同 id）。"""
        assert_output(
            _MICRO
            + 'f1 = k.add_fact("modern", "atom", "composed_of", "proton")\n'
            + 'f2 = k.add_fact("modern", "atom", "composed_of", "electron")\n'
            + 'print(f1 + "|" + f2)\n',
            ["1|2"],
        )

    def test_fact_record_authoritative_form(self):
        """get_fact = 权威记录形态（全字段 + 事件链；KB 唯一权威读取口）。"""
        assert_output(
            _MICRO
            + 'f1 = k.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
            + 'rec = k.get_fact(f1)\n'
            + "print(rec['id'] + '|' + rec['world'] + '|' + rec['s'] + '|' + rec['r'] + '|' + rec['o'])\n"
            + "print(rec['source'] + '|' + rec['status'])\n"
            + "print(len(rec['events']))\n",
            ["1|modern|atom|composed_of|proton", "v30|active", "1"],
        )

    def test_get_fact_unknown_id_is_null(self):
        """未知 fact_id = null 合法态（get 面查询语义，非错误）。"""
        assert_output(
            'k = knowledge()\nprint(k.get_fact("999") == None)\n',
            ["True"],
        )

    def test_facts_order_and_len(self):
        """facts() 全日志确定性序 = seq 序；fact_len 计数。"""
        assert_output(
            _MICRO
            + 'a = k.add_fact("modern", "atom", "composed_of", "proton")\n'
            + 'b = k.add_fact("modern", "atom", "composed_of", "electron")\n'
            + "print(len(k.facts()))\n"
            + "print(k.facts()[0]['id'] + '|' + k.facts()[1]['id'])\n"
            + "print(k.fact_len())\n",
            ["2", "1|2", "2"],
        )

    def test_governance_gate_unregistered_refs(self):
        """治理门（内建确定性）：world/relation/s/o 未注册 = fail-fast。"""
        for fact_args, _label in [
            ('"quantum", "atom", "composed_of", "proton"', "world 未注册"),
            ('"modern", "atom", "excites", "proton"', "relation 未注册"),
            ('"modern", "quark", "composed_of", "proton"', "s 未注册"),
            ('"modern", "atom", "composed_of", "quark"', "o 未注册"),
        ]:
            assert_error(
                _MICRO + f'k.add_fact({fact_args})\n',
                "KNW_VOCAB_UNREGISTERED",
                line=8,
            )

    def test_duplicate_active_fact_fail_fast(self):
        """同 (world,s,r,o) active 重复 = fail-fast（KNW_FACT_DUPLICATE，
        去重机器强制——非静默幂等）。"""
        assert_error(
            _MICRO
            + 'k.add_fact("modern", "atom", "composed_of", "proton")\n'
            + 'k.add_fact("modern", "atom", "composed_of", "proton")\n',
            "KNW_FACT_DUPLICATE",
            line=9,
        )
        # 同 (s,r) 不同 o 非重复（multi_valued 与否的矛盾判定归 contradicts）
        assert_output(
            _MICRO
            + 'k.add_fact("modern", "atom", "composed_of", "proton")\n'
            + 'f2 = k.add_fact("modern", "atom", "composed_of", "electron")\n'
            + "print(f2)\n",
            ["2"],
        )

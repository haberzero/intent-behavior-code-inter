"""语言行为层：knowledge 世界模型 KB 面（R3-C7b 迁移——原 test_world_model_kb.py
查找/对比/展开/审计/deep_clone/entries 平面 → 可观察断言面）。

**迁移映射**：lookup_pair/exists/all_in_world/contradicts/transitive/by_source/
by_subject（查找）+ expand/same_word/compare（对比展开）+ retract/amend_fact/
source/history_fact（审计）+ deepcopy 独立（克隆）+ store/get/amend/history
零回归（entries）→ 数据面 + 诊断码断言。索引结构（_indexes 内部形态）与
legacy 序列化 round-trip = 内部/⑦ 路径删除（契约 = 查询面[active vs 全日志]
+ Rust artifact 契约面，见迁移表）。
"""

from tests.behavior.helpers import assert_error, assert_output

_CHAIN = (
    "k = knowledge()\n"
    'k.register_world("modern", "现代物理世界", 3)\n'
    'k.register_relation("composed_of", "组成关系", False, False)\n'
    'k.register_relation("depends_on", "依赖关系", True, True)\n'
    'k.register_word("atom", "原子", False, [], {})\n'
    'k.register_word("proton", "质子", False, [], {})\n'
    'k.register_word("electron", "电子", False, [], {})\n'
    'k.register_word("nucleus", "原子核", False, [], {})\n'
    'f1 = k.add_fact("modern", "atom", "composed_of", "proton")\n'
    'f2 = k.add_fact("modern", "atom", "composed_of", "electron")\n'
    'f3 = k.add_fact("modern", "nucleus", "depends_on", "proton")\n'
    'f4 = k.add_fact("modern", "atom", "depends_on", "nucleus")\n'
)



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


class TestLookupPlane:
    def test_lookup_pair_all_o(self):
        """s 经 r 指向什么——lookup_pair 返回全部 active 事实（确定性序）。"""
        assert_output(
            _CHAIN
            + "print(len(k.lookup_pair('atom', 'composed_of')))\n"
            + "print(k.lookup_pair('atom', 'composed_of')[0]['o'])\n"
            + "print(k.lookup_pair('atom', 'composed_of')[1]['o'])\n"
            + "print(len(k.lookup_pair('atom', 'excites')))\n",
            ["2", "proton", "electron", "0"],
        )

    def test_exists_dedup(self):
        """事实存在吗（by_triple 成员检查）——去重语义。"""
        assert_output(
            _CHAIN
            + "print(k.exists('modern', 'atom', 'composed_of', 'proton'))\n"
            + "print(k.exists('modern', 'atom', 'composed_of', 'neutron'))\n"
            + "k.register_world('quantum', '量子世界', 4)\n"
            + "k.add_fact('quantum', 'atom', 'composed_of', 'proton')\n"
            + "print(k.exists('quantum', 'atom', 'composed_of', 'proton'))\n"
            + "print(k.exists('modern', 'atom', 'composed_of', 'proton'))\n",
            ["True", "False", "True", "True"],
        )

    def test_all_in_world(self):
        """某 world 的全部 active 事实。"""
        assert_output(
            _CHAIN
            + "print(len(k.all_in_world('modern')))\n"
            + "print(k.all_in_world('modern')[0]['world'])\n"
            + "print(len(k.all_in_world('quantum')))\n",
            ["4", "modern", "0"],
        )

    def test_by_subject_derived_not_stored(self):
        """关于某词的全部事实（word.relations 的派生替代——根治双写真相）。"""
        assert_output(
            _CHAIN + "print(len(k.by_subject('atom')))\nprint(k.by_subject('atom')[0]['id'])\n",
            ["3", "1"],
        )

    def test_by_source_audit_full_log(self):
        """某来源的全部事实（审计面——全日志视图）。"""
        assert_output(
            _CHAIN
            + "a5 = k.add_fact('modern', 'atom', 'depends_on', 'proton', 'v30-fly')\n"
            + "print(k.source('1') + '|' + k.source(a5))\n"
            + "print(k.by_source('v30-fly')[0]['id'])\n"
            + "print(len(k.by_source('nonexistent')))\n",
            ["|v30-fly", "5", "0"],
        )

    def test_contradicts_multi_valued_gate(self):
        """矛盾检查——同 (s,r) 不同 o 且关系非 multi_valued ⇒ 矛盾。"""
        assert_output(
            _CHAIN
            + "print(k.contradicts('atom', 'composed_of', 'neutron'))\n"
            + "k.add_fact('modern', 'proton', 'composed_of', 'electron')\n"
            + "print(k.contradicts('proton', 'composed_of', 'electron'))\n"
            + "print(k.contradicts('electron', 'composed_of', 'proton'))\n"
            + "print(k.contradicts('atom', 'depends_on', 'electron'))\n",
            ["True", "False", "False", "False"],
        )
        # 未注册关系 = fail-fast
        assert_error(
            _CHAIN + "print(k.contradicts('atom', 'excites', 'proton'))\n",
            "KNW_VOCAB_UNREGISTERED",
            line=13,
        )

    def test_transitive_closure_chain(self):
        """传递闭包——沿 transitive 关系链展开（含直接；via = 中间链）。"""
        assert_output(
            _CHAIN
            + "t = k.transitive('atom', 'depends_on')\n"
            + "print(len(t))\n"
            + "print(t[0]['o'] + '|' + str(len(t[0]['via'])))\n"
            + "print(t[1]['o'] + '|' + t[1]['via'][0])\n"
            + "print(len(k.transitive('atom', 'composed_of')))\n"
            + "print(len(k.transitive('electron', 'depends_on')))\n",
            ["2", "nucleus|0", "proton|nucleus", "0", "0"],
        )
        assert_error(
            _CHAIN + "print(k.transitive('atom', 'excites'))\n",
            "KNW_VOCAB_UNREGISTERED",
            line=13,
        )

    def test_transitive_cycle_safe(self):
        """传递闭包防环：环（a→b→a）不死循环，结果确定性。"""
        assert_output(
            _CHAIN
            + "k.register_word('loop_a', '环A', False, [], {})\n"
            + "k.register_word('loop_b', '环B', False, [], {})\n"
            + "k.add_fact('modern', 'loop_a', 'depends_on', 'loop_b')\n"
            + "k.add_fact('modern', 'loop_b', 'depends_on', 'loop_a')\n"
            + "t = k.transitive('loop_a', 'depends_on')\n"
            + "print(len(t))\n"
            + "print(t[0]['o'] + '|' + str(len(t[0]['via'])))\n",
            ["1", "loop_b|0"],
        )


class TestCompareExpandPlane:
    def test_expand_full_derivation(self):
        """展开全字段：事实 + 主语/对象词记录 + 跨世界词形 + 关系语义。"""
        assert_output(
            "k = knowledge()\n"
            'k.register_world("modern", "现代物理世界", 3)\n'
            'k.register_relation("composed_of", "组成关系", False, False)\n'
            'k.register_word("atom", "原子", False, [], '
            '{"modern": {"form": "atom", "self_ref": "self"}})\n'
            'k.register_word("proton", "质子", False, [], {})\n'
            'f1 = k.add_fact("modern", "atom", "composed_of", "proton", "v30")\n'
            "e = k.expand(f1)\n"
            "print(e['id'] + '|' + e['world'] + '|' + e['s'] + '|' + e['r'] + '|' + e['o'])\n"
            "print(e['source'] + '|' + e['status'])\n"
            "print(e['subject']['gloss'] + '|' + e['object']['gloss'])\n"
            "print(e['subject_form']['form'] + '|' + e['subject_form']['self_ref'])\n"
            "print(len(e['object_form']))\n"
            "print(e['relation']['semantics'])\n"
            "print(e['world_ctx']['size_rank'])\n",
            [
                "1|modern|atom|composed_of|proton",
                "v30|active",
                "原子|质子",
                "atom|self",
                "0",
                "组成关系",
                "3",
            ],
        )

    def test_expand_unknown_id_fail_fast(self):
        assert_error(
            "k = knowledge()\nprint(k.expand('999'))\n",
            "KNW_FACT_NOT_FOUND",
            line=2,
        )

    def test_same_word_identity(self):
        """词同一性：lexeme 相等且均注册 = 真；未注册 = false。"""
        assert_output(
            _CHAIN
            + "print(k.same_word('atom', 'atom'))\n"
            + "print(k.same_word('atom', 'proton'))\n"
            + "print(k.same_word('quark', 'quark'))\n",
            ["True", "False", "False"],
        )

    def test_compare_four_layers(self):
        """对比 4 层：exact / contradiction / scale / same_word 各判别。"""
        assert_output(
            _CHAIN
            + "c = k.compare(f1, f2)\n"
            + "print(str(c['exact']) + '|' + str(c['contradiction']) + '|' + c['scale'] + '|' + str(c['same_word']))\n"
            + "cs = k.compare(f1, f1)\n"
            + "print(str(cs['exact']) + '|' + str(cs['contradiction']))\n"
            + "k.register_world('quantum', '量子世界', 4)\n"
            + "f5 = k.add_fact('quantum', 'atom', 'composed_of', 'proton')\n"
            + "cc = k.compare(f1, f5)\n"
            + "print(cc['scale'] + '|' + str(cc['exact']))\n",
            ["False|True|same|True", "True|False", "cross|False"],
        )
        assert_error(
            _CHAIN + "print(k.compare(f1, '999'))\n",
            "KNW_FACT_NOT_FOUND",
            line=13,
        )


class TestAuditPlane:
    def test_retract_tombstone_semantics(self):
        """墓碑语义：retract = status 切换；图视图排除；日志保留全史。"""
        assert_output(
            _CHAIN
            + "k.retract(f1, '实验推翻')\n"
            + "print(k.exists('modern', 'atom', 'composed_of', 'proton'))\n"
            + "print(k.fact_len())\n"
            + "rec = k.get_fact(f1)\n"
            + "print(rec['status'])\n"
            + "print(rec['events'][1]['kind'] + '|' + rec['events'][1]['reason'])\n",
            ["False", "4", "retracted", "retract|实验推翻"],
        )

    def test_retract_error_surfaces(self):
        """retract 错误面：未知 id / reason 空 / 重复墓碑 全 fail-fast。"""
        assert_error(
            _CHAIN + "k.retract('999', 'r')\n", "KNW_FACT_NOT_FOUND", line=13
        )
        assert_error(
            _CHAIN + "k.retract(f1, '   ')\n", "KNW_REASON_EMPTY", line=13
        )
        assert_error(
            _CHAIN + "k.retract(f1, 'r1')\nk.retract(f1, 'r2')\n",
            "KNW_FACT_RETRACTED",
            line=14,
        )

    def test_amend_fact_versioning(self):
        """版本化：amend_fact = o 切换（原 o 留事件链全史可溯 + reason 强制）。"""
        assert_output(
            _CHAIN
            + "k.amend_fact(f1, 'electron', '重新测量')\n"
            + "rec = k.get_fact(f1)\n"
            + "print(rec['o'])\n"
            + "print(rec['events'][1]['kind'] + '|' + rec['events'][1]['new_o'])\n"
            + "print(k.exists('modern', 'atom', 'composed_of', 'electron'))\n"
            + "print(k.exists('modern', 'atom', 'composed_of', 'proton'))\n",
            ["electron", "amend|electron", "True", "False"],
        )

    def test_amend_fact_error_surfaces(self):
        """amend_fact 错误面：未知 id / 墓碑 / 新 o 未注册 全 fail-fast。"""
        assert_error(
            _CHAIN + "k.amend_fact('999', 'proton', 'r')\n",
            "KNW_FACT_NOT_FOUND",
            line=13,
        )
        assert_error(
            _CHAIN + "k.retract(f1, 'r1')\nk.amend_fact(f1, 'quark', 'r2')\n",
            "KNW_FACT_RETRACTED",
            line=14,
        )
        assert_error(
            _CHAIN + "k.amend_fact(f2, 'quark', 'r3')\n",
            "KNW_VOCAB_UNREGISTERED",
            line=13,
        )

    def test_source_and_history_fact(self):
        """source + history_fact（全事件链快照）；未知 id fail-fast。"""
        assert_output(
            _CHAIN
            + "f5 = k.add_fact('modern', 'atom', 'depends_on', 'proton', 'v30-flywheel')\n"
            + "print(k.source(f1) + '|' + k.source(f5))\n"
            + "h = k.history_fact(f5)\n"
            + "print(h[0]['kind'] + '|' + str(h[0]['seq']))\n",
            ["|v30-flywheel", "add|5"],
        )
        assert_error(
            _CHAIN + "print(k.source('999'))\n", "KNW_FACT_NOT_FOUND", line=13
        )

    def test_tombstone_then_new_fact_reactivation(self):
        """恢复语义 = 登记新事实（墓碑不复活——新版本是新事实）。"""
        assert_output(
            _CHAIN
            + "k.retract(f1, '推翻')\n"
            + "f_new = k.add_fact('modern', 'atom', 'composed_of', 'proton', 'v31')\n"
            + "print(f_new == f1)\n"
            + "print(k.fact_len())\n"
            + "recs = k.lookup_pair('atom', 'composed_of')\n"
            + "print(str(len(recs)) + '|' + recs[0]['id'] + '|' + recs[1]['id'])\n"
            + "print(k.get_fact(f1)['status'] + '|' + k.get_fact(f_new)['status'])\n",
            ["False", "5", "2|2|6", "retracted|active"],
        )


class TestDeepCloneIndependence:
    def test_clone_kb_planes_independent(self):
        """KB 深拷贝：克隆 A 的 add_fact 不影响克隆 B（可变容器引用语义）。"""
        assert_output(
            "k = knowledge()\n"
            'k.register_world("modern", "现代物理世界", 3)\n'
            'k.register_relation("composed_of", "组成关系", False, False)\n'
            'k.register_word("atom", "原子", False, [], {})\n'
            'k.register_word("proton", "质子", False, [], {})\n'
            'k.register_word("electron", "电子", False, [], {})\n'
            'k.add_fact("modern", "atom", "composed_of", "proton")\n'
            + "k2 = deepcopy(k)\n"
            + "k2.add_fact('modern', 'atom', 'composed_of', 'electron')\n"
            + "print(k.fact_len())\n"
            + "print(k2.fact_len())\n",
            ["1", "2"],
        )


class TestEntriesPlaneZeroRegression:
    def test_store_get_amend_history_unchanged(self):
        """entries 面既有契约零回归（KB 面扩展不改通用登记语义）。"""
        assert_output(
            "kb = knowledge()\n"
            "func ok(any x) -> bool:\n"
            "    return True\n"
            'kb.store("k1", 42, ok)\n'
            'print(kb.get("k1"))\n'
            "print(kb.len())\n"
            'kb.amend("k1", 43, "更正值")\n'
            'print(kb.get("k1"))\n'
            'print(len(kb.history("k1")))\n',
            ["42", "1", "43", "2"],
        )

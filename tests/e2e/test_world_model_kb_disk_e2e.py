"""
tests/e2e/test_world_model_kb_disk_e2e.py

world_model KB 磁盘面 E2E 契约（**R-B B1 验收形态**：load_kb 后 KB 可在 IBCI
内查询；追加 100 条新 fact 后增量可用，无需重编译）：

- **B1 验收全链路**（用户面）：save_kb 落盘 → load_kb 加载 → 活查询
  （lookup_pair/exists/expand）→ 追加 100 事实（循环 add_fact）→ 增量可用
  （查询面反映增量 + 治理门仍生效 + 重导出新 artifact 可再加载）；
- **三级验证门用户面**（try/except 可捕获 + 诊断码可辨）：篡改 artifact →
  KNW_KB_HASH_MISMATCH；
- **内容寻址审计面**：save_kb 返回 hash = 加载验证基准（同 KB 重导出同 hash；
  增量后 hash 变）。

注：本文件属 e2e 层（全量门覆盖；不在单任务默认 smoke 子集）。
"""

from tests.conftest import run_ibci


# 微型 KB 脚本头（用户面：1 世界 / 2 关系 / 4 词 / 2 事实 + 词形跨世界面）
_KB_HEAD = (
    "kb = knowledge()\n"
    'kb.register_world("modern", "现代物理世界", 3)\n'
    'kb.register_relation("composed_of", "组成关系", False, False)\n'
    'kb.register_relation("depends_on", "依赖关系", True, False)\n'
    'kb.register_word("atom", "原子", False, [], '
    '{"modern": {"form": "atom", "self_ref": "self"}})\n'
    'kb.register_word("proton", "质子", False, [], {})\n'
    'kb.register_word("electron", "电子", False, [], {})\n'
    'kb.register_word("nucleus", "原子核", False, [], {})\n'
    'f1 = kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
    'f2 = kb.add_fact("modern", "nucleus", "depends_on", "proton", "v30", "active")\n'
)


class TestB1Acceptance:
    def test_load_kb_live_query(self, tmp_path):
        """B1 验收前半：load_kb(path) 后 KB 可在 IBCI 内查询（活值——查询面
        全可用：lookup/exists/expand/fact 记录权威形态）。"""
        lines = run_ibci(
            "import world_model\n" + _KB_HEAD +
            'world_model.save_kb(kb, "./kb.json")\n'
            'kb2 = world_model.load_kb("./kb.json")\n'
            'print(kb2.fact_len())\n'
            'print(len(kb2.lookup_pair("atom", "composed_of")))\n'
            'print(kb2.exists("modern", "atom", "composed_of", "proton"))\n'
            'print(kb2.expand(kb2.facts()[0]["id"])["subject_form"]["form"])\n'
            'print(kb2.get_fact(kb2.facts()[0]["id"])["source"])\n',
            root_dir=str(tmp_path),
        )
        assert lines == ["2", "1", "True", "atom", "v30"]

    def test_incremental_100_facts_no_recompile(self, tmp_path):
        """B1 验收后半：追加 100 条新 fact 后增量可用，**无需重编译**
        （活 KB 值语义——加载后的 KB 是可增量的活值，非冻结快照）。"""
        # 100 新事实：electron_i（i=0..99）经 excites 关系——词表须先注册
        # （治理门：s/o 已注册词）。经 IBCI 循环批量注册 + 登记。
        append_code = (
            "import world_model\n"
            'kb = world_model.load_kb("./kb.json")\n'
            'kb.register_relation("excites", "激发关系", False, True)\n'
            # 循环批量注册 100 词（nucleon_0..99）
            "int i = 0\n"
            "while i < 100:\n"
            '    kb.register_word("nucleon_" + str(i), "核子" + str(i), False, [], {})\n'
            "    i = i + 1\n"
            # 循环批量登记 100 事实（atom 经 excites 指向各核子；multi_valued
            # 关系——同 (s,r) 多 o 合法，去重门不误伤增量）
            "int j = 0\n"
            "while j < 100:\n"
            '    kb.add_fact("modern", "atom", "excites", "nucleon_" + str(j), "flywheel", "active")\n'
            "    j = j + 1\n"
            "print(kb.fact_len())\n"
            # 增量可用：查询面反映 100 增量（by_source 审计 + lookup 聚合）
            'print(len(kb.by_source("flywheel")))\n'
            'print(len(kb.lookup_pair("atom", "excites")))\n'
            # 治理门增量后仍生效（未注册词 add_fact fail-fast 可捕获）
            "try:\n"
            '    kb.add_fact("modern", "atom", "excites", "quark")\n'
            "    print('gate-broken')\n"
            "except Exception as e:\n"
            "    print('gate-alive')\n"
            # 增量后重导出 → 新 hash（内容变）→ 再加载保真
            'h2 = world_model.save_kb(kb, "./kb_v2.json")\n'
            'kb3 = world_model.load_kb("./kb_v2.json")\n'
            "print(kb3.fact_len())\n"
            'print(len(kb3.by_source("flywheel")))\n'
        )
        # 先落盘初始 artifact
        run_ibci(
            "import world_model\n" + _KB_HEAD +
            'world_model.save_kb(kb, "./kb.json")\n',
            root_dir=str(tmp_path),
        )
        lines = run_ibci(append_code, root_dir=str(tmp_path))
        assert lines == ["102", "100", "100", "gate-alive", "102", "100"]

    def test_content_hash_audit_surface(self, tmp_path):
        """内容寻址审计面（用户面）：save_kb 返回 hash = 验证基准（同 KB
        重导出同 hash；增量后 hash 变）。"""
        lines = run_ibci(
            "import world_model\n" + _KB_HEAD +
            'h1 = world_model.save_kb(kb, "./a.json")\n'
            'h2 = world_model.save_kb(kb, "./b.json")\n'
            "print(h1 == h2)\n"
            'kb.add_fact("modern", "atom", "composed_of", "electron", "v31", "active")\n'
            'h3 = world_model.save_kb(kb, "./c.json")\n'
            "print(h3 == h1)\n",
            root_dir=str(tmp_path),
        )
        assert lines == ["True", "False"]


class TestValidationGatesUserSurface:
    def test_tampered_artifact_capturable(self, tmp_path):
        """完整性门用户面：篡改 artifact 后 load_kb fail-fast——try/except
        可捕获 + 诊断码可辨（KNW_KB_HASH_MISMATCH）。"""
        run_ibci(
            "import world_model\n" + _KB_HEAD +
            'world_model.save_kb(kb, "./kb.json")\n',
            root_dir=str(tmp_path),
        )
        # Python 侧篡改 artifact 内容（不改 hash）
        import json as _json
        p = tmp_path / "kb.json"
        a = _json.loads(p.read_text(encoding="utf-8"))
        a["facts"][0]["o"] = "quark"
        p.write_text(_json.dumps(a, ensure_ascii=False), encoding="utf-8")
        # 用户面：try/except 可捕获（非崩溃）+ 诊断码可辨（KNW_KB_HASH_MISMATCH）
        lines = run_ibci(
            "import world_model\n"
            "try:\n"
            "    kb = world_model.load_kb('./kb.json')\n"
            "    print('tamper-passthrough')\n"
            "except Exception as e:\n"
            "    print('tamper-caught')\n"
            "    print(e.message)\n",
            root_dir=str(tmp_path),
        )
        assert "tamper-passthrough" not in lines  # 未被静默放行
        assert "tamper-caught" in lines           # try/except 可捕获
        assert any("KNW_KB_HASH_MISMATCH" in l for l in lines)  # 诊断码可辨

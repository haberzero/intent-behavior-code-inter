"""
tests/runtime/test_world_model_kb_disk.py

world_model 模块（KB 磁盘面——内容寻址 artifact）判别测试（P3 C1）：

- **save/load round-trip**：KB 面（facts/vocab/seq）保真 + 索引水化重建等价
  + 加载 = 活 KB（可增量 add_fact——B1 验收语义）；
- **三级验证门**（fail-fast 不静默）：结构门 KNW_KB_ARTIFACT_MALFORMED /
  版本门 KNW_KB_SCHEMA_VERSION（无自动迁移）/ 完整性门
  KNW_KB_HASH_MISMATCH（篡改/损坏）；
- **内容寻址纪律**：content_hash = canonical 载荷 sha256（排版无关——同内容
  不同缩进/键序 = 同 hash 可 load；canonical 确定性——同载荷同 hash）；
- **保存审计面**：save_kb 返回 content_hash（钉扎基准——重导出同 KB = 同 hash）。

注：e2e（B1 验收形态：load → 活查询 → 增量 100 事实）归同批次 e2e 文件；
差分 harness 语料不做磁盘 I/O（语料纪律 = 自包含脚本）。
"""

import json
import os

import pytest

from core.base.diagnostics.codes import (
    KNW_KB_ARTIFACT_MALFORMED,
    KNW_KB_HASH_MISMATCH,
    KNW_KB_SCHEMA_VERSION,
)
from core.kernel.issue import InterpreterError
from core.runtime.modules.world_model_impl import (
    KB_SCHEMA_VERSION,
    kb_canonical_payload,
    kb_content_hash,
)


def _code_err(ex):
    assert isinstance(ex, InterpreterError), f"期望 InterpreterError，实际 {type(ex).__name__}"
    return ex.error_code


class TestCanonicalHash:
    def test_hash_deterministic(self):
        """canonical 确定性：同载荷同 hash（内容即身份）。"""
        facts = {"1": {"id": "1", "world": "w", "s": "a", "r": "b", "o": "c",
                       "source": "s", "status": "active", "events": []}}
        vocab = {"words": {}, "relations": {}, "worlds": {}}
        h1 = kb_content_hash(facts, vocab, 1)
        h2 = kb_content_hash(facts, vocab, 1)
        assert h1 == h2
        assert len(h1) == 64  # sha256 全摘要

    def test_hash_layout_independent(self):
        """排版无关性：同内容不同 dict 键序/文件缩进 = 同 canonical 文本
        （sort_keys + 紧凑分隔规范形态）。"""
        facts = {"1": {"id": "1", "world": "w", "s": "a", "r": "b", "o": "c",
                       "source": "s", "status": "active", "events": []}}
        vocab = {"words": {"x": {"lexeme": "x", "gloss": "g", "is_set": False,
                                 "members": [], "entries": {}}},
                 "relations": {}, "worlds": {}}
        text = kb_canonical_payload(facts, vocab, 3)
        parsed = json.loads(text)
        # 重排键序（json 往返 + sort_keys）→ 同 canonical 文本
        text2 = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert text == text2

    def test_schema_version_constant(self):
        assert KB_SCHEMA_VERSION == 2


def _save_kb(tmp_path, name="kb.json"):
    """经 IBCI 代码面 save_kb 落盘（微型 KB：1 世界/1 关系/2 词/1 事实）。"""
    from tests.conftest import run_ibci
    code = (
        "import world_model\n"
        "kb = knowledge()\n"
        'kb.register_world("modern", "现代物理世界", 3)\n'
        'kb.register_relation("composed_of", "组成关系", False, False)\n'
        'kb.register_word("atom", "原子", False, [], {})\n'
        'kb.register_word("proton", "质子", False, [], {})\n'
        'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
        f'h = world_model.save_kb(kb, "./{name}")\n'
        "print(h)\n"
    )
    lines = run_ibci(code, root_dir=str(tmp_path))
    return lines[0], tmp_path / name


class TestSaveLoadRoundTrip:
    def test_round_trip_fidelity(self, tmp_path):
        """save → load round-trip：KB 面全保真（facts/vocab/seq + 索引水化
        等价）+ 加载 = 活 KB。"""
        from tests.conftest import run_ibci
        h, artifact_path = _save_kb(tmp_path)
        assert len(h) == 64
        # artifact 落盘 = 合规封套（v2 = 含 vector 节；空 KB 嵌入面 dim=0）
        a = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert a["schema_version"] == 2
        assert a["content_hash"] == h
        assert len(a["facts"]) == 1 and len(a["vocab"]["words"]) == 2
        assert a["vector"]["dim"] == 0 and a["vector"]["embeddings"] == {}
        # 经语言面 load → 活查询
        code = (
            f"import world_model\n"
            f'kb = world_model.load_kb("./kb.json")\n'
            "print(kb.fact_len())\n"
            'print(kb.lookup_pair("atom", "composed_of")[0]["o"])\n'
            'print(kb.get_fact("1")["source"])\n'
            'print(kb.expand("1")["subject"]["gloss"])\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines == ["1", "proton", "v30", "原子"]

    def test_loaded_kb_is_live_incremental(self, tmp_path):
        """B1 验收语义：加载 = 活 KB——增量 add_fact 可用（无需重编译）；
        增量后重导出 → 新 hash（内容变了）→ 再加载保真。"""
        from tests.conftest import run_ibci
        h1, _ = _save_kb(tmp_path)
        code = (
            "import world_model\n"
            'kb = world_model.load_kb("./kb.json")\n'
            'kb.register_word("electron", "电子", False, [], {})\n'
            'kb.add_fact("modern", "atom", "composed_of", "electron", "v31", "active")\n'
            'print(kb.fact_len())\n'
            'h2 = world_model.save_kb(kb, "./kb2.json")\n'
            f'print(h2 == "{h1}")\n'
            'kb2 = world_model.load_kb("./kb2.json")\n'
            'print(kb2.by_subject("atom")[1]["source"])\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines == ["2", "False", "v31"]  # 增量可用；内容变 → hash 变；再加载保真

    def test_save_idempotent_hash(self, tmp_path):
        """保存审计面：同 KB 重导出 = 同 hash（钉扎基准——hash 是内容函数，
        非文件函数）。"""
        from tests.conftest import run_ibci
        code = (
            "import world_model\n"
            "kb = knowledge()\n"
            'kb.register_world("modern", "现代物理世界", 3)\n'
            'kb.register_relation("composed_of", "组成关系", False, False)\n'
            'kb.register_word("atom", "原子", False, [], {})\n'
            'kb.register_word("proton", "质子", False, [], {})\n'
            'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
            'h1 = world_model.save_kb(kb, "./a.json")\n'
            'h2 = world_model.save_kb(kb, "./b.json")\n'
            "print(h1 == h2)\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines == ["True"]


class TestValidationGates:
    def test_malformed_json_fail_fast(self, tmp_path):
        """结构门：非合法 JSON = KNW_KB_ARTIFACT_MALFORMED。"""
        from tests.conftest import run_ibci
        (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nkb = world_model.load_kb('./bad.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == KNW_KB_ARTIFACT_MALFORMED

    def test_missing_envelope_field_fail_fast(self, tmp_path):
        """结构门：缺封套字段 = KNW_KB_ARTIFACT_MALFORMED。"""
        from tests.conftest import run_ibci
        h, _ = _save_kb(tmp_path)
        a = json.loads((tmp_path / "kb.json").read_text(encoding="utf-8"))
        del a["seq"]
        (tmp_path / "noseq.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nkb = world_model.load_kb('./noseq.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == KNW_KB_ARTIFACT_MALFORMED

    def test_bad_schema_version_fail_fast(self, tmp_path):
        """版本门：schema_version ≠ 1 = KNW_KB_SCHEMA_VERSION（无自动迁移）。"""
        from tests.conftest import run_ibci
        _, _ = _save_kb(tmp_path)
        a = json.loads((tmp_path / "kb.json").read_text(encoding="utf-8"))
        a["schema_version"] = 99
        (tmp_path / "v99.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nkb = world_model.load_kb('./v99.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == KNW_KB_SCHEMA_VERSION

    def test_tampered_content_fail_fast(self, tmp_path):
        """完整性门：内容篡改不改 hash = KNW_KB_HASH_MISMATCH（内容寻址
        的"寻址"即验证）。"""
        from tests.conftest import run_ibci
        _, _ = _save_kb(tmp_path)
        a = json.loads((tmp_path / "kb.json").read_text(encoding="utf-8"))
        a["facts"][0]["o"] = "quark"  # 篡改事实内容，content_hash 不动
        (tmp_path / "tamp.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nkb = world_model.load_kb('./tamp.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == KNW_KB_HASH_MISMATCH

    def test_relayouted_content_loads(self, tmp_path):
        """排版无关性（语言面）：同内容重排（缩进/键序）后仍 hash 匹配可
        load（身份 = canonical，非文件布局）。"""
        from tests.conftest import run_ibci
        _, _ = _save_kb(tmp_path)
        a = json.loads((tmp_path / "kb.json").read_text(encoding="utf-8"))
        (tmp_path / "pretty.json").write_text(
            json.dumps(a, ensure_ascii=False, indent=4, sort_keys=True),
            encoding="utf-8")
        lines = run_ibci(
            "import world_model\nkb = world_model.load_kb('./pretty.json')\n"
            "print(kb.fact_len())\n",
            root_dir=str(tmp_path))
        assert lines == ["1"]

    def test_missing_file_fs_isomorphic(self, tmp_path):
        """文件不存在 = 复用 fs 面诊断（RUN_GENERIC_ERROR——与 fs.read 缺失
        文件同构，不另造码）。"""
        from tests.conftest import run_ibci
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nkb = world_model.load_kb('./nope.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == "RUN_GENERIC_ERROR"


class TestSaveGate:
    def test_save_kb_gate_on_live_kb(self, tmp_path):
        """save_kb 结构门（保存前同构验证——畸形 KB 面 fail-fast 不落盘）。
        空 KB 面（未注册词表/无事实）合法可存（空日志是合法 KB 状态）。"""
        from tests.conftest import run_ibci
        code = (
            "import world_model\n"
            "kb = knowledge()\n"
            'h = world_model.save_kb(kb, "./empty.json")\n'
            "print(h)\n"
            'kb2 = world_model.load_kb("./empty.json")\n'
            "print(kb2.fact_len())\n"
            "print(kb2.words())\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert len(lines[0]) == 64
        assert lines[1] == "0"
        assert lines[2] == "[]"

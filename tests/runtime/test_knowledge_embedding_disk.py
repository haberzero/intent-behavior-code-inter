"""
tests/runtime/test_knowledge_embedding_disk.py

world_model 模块（KB 向量面——artifact v2 内容寻址）判别测试（P6 F2）：

- **v2 嵌入 round-trip**：set_embedding → save_kb（v2，vector 节）→ load_kb
  → 嵌入面保真（embed_search 结果一致 + embedding_dim 一致）；
- **v1 向后兼容**：v1 artifact（无 vector 节，v1 hash）可 load（嵌入面空）——
  旧 KB artifact 不被 v2 演进破坏；
- **hash 版本感知**：同 KB 面 v1 hash（无 vector）≠ v2 hash（含 vector）；
  保存恒 v2（save_kb 写 schema_version=2 + vector 节）；
- **重导出幂等**：同 KB（含嵌入）重导出 = 同 hash（v2，钉扎基准）；
- **嵌入篡改检测**：篡改 vector 节不改 hash = KNW_KB_HASH_MISMATCH（完整性门）。

注：向量面 = 内容信号（非判定）——嵌入持久化进 artifact（v2），加载水化为活
KB 值的嵌入面；确定性 mock 嵌入（ai.set_embedding_mock）保证测试零 LLM。
"""

import json

import pytest

from core.base.diagnostics.codes import KNW_KB_HASH_MISMATCH
from core.kernel.issue import InterpreterError
from core.runtime.modules.world_model_impl import (
    KB_SCHEMA_VERSION,
    kb_content_hash,
)


def _code_err(ex):
    assert isinstance(ex, InterpreterError), f"期望 InterpreterError，实际 {type(ex).__name__}"
    return ex.error_code


def _save_kb_with_embeddings(tmp_path, name="kb.json", dim=4):
    """经 IBCI 代码面构造带嵌入 KB 并 save（确定性 mock 嵌入）。"""
    from tests.conftest import run_ibci
    code = (
        "import ai\n"
        "import world_model\n"
        f"ai.set_embedding_mock(True, dim={dim})\n"
        "kb = knowledge()\n"
        'kb.register_world("modern", "现代物理世界", 3)\n'
        'kb.register_relation("composed_of", "组成关系", False, False)\n'
        'kb.register_word("atom", "原子", False, [], {})\n'
        'kb.register_word("proton", "质子", False, [], {})\n'
        'kb.register_word("electron", "电子", False, [], {})\n'
        'kb.add_fact("modern", "atom", "composed_of", "proton", "v30", "active")\n'
        'kb.set_embedding("atom", ai.embed("atom"))\n'
        'kb.set_embedding("proton", ai.embed("proton"))\n'
        'kb.set_embedding("electron", ai.embed("electron"))\n'
        f'h = world_model.save_kb(kb, "./{name}")\n'
        "print(h)\n"
    )
    lines = run_ibci(code, root_dir=str(tmp_path))
    return lines[0], tmp_path / name


class TestV2RoundTrip:
    def test_schema_version_is_v2(self, tmp_path):
        """保存恒 v2（含 vector 节）。"""
        h, path = _save_kb_with_embeddings(tmp_path)
        a = json.loads(path.read_text(encoding="utf-8"))
        assert a["schema_version"] == 2
        assert KB_SCHEMA_VERSION == 2
        assert "vector" in a
        assert a["vector"]["dim"] == 4
        assert set(a["vector"]["embeddings"]) == {"atom", "proton", "electron"}

    def test_embedding_round_trip_fidelity(self, tmp_path):
        """v2 round-trip：嵌入面保真（load 后 embed_search 结果一致）。"""
        from tests.conftest import run_ibci
        _save_kb_with_embeddings(tmp_path)
        code = (
            "import world_model\n"
            'kb = world_model.load_kb("./kb.json")\n'
            "print(kb.has_embedding(\"atom\"))\n"
            "print(kb.embedding_dim())\n"
            'print(kb.embed_search(kb.embedding("atom"), 3))\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "True"
        assert lines[1] == "4"
        # atom 自身最相似（cosine≈1），确定性排序
        assert 'word: atom' in lines[2] or 'atom' in lines[2]
        assert lines[2].index("atom") < lines[2].index("proton")

    def test_reexport_idempotent_hash(self, tmp_path):
        """重导出幂等：同 KB（含嵌入）重导出 = 同 hash（v2 钉扎基准）。"""
        from tests.conftest import run_ibci
        h1, _ = _save_kb_with_embeddings(tmp_path)
        code = (
            "import world_model\n"
            'kb = world_model.load_kb("./kb.json")\n'
            'h2 = world_model.save_kb(kb, "./kb2.json")\n'
            f'print(h2 == "{h1}")\n'
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "True"


class TestV1BackwardCompat:
    def test_v1_artifact_loads_empty_embeddings(self, tmp_path):
        """v1 向后兼容：无 vector 节的 v1 artifact 可 load（嵌入面空）。"""
        from tests.conftest import run_ibci
        # 手工构造 v1 artifact（无 vector 节，v1 hash）
        facts = {"0": {"id": "0", "world": "w", "s": "a", "r": "b", "o": "c",
                       "source": "s", "status": "active", "events": []}}
        vocab = {"words": {"a": {"lexeme": "a", "gloss": "a", "is_set": False,
                                  "members": [], "entries": {}},
                           "b": {"lexeme": "b", "gloss": "b", "is_set": False,
                                  "members": [], "entries": {}},
                           "c": {"lexeme": "c", "gloss": "c", "is_set": False,
                                  "members": [], "entries": {}}},
                 "relations": {"b": {"type": "b", "semantics": "s",
                                       "transitive": False, "multi_valued": False}},
                 "worlds": {}}
        h = kb_content_hash(facts, vocab, 0, vector=None)  # v1 hash（无 vector）
        artifact = {"schema_version": 1, "content_hash": h,
                    "facts": [facts["0"]], "vocab": vocab, "seq": 0}
        (tmp_path / "v1.json").write_text(
            json.dumps(artifact, ensure_ascii=False), encoding="utf-8")
        code = (
            "import world_model\n"
            'kb = world_model.load_kb("./v1.json")\n'
            "print(kb.fact_len())\n"
            "print(kb.has_embedding(\"a\"))\n"
        )
        lines = run_ibci(code, root_dir=str(tmp_path))
        assert lines[0] == "1"      # KB 面保真
        assert lines[1] == "False"  # v1 无嵌入面


class TestHashVersionAware:
    def test_v1_v2_hash_differ(self, tmp_path):
        """hash 版本感知：同 KB 面 v1 hash（无 vector）≠ v2 hash（含 vector）。"""
        facts = {"0": {"id": "0", "world": "w", "s": "a", "r": "b", "o": "c",
                       "source": "s", "status": "active", "events": []}}
        vocab = {"words": {}, "relations": {}, "worlds": {}}
        h_v1 = kb_content_hash(facts, vocab, 0, vector=None)
        vector = {"dim": 2, "embeddings": {"a": [1.0, 0.0]}}
        h_v2 = kb_content_hash(facts, vocab, 0, vector=vector)
        assert h_v1 != h_v2  # vector 节入 hash = 身份不同

    def test_tampered_embedding_hash_mismatch(self, tmp_path):
        """完整性门：篡改 vector 节不改 hash = KNW_KB_HASH_MISMATCH。"""
        from tests.conftest import run_ibci
        _save_kb_with_embeddings(tmp_path)
        a = json.loads((tmp_path / "kb.json").read_text(encoding="utf-8"))
        a["vector"]["embeddings"]["atom"] = [999.0, 999.0, 999.0, 999.0]
        (tmp_path / "tamp.json").write_text(
            json.dumps(a, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            run_ibci("import world_model\nkb = world_model.load_kb('./tamp.json')\n",
                     root_dir=str(tmp_path))
        assert _code_err(exc.value) == KNW_KB_HASH_MISMATCH

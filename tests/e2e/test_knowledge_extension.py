"""
tests/e2e/test_knowledge_extension.py

knowledge 扩展面（round3 R3-⑫ R-8）：

- export：整库导出（键 → {value, check_name, provenance, events} 审计链全量）；
- history kind 过滤：第 2 参 kind（"store"/"amend"）过滤事件类型，缺省全事件；
- provenance：store 第 4 参来源标记，入条目 + 经 export/history 可观测；
- 深克隆/序列化往返保真（provenance 随行不丢失）。
"""
import pytest

from tests.conftest import run_ibci


_OK = "func ok(any v) -> bool:\n    return True\n"


class TestProvenance:
    def test_store_with_provenance(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok, \"round-1\")\n"
            "dict e = kb.export()\n"
            "print(e[\"a\"][\"provenance\"])\n"
        )
        assert out == ["round-1"]

    def test_store_without_provenance_empty(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok)\n"
            "dict e = kb.export()\n"
            "if e[\"a\"][\"provenance\"] == \"\":\n"
            "    print(\"empty\")\n"
        )
        assert out == ["empty"]


class TestExport:
    def test_export_structure(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok, \"src\")\n"
            "kb.amend(\"a\", \"v2\", \"refined\")\n"
            "dict e = kb.export()\n"
            "print(e[\"a\"][\"value\"])\n"
            "print(len(e[\"a\"][\"events\"]))\n"
            "print(e[\"a\"][\"events\"][1][\"kind\"])\n"
        )
        assert out == ["v2", "2", "amend"]

    def test_export_multiple_keys(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"1\", ok, \"s1\")\n"
            "kb.store(\"b\", \"2\", ok, \"s2\")\n"
            "dict e = kb.export()\n"
            "print(len(e))\n"
            "print(e[\"b\"][\"provenance\"])\n"
        )
        assert out == ["2", "s2"]


class TestHistoryKindFilter:
    def test_filter_amend_only(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok)\n"
            "kb.amend(\"a\", \"v2\", \"r1\")\n"
            "kb.amend(\"a\", \"v3\", \"r2\")\n"
            "list h = kb.history(\"a\", \"amend\")\n"
            "print(len(h))\n"
            "print(h[0][\"reason\"])\n"
        )
        assert out == ["2", "r1"]

    def test_filter_store_only(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok)\n"
            "kb.amend(\"a\", \"v2\", \"r1\")\n"
            "list h = kb.history(\"a\", \"store\")\n"
            "print(len(h))\n"
            "print(h[0][\"kind\"])\n"
        )
        assert out == ["1", "store"]

    def test_all_events_default(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok)\n"
            "kb.amend(\"a\", \"v2\", \"r1\")\n"
            "list h = kb.history(\"a\")\n"
            "print(len(h))\n"
        )
        assert out == ["2"]

    def test_unknown_kind_empty(self):
        out = run_ibci(
            _OK +
            "knowledge kb = knowledge()\n"
            "kb.store(\"a\", \"v1\", ok)\n"
            "list h = kb.history(\"a\", \"nope\")\n"
            "print(len(h))\n"
        )
        assert out == ["0"]


# provenance 经 save_state/load_state 往返保真面属 runtime 层（ihost 文件
# 机制 + engine/tmp_path fixture）——见 tests/runtime/test_knowledge_type.py
# TestSaveLoadFidelity::test_provenance_roundtrip。

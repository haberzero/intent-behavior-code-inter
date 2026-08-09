"""
tests/contracts/test_diagnostic_exporter.py
============================================

Contract tests for the symbol table / type binding exporter (PT-FEAT-5).

Validates:
- EXP-1: export_symbols_json returns every root symbol with required fields
- EXP-2: type bindings export maps node kind + location → type
- EXP-3: dot export produces a well-formed digraph (clusters + edges)
- EXP-4: json is serializable and round-trips through json.loads
- EXP-5: handles empty/missing data without crashing (fail-open)
"""

import json

import pytest

from core.engine import IBCIEngine
from core.compiler.diagnostics.exporter import (
    export_symbols_json,
    export_type_bindings_json,
    export_dot,
    export_artifact,
)


@pytest.fixture(scope="module")
def hello_result():
    engine = IBCIEngine(root_dir="examples/01_getting_started", auto_sniff=False)
    artifact = engine.compile("examples/01_getting_started/01_hello_world.ibci")
    assert artifact is not None, "compile of hello_world failed"
    return artifact.modules[artifact.entry_module]


class TestSymbolsJson:
    def test_exports_root_symbols(self, hello_result):
        entries = export_symbols_json(hello_result.symbol_table)
        assert entries, "expected at least some symbols"
        for entry in entries:
            assert "scope" in entry and "symbol" in entry
            sym = entry["symbol"]
            for field in ("name", "kind", "uid", "type"):
                assert field in sym, f"missing symbol field {field!r}"

    def test_required_fields_present(self, hello_result):
        entries = export_symbols_json(hello_result.symbol_table)
        # 每个符号都有 kind 与 uid（定位信息不缺失）
        for entry in entries:
            assert entry["symbol"]["kind"]
            assert entry["symbol"]["uid"]

    def test_json_round_trip(self, hello_result):
        payload = export_artifact(hello_result, "mod", fmt="json")
        data = json.loads(payload)
        assert "module" in data and "symbols" in data and "type_bindings" in data


class TestTypeBindingsJson:
    def test_maps_node_to_type(self, hello_result):
        bindings = export_type_bindings_json(hello_result)
        assert isinstance(bindings, list)
        for b in bindings:
            assert "node" in b and "type" in b


class TestDotExport:
    def test_well_formed_digraph(self, hello_result):
        dot = export_dot(hello_result.symbol_table, hello_result)
        assert dot.startswith('digraph "symbols" {')
        assert dot.rstrip().endswith("}")
        # 存在符号节点与子图 cluster
        assert "subgraph cluster_" in dot
        assert 'shape=box' in dot

    def test_has_scope_and_type_edges(self, hello_result):
        dot = export_dot(hello_result.symbol_table, hello_result)
        assert "->" in dot  # 至少一条边（作用域父子或类型绑定，dot 语法用 ->）


class TestFailOpen:
    def test_none_symbol_table(self):
        assert export_symbols_json(None) == []

    def test_empty_result_dot(self):
        # 空 result（无 node_to_type）不崩，仍输出合法 digraph 骨架
        class _Empty:
            symbol_table = None
            node_to_type = {}
            node_to_loc = {}

        dot = export_dot(None, _Empty(), module_name="empty")
        assert dot.startswith('digraph "symbols" {')
        assert dot.rstrip().endswith("}")

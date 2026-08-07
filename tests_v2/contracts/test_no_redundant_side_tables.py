"""
Contract test: redundant side tables have been removed.

After the 双写真相收敛, the serialized side_tables dict must NOT contain
'node_is_callable_instance' or 'node_capture_mode' keys.
These values now live exclusively on AST node fields.
"""

import pytest
from core.kernel import ast
from core.kernel.symbols import SymbolTable
from core.kernel.blueprint import CompilationResult
from core.compiler.serialization.serializer import FlatSerializer


def test_no_redundant_side_tables_in_serialized_output():
    """Serialized output must not contain node_is_callable_instance or node_capture_mode."""
    module = ast.IbModule(body=[])
    symbol_table = SymbolTable()

    result = CompilationResult(
        module_ast=module,
        symbol_table=symbol_table,
    )

    serializer = FlatSerializer()
    output = serializer.serialize_result(result)

    side_tables = output.get("side_tables", {})
    assert "node_is_callable_instance" not in side_tables, \
        "node_is_callable_instance should no longer exist in side_tables (moved to AST field)"
    assert "node_capture_mode" not in side_tables, \
        "node_capture_mode should no longer exist in side_tables (moved to AST field)"
    # These should still exist
    assert "node_to_symbol" in side_tables
    assert "node_to_type" in side_tables
    assert "node_to_loc" in side_tables

"""
Regression tests for ContextBuilder (prelude injection).

Covers fix: ContextBuilder.build() now injects builtin prelude symbols.
"""

import pytest
from core.kernel import ast
from core.kernel.factory import create_default_registry
from core.compiler.semantic_v2.context import ContextBuilder


def test_context_builder_injects_prelude():
    """ContextBuilder.build() should inject builtin types/functions into symbol table."""
    module = ast.IbModule(body=[])
    registry = create_default_registry()

    builder = ContextBuilder()
    builder.with_ast(module).with_registry(registry).with_module_name("test")
    context = builder.build()

    # The root symbol table should contain builtin types like 'int', 'str', etc.
    sym_table = context.symbol_table.current
    assert sym_table.resolve("int") is not None
    assert sym_table.resolve("str") is not None
    assert sym_table.resolve("bool") is not None
    assert sym_table.resolve("float") is not None


def test_context_builder_without_registry_fails():
    """Without registry, build should fail."""
    module = ast.IbModule(body=[])

    builder = ContextBuilder()
    builder.with_ast(module).with_module_name("test")

    with pytest.raises(ValueError, match="Registry is required"):
        builder.build()

"""Shared fixtures for semantic_v2 pass tests."""

import pytest
from core.kernel import ast
from core.kernel.spec.registry import SpecRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.symbols import SymbolTable
from core.compiler.semantic_v2.context import SemanticContext, ContextBuilder
from core.compiler.semantic_v2.metadata import MetadataStore, SymbolTableContext, TypeEnvironment


@pytest.fixture
def axiom_registry():
    return AxiomRegistry()


@pytest.fixture
def spec_registry(axiom_registry):
    return SpecRegistry(axiom_registry)


@pytest.fixture
def empty_module():
    return ast.IbModule(body=[])


def make_context(module_ast, registry):
    """Helper to build a SemanticContext for testing."""
    symbol_table = SymbolTable()
    return SemanticContext(
        ast=module_ast,
        registry=registry,
        module_name="test_module",
        symbol_table=SymbolTableContext(current=symbol_table),
        type_environment=TypeEnvironment(),
        metadata=MetadataStore(),
    )

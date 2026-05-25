"""Shared fixtures for semantic pass tests."""

import pytest
from core.kernel import ast
from core.kernel.spec.registry import SpecRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.factory import create_default_registry
from core.kernel.symbols import SymbolTable
from core.compiler.semantic.context import SemanticContext, ContextBuilder
from core.compiler.semantic.metadata import MetadataStore, SymbolTableContext, TypeInferenceState


@pytest.fixture
def axiom_registry():
    return AxiomRegistry()


@pytest.fixture
def spec_registry(axiom_registry):
    """A fully-populated SpecRegistry with all builtin types (int, str, etc.)."""
    return create_default_registry()


@pytest.fixture
def empty_module():
    return ast.IbModule(body=[])


def make_context(module_ast, registry):
    """Helper to build a SemanticContext for testing (uses full ContextBuilder pipeline)."""
    return ContextBuilder().with_ast(module_ast).with_registry(registry).with_module_name("test_module").build()

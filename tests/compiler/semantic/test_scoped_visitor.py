"""
Tests for ScopedVisitor base class.

Validates:
- Scope stack push/pop mechanics
- enter_scope context manager safety (auto-pop on exception)
- visit dispatch and generic_visit fallback
- error/warning diagnostic helpers
"""

import pytest
from core.kernel import ast
from core.kernel.symbols import SymbolTable
from core.kernel.factory import create_default_registry
from core.compiler.semantic.context import ContextBuilder
from core.compiler.semantic.passes.scoped_visitor import ScopedVisitor


def make_visitor():
    """Create a ScopedVisitor with a minimal context."""
    registry = create_default_registry()
    module = ast.IbModule(body=[])
    context = ContextBuilder().with_ast(module).with_registry(registry).with_module_name("test").build()
    return ScopedVisitor(context)


class TestScopeStack:
    """Scope stack push/pop mechanics."""

    def test_initial_scope_is_root(self):
        v = make_visitor()
        assert v.current_scope is v.symbol_table
        assert len(v.scope_stack) == 1

    def test_push_pop(self):
        v = make_visitor()
        child = SymbolTable(parent=v.current_scope, name="child")
        v.push_scope(child)
        assert v.current_scope is child
        assert len(v.scope_stack) == 2
        v.pop_scope()
        assert v.current_scope is v.symbol_table
        assert len(v.scope_stack) == 1

    def test_pop_never_removes_root(self):
        v = make_visitor()
        v.pop_scope()  # should be no-op
        assert len(v.scope_stack) == 1
        assert v.current_scope is v.symbol_table


class TestEnterScope:
    """enter_scope context manager."""

    def test_normal_exit(self):
        v = make_visitor()
        child = SymbolTable(parent=v.current_scope, name="func")
        with v.enter_scope(child):
            assert v.current_scope is child
        assert v.current_scope is v.symbol_table

    def test_exception_still_pops(self):
        v = make_visitor()
        child = SymbolTable(parent=v.current_scope, name="func")
        with pytest.raises(ValueError):
            with v.enter_scope(child):
                assert v.current_scope is child
                raise ValueError("test error")
        # Scope should be restored even after exception
        assert v.current_scope is v.symbol_table

    def test_nested_scopes(self):
        v = make_visitor()
        s1 = SymbolTable(parent=v.current_scope, name="s1")
        s2 = SymbolTable(parent=s1, name="s2")
        with v.enter_scope(s1):
            assert v.current_scope is s1
            with v.enter_scope(s2):
                assert v.current_scope is s2
            assert v.current_scope is s1
        assert v.current_scope is v.symbol_table


class TestVisitDispatch:
    """visit() dispatch mechanism."""

    def test_visits_module(self):
        v = make_visitor()
        visited = []

        def visit_IbModule(node):
            visited.append(node)

        v.visit_IbModule = visit_IbModule
        module = ast.IbModule(body=[])
        v.visit(module)
        assert len(visited) == 1

    def test_none_returns_none(self):
        v = make_visitor()
        assert v.visit(None) is None


class TestDiagnostics:
    """error/warning helpers."""

    def test_error_records_diagnostic(self):
        v = make_visitor()
        node = ast.IbModule(body=[])
        v.error("test error", node, code="SEM_999")
        assert len(v.diagnostics) == 1
        assert v.diagnostics[0].code == "SEM_999"
        assert v.diagnostics[0].message == "test error"

    def test_warning_records_diagnostic(self):
        v = make_visitor()
        node = ast.IbModule(body=[])
        v.warning("test warning", node, code="SEM_081")
        assert len(v.diagnostics) == 1
        assert v.diagnostics[0].message == "test warning"

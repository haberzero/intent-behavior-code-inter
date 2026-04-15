"""
tests/kernel/test_symbols.py

Unit tests for core/kernel/symbols.py

Coverage:
  - Symbol / FunctionSymbol / TypeSymbol / VariableSymbol construction
  - Symbol.spec field and .descriptor backward-compat shim
  - Symbol.clone()
  - Symbol.get_content_hash() stability
  - SymbolTable.define / resolve (including scoped lookup)
  - SymbolTable.uid uniqueness
  - SymbolTable duplicate-define error
  - SymbolFactory.create_from_spec
"""

import pytest
from core.kernel.symbols import (
    Symbol, SymbolKind,
    FunctionSymbol, TypeSymbol, VariableSymbol, IntentSymbol,
    SymbolTable, SymbolFactory,
)
from core.kernel.spec import FuncSpec, ClassSpec, ModuleSpec, IbSpec
from core.kernel.factory import create_default_registry


@pytest.fixture(scope="module")
def reg():
    return create_default_registry()


# ---------------------------------------------------------------------------
# 1. Symbol construction and spec/descriptor compat shim
# ---------------------------------------------------------------------------

class TestSymbolBasic:
    def test_variable_symbol_with_spec(self, reg):
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        assert sym.name == "x"
        assert sym.spec is int_s
        assert sym.descriptor is int_s  # compat shim

    def test_descriptor_setter_routes_to_spec(self, reg):
        sym = VariableSymbol(name="y", kind=SymbolKind.VARIABLE)
        int_s = reg.resolve("int")
        sym.descriptor = int_s  # use old-style setter
        assert sym.spec is int_s

    def test_symbol_with_no_spec(self):
        sym = VariableSymbol(name="z", kind=SymbolKind.VARIABLE)
        assert sym.spec is None
        assert sym.descriptor is None

    def test_function_symbol(self, reg):
        fn_spec = reg.factory.create_func("add", ["int", "int"], return_type_name="int")
        sym = FunctionSymbol(name="add", kind=SymbolKind.FUNCTION, spec=fn_spec)
        assert sym.is_function
        assert not sym.is_type
        assert sym.return_type_name == "int"
        assert sym.param_type_names == ["int", "int"]

    def test_type_symbol(self, reg):
        cls_spec = reg.factory.create_class("Dog")
        sym = TypeSymbol(name="Dog", kind=SymbolKind.CLASS, spec=cls_spec)
        assert sym.is_type
        assert not sym.is_function

    def test_variable_symbol_is_variable(self, reg):
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="count", kind=SymbolKind.VARIABLE, spec=int_s)
        assert sym.is_variable

    def test_intent_symbol(self):
        sym = IntentSymbol(
            name="myIntent", kind=SymbolKind.INTENT,
            content="do something", is_exclusive=True
        )
        assert sym.content == "do something"
        assert sym.is_exclusive


# ---------------------------------------------------------------------------
# 2. Symbol.clone()
# ---------------------------------------------------------------------------

class TestSymbolClone:
    def test_clone_produces_new_object(self, reg):
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        clone = sym.clone()
        assert clone is not sym
        assert clone.name == sym.name

    def test_clone_shares_spec_object(self, reg):
        """IbSpec is pure data - sharing is intentional and safe."""
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        clone = sym.clone()
        assert clone.spec is sym.spec  # same object - OK, pure data

    def test_clone_without_spec(self):
        sym = VariableSymbol(name="anon", kind=SymbolKind.VARIABLE)
        clone = sym.clone()
        assert clone.name == "anon"
        assert clone.spec is None


# ---------------------------------------------------------------------------
# 3. Symbol.get_content_hash()
# ---------------------------------------------------------------------------

class TestSymbolHash:
    def test_hash_is_string(self, reg):
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        h = sym.get_content_hash()
        assert isinstance(h, str) and len(h) == 16

    def test_same_symbol_same_hash(self, reg):
        int_s = reg.resolve("int")
        s1 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        s2 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        assert s1.get_content_hash() == s2.get_content_hash()

    def test_different_name_different_hash(self, reg):
        int_s = reg.resolve("int")
        s1 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        s2 = VariableSymbol(name="y", kind=SymbolKind.VARIABLE, spec=int_s)
        assert s1.get_content_hash() != s2.get_content_hash()

    def test_hash_no_spec(self):
        sym = VariableSymbol(name="bare", kind=SymbolKind.VARIABLE)
        h = sym.get_content_hash()
        assert len(h) == 16


# ---------------------------------------------------------------------------
# 4. SymbolTable
# ---------------------------------------------------------------------------

class TestSymbolTable:
    def test_define_and_resolve(self, reg):
        table = SymbolTable(name="global")
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="count", kind=SymbolKind.VARIABLE, spec=int_s)
        table.define(sym)
        found = table.resolve("count")
        assert found is sym

    def test_resolve_unknown_returns_none(self):
        table = SymbolTable(name="empty")
        assert table.resolve("nonexistent") is None

    def test_scoped_lookup_walks_parent(self, reg):
        parent = SymbolTable(name="parent")
        child = SymbolTable(parent=parent, name="child")
        int_s = reg.resolve("int")
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        parent.define(sym)
        # child can resolve from parent
        assert child.resolve("x") is sym

    def test_child_shadows_parent(self, reg):
        parent = SymbolTable(name="parent")
        child = SymbolTable(parent=parent, name="child")
        int_s = reg.resolve("int")
        str_s = reg.resolve("str")
        p_sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        c_sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=str_s)
        parent.define(p_sym)
        child.define(c_sym)
        # child sees its own 'x'
        assert child.resolve("x") is c_sym
        # parent still sees its own
        assert parent.resolve("x") is p_sym

    def test_duplicate_define_raises(self, reg):
        table = SymbolTable(name="scope")
        int_s = reg.resolve("int")
        s1 = VariableSymbol(name="dup", kind=SymbolKind.VARIABLE, spec=int_s)
        s2 = VariableSymbol(name="dup", kind=SymbolKind.VARIABLE, spec=int_s)
        table.define(s1)
        with pytest.raises(ValueError, match="already defined"):
            table.define(s2)

    def test_allow_overwrite(self, reg):
        table = SymbolTable(name="scope")
        int_s = reg.resolve("int")
        str_s = reg.resolve("str")
        s1 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=int_s)
        s2 = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, spec=str_s)
        table.define(s1)
        table.define(s2, allow_overwrite=True)
        assert table.resolve("x").spec is str_s

    def test_uid_format(self):
        root = SymbolTable(name="root")
        child = SymbolTable(parent=root, name="fn_body")
        assert "root" in root.uid
        assert "fn_body" in child.uid

    def test_get_global_scope(self):
        g = SymbolTable(name="global")
        m = SymbolTable(parent=g, name="mid")
        l = SymbolTable(parent=m, name="local")
        assert l.get_global_scope() is g

    def test_depth_counter(self):
        g = SymbolTable(name="g")
        m = SymbolTable(parent=g, name="m")
        l = SymbolTable(parent=m, name="l")
        assert g.depth == 0
        assert m.depth == 1
        assert l.depth == 2


# ---------------------------------------------------------------------------
# 5. SymbolFactory
# ---------------------------------------------------------------------------

class TestSymbolFactory:
    def test_create_from_func_spec(self, reg):
        fn = reg.factory.create_func("say", ["str"], return_type_name="void")
        sym = SymbolFactory.create_from_spec("say", fn)
        assert isinstance(sym, FunctionSymbol)
        assert sym.spec is fn

    def test_create_from_class_spec(self, reg):
        cls = reg.factory.create_class("Cat")
        sym = SymbolFactory.create_from_spec("Cat", cls)
        assert isinstance(sym, TypeSymbol)

    def test_create_from_module_spec(self, reg):
        ms = reg.factory.create_module("mymod")
        sym = SymbolFactory.create_from_spec("mymod", ms)
        assert isinstance(sym, VariableSymbol)

    def test_create_builtin_method(self, reg):
        fn = reg.factory.create_func("__add__", ["int"], return_type_name="int")
        sym = SymbolFactory.create_builtin_method("__add__", fn)
        assert sym.metadata.get("is_builtin") is True

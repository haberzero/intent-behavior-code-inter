"""
tests/kernel/test_spec_layer.py

Module-level end-to-end unit tests for the core/kernel/spec/ layer.

Coverage:
  - IbSpec base and subclass construction
  - SpecFactory (create_primitive, create_func, create_class, create_list,
                 create_dict, create_module, create_bound_method)
  - SpecRegistry.register / resolve / resolve_from_value
  - SpecRegistry capability queries (is_callable, is_class_spec, is_module_spec,
                                    is_dynamic, is_assignable, get_axiom,
                                    get_operator_cap, get_call_cap)
  - SpecRegistry.resolve_member / resolve_return
  - None-safety on all predicate methods
  - create_default_spec_registry (full bootstrap)
  - kernel/factory.create_default_registry (integration)
"""

import pytest
from core.kernel.spec import (
    IbSpec, FuncSpec, ClassSpec, ListSpec, DictSpec, ModuleSpec, BoundMethodSpec,
    INT_SPEC, STR_SPEC, FLOAT_SPEC, BOOL_SPEC, VOID_SPEC, ANY_SPEC, AUTO_SPEC,
)
from core.kernel.spec.registry import SpecRegistry, SpecFactory, create_default_spec_registry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms
from core.kernel.factory import create_default_registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def axiom_registry() -> AxiomRegistry:
    ax = AxiomRegistry()
    register_core_axioms(ax)
    return ax


@pytest.fixture(scope="module")
def spec_reg(axiom_registry: AxiomRegistry) -> SpecRegistry:
    return create_default_spec_registry(axiom_registry)


@pytest.fixture(scope="module")
def factory(spec_reg: SpecRegistry) -> SpecFactory:
    return spec_reg.factory


# ---------------------------------------------------------------------------
# 1. IbSpec base and subclass construction
# ---------------------------------------------------------------------------

class TestIbSpecBase:
    def test_primitive_spec_attributes(self):
        s = IbSpec(name="int", is_nullable=False, is_user_defined=False)
        assert s.name == "int"
        assert not s.is_nullable
        assert not s.is_user_defined
        assert s.module_path is None

    def test_get_base_name_primitive(self):
        assert INT_SPEC.get_base_name() == "int"

    def test_get_base_name_with_module(self):
        s = IbSpec(name="MyType", module_path="mymod")
        assert s.get_base_name() == "MyType"

    def test_func_spec_attributes(self):
        fn = FuncSpec(
            name="add",
            param_type_names=["int", "int"],
            return_type_name="int",
        )
        assert fn.param_type_names == ["int", "int"]
        assert fn.return_type_name == "int"
        assert fn.is_llm is False

    def test_class_spec_attributes(self):
        cls = ClassSpec(name="Dog", parent_name="Object")
        assert cls.name == "Dog"
        assert cls.parent_name == "Object"
        assert cls.is_user_defined is True

    def test_list_spec_attributes(self):
        ls = ListSpec(name="list", element_type_name="str")
        assert ls.element_type_name == "str"
        assert "str" in repr(ls)

    def test_dict_spec_attributes(self):
        ds = DictSpec(name="dict", key_type_name="str", value_type_name="int")
        assert ds.key_type_name == "str"
        assert ds.value_type_name == "int"

    def test_module_spec_axiom_name(self):
        ms = ModuleSpec(name="mymod")
        # get_base_name() returns the axiom lookup key ('module' for ModuleSpec),
        # not the instance name.  The instance name is accessed via .name.
        assert ms.name == "mymod"
        assert ms.get_base_name() == "module"  # axiom key is always 'module'

    def test_bound_method_spec(self):
        bm = BoundMethodSpec(
            name="bound_method",
            receiver_type_name="str",
            func_spec_name="callable",
        )
        assert bm.receiver_type_name == "str"
        assert bm.func_spec_name == "callable"

    def test_constants_are_correct_types(self):
        assert isinstance(INT_SPEC, IbSpec)
        assert isinstance(ANY_SPEC, IbSpec)
        assert INT_SPEC.name == "int"
        assert ANY_SPEC.name == "any"


# ---------------------------------------------------------------------------
# 2. SpecFactory
# ---------------------------------------------------------------------------

class TestSpecFactory:
    def test_create_primitive(self, factory: SpecFactory):
        s = factory.create_primitive("mytype")
        assert isinstance(s, IbSpec)
        assert s.name == "mytype"

    def test_create_func_defaults(self, factory: SpecFactory):
        fn = factory.create_func("greet")
        assert isinstance(fn, FuncSpec)
        assert fn.return_type_name == "void"
        assert fn.param_type_names == []

    def test_create_func_full(self, factory: SpecFactory):
        fn = factory.create_func("add", ["int", "int"], return_type_name="int")
        assert fn.param_type_names == ["int", "int"]
        assert fn.return_type_name == "int"
        assert fn.name == "add"

    def test_create_class(self, factory: SpecFactory):
        cls = factory.create_class("Cat", parent_name="Object")
        assert isinstance(cls, ClassSpec)
        assert cls.parent_name == "Object"
        assert cls.is_user_defined is True

    def test_create_class_no_parent(self, factory: SpecFactory):
        cls = factory.create_class("Base")
        assert cls.parent_name is None

    def test_create_list(self, factory: SpecFactory):
        ls = factory.create_list("str")
        assert isinstance(ls, ListSpec)
        assert ls.element_type_name == "str"

    def test_create_dict(self, factory: SpecFactory):
        ds = factory.create_dict("str", "int")
        assert isinstance(ds, DictSpec)
        assert ds.key_type_name == "str"
        assert ds.value_type_name == "int"

    def test_create_module(self, factory: SpecFactory):
        ms = factory.create_module("mymod")
        assert isinstance(ms, ModuleSpec)
        assert ms.name == "mymod"

    def test_create_bound_method(self, factory: SpecFactory):
        bm = factory.create_bound_method("str", "callable")
        assert isinstance(bm, BoundMethodSpec)
        assert bm.receiver_type_name == "str"


# ---------------------------------------------------------------------------
# 3. SpecRegistry.register / resolve
# ---------------------------------------------------------------------------

class TestSpecRegistryResolve:
    def test_resolve_builtin_primitives(self, spec_reg: SpecRegistry):
        for name in ("int", "str", "float", "bool", "void", "any", "auto"):
            s = spec_reg.resolve(name)
            assert s is not None, f"Missing builtin spec: {name}"
            assert s.name == name

    def test_resolve_list_and_dict(self, spec_reg: SpecRegistry):
        ls = spec_reg.resolve("list")
        ds = spec_reg.resolve("dict")
        assert isinstance(ls, ListSpec)
        assert isinstance(ds, DictSpec)

    def test_resolve_module(self, spec_reg: SpecRegistry):
        ms = spec_reg.resolve("module")
        assert isinstance(ms, ModuleSpec)

    def test_resolve_unknown_returns_none(self, spec_reg: SpecRegistry):
        assert spec_reg.resolve("definitely_not_a_type") is None

    def test_register_and_resolve_custom_class(self, spec_reg: SpecRegistry):
        cls = spec_reg.factory.create_class("Parrot")
        registered = spec_reg.register(cls)
        found = spec_reg.resolve("Parrot")
        assert found is not None
        assert found.name == "Parrot"

    def test_register_with_module_path(self, spec_reg: SpecRegistry):
        cls = ClassSpec(name="Widget", module_path="ui.components")
        spec_reg.register(cls)
        found = spec_reg.resolve("Widget", module="ui.components")
        assert found is not None

    def test_resolve_from_value_int(self, spec_reg: SpecRegistry):
        s = spec_reg.resolve_from_value(42)
        assert s is not None and s.name == "int"

    def test_resolve_from_value_str(self, spec_reg: SpecRegistry):
        s = spec_reg.resolve_from_value("hello")
        assert s is not None and s.name == "str"

    def test_resolve_from_value_bool(self, spec_reg: SpecRegistry):
        # bool before int (isinstance(True, int) is True in Python)
        s = spec_reg.resolve_from_value(True)
        assert s is not None and s.name == "bool"

    def test_resolve_from_value_float(self, spec_reg: SpecRegistry):
        s = spec_reg.resolve_from_value(3.14)
        assert s is not None and s.name == "float"

    def test_resolve_from_value_none(self, spec_reg: SpecRegistry):
        s = spec_reg.resolve_from_value(None)
        assert s is not None and s.name == "void"

    def test_resolve_from_value_unknown(self, spec_reg: SpecRegistry):
        s = spec_reg.resolve_from_value(object())
        assert s is None


# ---------------------------------------------------------------------------
# 4. None-safety for all predicate methods
# ---------------------------------------------------------------------------

class TestNoneSafety:
    def test_is_callable_none(self, spec_reg: SpecRegistry):
        assert spec_reg.is_callable(None) is False

    def test_is_dynamic_none(self, spec_reg: SpecRegistry):
        assert spec_reg.is_dynamic(None) is True  # unknown → dynamic

    def test_is_class_spec_none(self, spec_reg: SpecRegistry):
        assert spec_reg.is_class_spec(None) is False

    def test_is_module_spec_none(self, spec_reg: SpecRegistry):
        assert spec_reg.is_module_spec(None) is False

    def test_get_axiom_none(self, spec_reg: SpecRegistry):
        assert spec_reg.get_axiom(None) is None

    def test_get_call_cap_none(self, spec_reg: SpecRegistry):
        assert spec_reg.get_call_cap(None) is None

    def test_get_operator_cap_none(self, spec_reg: SpecRegistry):
        assert spec_reg.get_operator_cap(None) is None


# ---------------------------------------------------------------------------
# 5. Capability queries
# ---------------------------------------------------------------------------

class TestCapabilityQueries:
    def test_int_has_operator_cap(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        cap = spec_reg.get_operator_cap(int_s)
        assert cap is not None

    def test_int_has_axiom(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        ax = spec_reg.get_axiom(int_s)
        assert ax is not None
        assert type(ax).__name__ == "IntAxiom"

    def test_str_has_axiom(self, spec_reg: SpecRegistry):
        str_s = spec_reg.resolve("str")
        ax = spec_reg.get_axiom(str_s)
        assert ax is not None

    def test_int_axiom_has_method_specs(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        ax = spec_reg.get_axiom(int_s)
        methods = ax.get_method_specs()
        assert isinstance(methods, dict)
        assert len(methods) > 0

    def test_int_is_not_callable(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        assert spec_reg.is_callable(int_s) is False

    def test_callable_is_callable(self, spec_reg: SpecRegistry):
        callable_s = spec_reg.resolve("callable")
        assert callable_s is not None
        # callable has a call_cap via its axiom or is FuncSpec
        cap = spec_reg.get_call_cap(callable_s)
        callable_by_cap = cap is not None
        callable_by_type = spec_reg.is_callable(callable_s)
        # At minimum one should be true
        assert callable_by_cap or callable_by_type

    def test_func_spec_is_callable(self, spec_reg: SpecRegistry):
        fn = spec_reg.factory.create_func("test_fn", ["int"], return_type_name="str")
        assert spec_reg.is_callable(fn) is True

    def test_any_is_dynamic(self, spec_reg: SpecRegistry):
        any_s = spec_reg.resolve("any")
        assert spec_reg.is_dynamic(any_s) is True

    def test_auto_is_dynamic(self, spec_reg: SpecRegistry):
        auto_s = spec_reg.resolve("auto")
        assert spec_reg.is_dynamic(auto_s) is True

    def test_int_is_not_dynamic(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        assert spec_reg.is_dynamic(int_s) is False

    def test_class_spec_is_class(self, spec_reg: SpecRegistry):
        cls = spec_reg.factory.create_class("Foo")
        assert spec_reg.is_class_spec(cls) is True

    def test_int_spec_is_not_class(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        assert spec_reg.is_class_spec(int_s) is False

    def test_module_spec_is_module(self, spec_reg: SpecRegistry):
        ms = spec_reg.factory.create_module("testmod")
        assert spec_reg.is_module_spec(ms) is True

    def test_int_is_not_module(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        assert spec_reg.is_module_spec(int_s) is False


# ---------------------------------------------------------------------------
# 6. Assignability
# ---------------------------------------------------------------------------

class TestAssignability:
    def test_same_type_assignable(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        assert spec_reg.is_assignable(int_s, int_s) is True

    def test_int_assignable_to_any(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        any_s = spec_reg.resolve("any")
        assert spec_reg.is_assignable(int_s, any_s) is True

    def test_any_not_assignable_to_int(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        any_s = spec_reg.resolve("any")
        assert spec_reg.is_assignable(any_s, int_s) is False

    def test_none_source_or_target(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        # None source = unknown, treat as incompatible
        assert spec_reg.is_assignable(None, int_s) is False
        assert spec_reg.is_assignable(int_s, None) is False


# ---------------------------------------------------------------------------
# 7. Integration: create_default_registry (factory module)
# ---------------------------------------------------------------------------

class TestDefaultRegistry:
    def test_create_default_registry_returns_spec_registry(self):
        reg = create_default_registry()
        assert isinstance(reg, SpecRegistry)

    def test_all_core_types_present(self):
        reg = create_default_registry()
        for name in ("int", "str", "float", "bool", "void", "any", "auto", "callable"):
            assert reg.resolve(name) is not None, f"Missing: {name}"

    def test_list_and_dict_present(self):
        reg = create_default_registry()
        assert reg.resolve("list") is not None
        assert reg.resolve("dict") is not None

    def test_axioms_are_hydrated(self):
        reg = create_default_registry()
        int_s = reg.resolve("int")
        ax = reg.get_axiom(int_s)
        assert ax is not None, "int axiom should be hydrated after create_default_registry"

    def test_operator_cap_on_int(self):
        reg = create_default_registry()
        int_s = reg.resolve("int")
        cap = reg.get_operator_cap(int_s)
        assert cap is not None

    def test_parser_cap_on_int(self):
        reg = create_default_registry()
        int_s = reg.resolve("int")
        cap = reg.get_parser_cap(int_s)
        assert cap is not None

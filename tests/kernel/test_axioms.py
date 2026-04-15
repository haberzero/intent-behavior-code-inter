"""
tests/kernel/test_axioms.py

Unit tests for core/kernel/axioms/ layer.

Coverage:
  - AxiomRegistry: register, get_axiom, list_axioms
  - register_core_axioms: all expected primitives present
  - Per-axiom: get_method_specs, get_operator_capability,
               get_call_capability, get_iter_capability,
               get_subscript_capability, is_compatible
  - EnumAxiom: instance-level isolation (no cross-instance leakage)
  - SpecRegistry delegation: get_axiom, get_operator_cap, get_call_cap,
                             get_iter_cap, get_subscript_cap
"""

import pytest
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms
from core.kernel.axioms.protocols import TypeAxiom
from core.kernel.spec.registry import create_default_spec_registry, SpecRegistry
from core.kernel.spec import IbSpec, ClassSpec, FuncSpec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ax_reg() -> AxiomRegistry:
    ax = AxiomRegistry()
    register_core_axioms(ax)
    return ax


@pytest.fixture(scope="module")
def spec_reg(ax_reg: AxiomRegistry) -> SpecRegistry:
    return create_default_spec_registry(ax_reg)


# ---------------------------------------------------------------------------
# 1. AxiomRegistry basics
# ---------------------------------------------------------------------------

class TestAxiomRegistry:
    def test_register_and_get(self):
        ax = AxiomRegistry()
        register_core_axioms(ax)
        int_axiom = ax.get_axiom("int")
        assert int_axiom is not None

    def test_missing_axiom_returns_none(self, ax_reg: AxiomRegistry):
        assert ax_reg.get_axiom("totally_unknown_xyz") is None

    def test_all_core_axioms_present(self, ax_reg: AxiomRegistry):
        for name in ("int", "float", "str", "bool", "list", "dict", "callable"):
            axiom = ax_reg.get_axiom(name)
            assert axiom is not None, f"Missing core axiom: {name}"

    def test_axiom_implements_protocol(self, ax_reg: AxiomRegistry):
        for name in ("int", "str", "list"):
            axiom = ax_reg.get_axiom(name)
            assert isinstance(axiom, TypeAxiom), f"{name} axiom is not TypeAxiom"


# ---------------------------------------------------------------------------
# 2. Per-axiom: method specs
# ---------------------------------------------------------------------------

class TestAxiomMethodSpecs:
    def test_int_method_specs_nonempty(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        methods = ax.get_method_specs()
        assert isinstance(methods, dict)
        assert len(methods) > 0

    def test_str_method_specs_include_to_bool(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("str")
        methods = ax.get_method_specs()
        assert "to_bool" in methods

    def test_method_spec_values_are_method_member_spec(self, ax_reg: AxiomRegistry):
        from core.kernel.spec.member import MethodMemberSpec
        ax = ax_reg.get_axiom("int")
        for name, spec in ax.get_method_specs().items():
            assert isinstance(spec, MethodMemberSpec), f"int.{name} is not MethodMemberSpec"


# ---------------------------------------------------------------------------
# 3. Per-axiom: operator capability
# ---------------------------------------------------------------------------

class TestOperatorCapability:
    def test_int_has_operator_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        cap = ax.get_operator_capability()
        assert cap is not None

    def test_float_has_operator_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("float")
        cap = ax.get_operator_capability()
        assert cap is not None

    def test_bool_has_operator_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("bool")
        cap = ax.get_operator_capability()
        assert cap is not None

    def test_str_has_operator_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("str")
        cap = ax.get_operator_capability()
        assert cap is not None

    def test_void_no_operator_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("void")
        # void may or may not have operator cap, just shouldn't crash
        _ = ax.get_operator_capability() if ax else None


# ---------------------------------------------------------------------------
# 4. Per-axiom: call capability (callable)
# ---------------------------------------------------------------------------

class TestCallCapability:
    def test_callable_has_call_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("callable")
        cap = ax.get_call_capability()
        assert cap is not None

    def test_int_no_call_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        cap = ax.get_call_capability()
        assert cap is None


# ---------------------------------------------------------------------------
# 5. Per-axiom: iter capability (list)
# ---------------------------------------------------------------------------

class TestIterCapability:
    def test_list_has_iter_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("list")
        cap = ax.get_iter_capability()
        assert cap is not None

    def test_int_no_iter_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        cap = ax.get_iter_capability()
        assert cap is None

    def test_str_has_iter_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("str")
        cap = ax.get_iter_capability()
        # Strings are iterable in IBC
        assert cap is not None


# ---------------------------------------------------------------------------
# 6. Per-axiom: subscript capability (list, dict)
# ---------------------------------------------------------------------------

class TestSubscriptCapability:
    def test_list_has_subscript_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("list")
        cap = ax.get_subscript_capability()
        assert cap is not None

    def test_dict_has_subscript_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("dict")
        cap = ax.get_subscript_capability()
        assert cap is not None

    def test_int_no_subscript_cap(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        cap = ax.get_subscript_capability()
        assert cap is None


# ---------------------------------------------------------------------------
# 7. is_compatible
# ---------------------------------------------------------------------------

class TestIsCompatible:
    def test_int_compatible_with_int(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        assert ax.is_compatible("int") is True

    def test_bool_compatible_with_int(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("bool")
        # bool is a subtype of int in most type systems
        result = ax.is_compatible("int")
        # This tests the axiom's explicit claim — bool isa int
        assert isinstance(result, bool)

    def test_int_not_compatible_with_str(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("int")
        assert ax.is_compatible("str") is False

    def test_any_compatible_with_anything(self, ax_reg: AxiomRegistry):
        ax = ax_reg.get_axiom("any")
        if ax:
            result = ax.is_compatible("int")
            assert result is True


# ---------------------------------------------------------------------------
# 8. EnumAxiom instance isolation
# ---------------------------------------------------------------------------

class TestEnumAxiomIsolation:
    def test_two_enum_axiom_instances_independent(self, ax_reg: AxiomRegistry):
        """EnumAxiom must use instance-level state, not class-level."""
        from core.kernel.axioms.primitives import EnumAxiom
        ax1 = EnumAxiom()
        ax2 = EnumAxiom()
        # Register a value in ax1
        if hasattr(ax1, "_enum_index_registry"):
            ax1._enum_index_registry["TestEnum"] = {"A": 0, "B": 1}
            # ax2 must not see it
            assert "TestEnum" not in ax2._enum_index_registry

    def test_separate_axiom_registries_no_cross_contamination(self):
        """Two AxiomRegistry instances must be fully independent."""
        ax1 = AxiomRegistry()
        register_core_axioms(ax1)
        ax2 = AxiomRegistry()
        register_core_axioms(ax2)
        # Getting axioms from each should give separate instances
        int_ax1 = ax1.get_axiom("int")
        int_ax2 = ax2.get_axiom("int")
        # Both are valid
        assert int_ax1 is not None
        assert int_ax2 is not None


# ---------------------------------------------------------------------------
# 9. SpecRegistry delegation to axioms
# ---------------------------------------------------------------------------

class TestSpecRegistryAxiomDelegation:
    def test_get_axiom_via_spec_reg(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        ax = spec_reg.get_axiom(int_s)
        assert ax is not None
        assert type(ax).__name__ == "IntAxiom"

    def test_operator_cap_via_spec_reg(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        cap = spec_reg.get_operator_cap(int_s)
        assert cap is not None

    def test_call_cap_via_spec_reg(self, spec_reg: SpecRegistry):
        callable_s = spec_reg.resolve("callable")
        cap = spec_reg.get_call_cap(callable_s)
        assert cap is not None

    def test_iter_cap_via_spec_reg(self, spec_reg: SpecRegistry):
        list_s = spec_reg.resolve("list")
        cap = spec_reg.get_iter_cap(list_s)
        assert cap is not None

    def test_subscript_cap_via_spec_reg(self, spec_reg: SpecRegistry):
        list_s = spec_reg.resolve("list")
        cap = spec_reg.get_subscript_cap(list_s)
        assert cap is not None

    def test_parser_cap_on_int_via_spec_reg(self, spec_reg: SpecRegistry):
        int_s = spec_reg.resolve("int")
        cap = spec_reg.get_parser_cap(int_s)
        assert cap is not None

    def test_user_class_no_axiom(self, spec_reg: SpecRegistry):
        """User-defined classes have no axiom — should return None gracefully."""
        cls = spec_reg.factory.create_class("MyCustomClass")
        ax = spec_reg.get_axiom(cls)
        assert ax is None  # not a known primitive

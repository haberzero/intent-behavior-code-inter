"""
Tests for SpecRegistry.resolve_call_return() — unified callable return type resolution.

Validates that the single entry point correctly handles:
- Structural callables (FUNCTION / CALLABLE_SIG) with explicit return_type
- Class constructors → returns class spec itself
- Callable instances (fn_callable with value_type)
- Axiom-backed callables
- resolve_callable_instance_return for __call__ protocol
"""

import pytest

from core.kernel.spec.base import TypeKind, TypeDef, IbSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.registry import SpecRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms


@pytest.fixture
def registry():
    ax = AxiomRegistry()
    register_core_axioms(ax)
    from core.kernel.spec.registry import create_default_spec_registry
    return create_default_spec_registry(ax)


class TestResolveCallReturn:
    """resolve_call_return() unified return type resolution."""

    def test_function_with_explicit_return(self, registry: SpecRegistry):
        """FUNCTION spec with return_type → resolves to declared type."""
        fn_spec = TypeDef(
            name="my_fn",
            kind=TypeKind.FUNCTION.value,
            return_type=TypeRef.of("int"),
            param_types=[TypeRef.of("str")],
        )
        result = registry.resolve_call_return(fn_spec, [registry.resolve("str")])
        assert result is not None
        assert result.name == "int"

    def test_callable_sig_with_return(self, registry: SpecRegistry):
        """CALLABLE_SIG spec with return_type → resolves to declared type."""
        sig_spec = TypeDef(
            name="my_sig",
            kind=TypeKind.CALLABLE_SIG.value,
            return_type=TypeRef.of("bool"),
            param_types=[TypeRef.of("int")],
        )
        result = registry.resolve_call_return(sig_spec, [registry.resolve("int")])
        assert result is not None
        assert result.name == "bool"

    def test_class_constructor(self, registry: SpecRegistry):
        """CLASS spec called as constructor → returns itself."""
        class_spec = TypeDef(
            name="MyClass",
            kind=TypeKind.CLASS.value,
            is_user_defined=True,
        )
        registry.register(class_spec)
        result = registry.resolve_call_return(class_spec, [])
        assert result is class_spec

    def test_primitive_class_constructor(self, registry: SpecRegistry):
        """Primitive (int) used as constructor/cast → returns itself."""
        int_spec = registry.resolve("int")
        result = registry.resolve_call_return(int_spec, [])
        assert result is not None
        assert result.name == "int"

    def test_primitive_list_constructor(self, registry: SpecRegistry):
        """Primitive list constructor → returns itself."""
        list_spec = registry.resolve("list")
        result = registry.resolve_call_return(list_spec, [])
        assert result is not None
        assert result.name == "list"

    def test_callable_instance_with_value_type(self, registry: SpecRegistry):
        """CALLABLE_INSTANCE with value_type → resolves to value_type."""
        ci_spec = TypeDef(
            name="typed_fn",
            kind=TypeKind.CALLABLE_INSTANCE.value,
            value_type=TypeRef.of("str"),
        )
        result = registry.resolve_call_return(ci_spec, [])
        assert result is not None
        assert result.name == "str"

    def test_callable_instance_auto_value_type(self, registry: SpecRegistry):
        """CALLABLE_INSTANCE with auto/any value_type → returns any."""
        ci_spec = TypeDef(
            name="untyped_fn",
            kind=TypeKind.CALLABLE_INSTANCE.value,
            value_type=TypeRef.of("auto"),
        )
        result = registry.resolve_call_return(ci_spec, [])
        assert result is not None
        assert result.name == "any"

    def test_not_callable_returns_none(self, registry: SpecRegistry):
        """Non-callable spec → returns None."""
        # A bare primitive without call cap and not CLASS/FUNCTION etc.
        # Create a spec with a kind that's not callable
        spec = TypeDef(
            name="some_value",
            kind=TypeKind.PRIMITIVE.value,
        )
        result = registry.resolve_call_return(spec, [])
        # Primitives without axiom call cap → None
        assert result is None

    def test_none_callee_returns_none(self, registry: SpecRegistry):
        """None callee → returns None."""
        result = registry.resolve_call_return(None, [])
        assert result is None

    def test_bound_method_with_return(self, registry: SpecRegistry):
        """BOUND_METHOD spec with return_type → resolves to declared type."""
        bm_spec = TypeDef(
            name="my_method",
            kind=TypeKind.BOUND_METHOD.value,
            return_type=TypeRef.of("float"),
        )
        result = registry.resolve_call_return(bm_spec, [])
        assert result is not None
        assert result.name == "float"


class TestResolveCallableInstanceReturn:
    """resolve_callable_instance_return() for __call__ protocol."""

    def test_class_with_call_method(self, registry: SpecRegistry):
        """Class with __call__ member → resolves __call__ return type."""
        class_spec = TypeDef(
            name="CallableClass",
            kind=TypeKind.CLASS.value,
            is_user_defined=True,
            members={
                "__call__": MethodMemberSpec(
                    name="__call__",
                    return_type=TypeRef.of("int"),
                    param_types=[],
                ),
            },
        )
        registry.register(class_spec)
        result = registry.resolve_callable_instance_return(class_spec, [])
        assert result is not None
        assert result.name == "int"

    def test_class_without_call(self, registry: SpecRegistry):
        """Class without __call__ → returns None."""
        class_spec = TypeDef(
            name="PlainClass",
            kind=TypeKind.CLASS.value,
            is_user_defined=True,
        )
        result = registry.resolve_callable_instance_return(class_spec, [])
        assert result is None

    def test_non_class_returns_none(self, registry: SpecRegistry):
        """Non-CLASS spec → returns None."""
        fn_spec = TypeDef(
            name="fn",
            kind=TypeKind.FUNCTION.value,
            return_type=TypeRef.of("int"),
        )
        result = registry.resolve_callable_instance_return(fn_spec, [])
        assert result is None

    def test_class_scope_lookup_preferred(self, registry: SpecRegistry):
        """class_scope_lookup callback is preferred over resolve_member."""
        class_spec = TypeDef(
            name="DynClass",
            kind=TypeKind.CLASS.value,
            is_user_defined=True,
            members={
                "__call__": MethodMemberSpec(
                    name="__call__",
                    return_type=TypeRef.of("str"),  # member says str
                    param_types=[],
                ),
            },
        )
        registry.register(class_spec)

        # scope lookup overrides to return a function spec with "bool" return
        override_spec = TypeDef(
            name="__call__",
            kind=TypeKind.FUNCTION.value,
            return_type=TypeRef.of("bool"),
        )

        def lookup(cls_name, method_name):
            if cls_name == "DynClass" and method_name == "__call__":
                return override_spec
            return None

        result = registry.resolve_callable_instance_return(
            class_spec, [], class_scope_lookup=lookup
        )
        assert result is not None
        assert result.name == "bool"

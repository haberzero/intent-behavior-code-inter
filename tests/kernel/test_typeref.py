"""
tests/kernel/test_typeref.py

TypeRef 回归测试。

覆盖范围：
  1. TypeRef 基础构造（非泛型、泛型、含模块限定）
  2. canonical_name / qualified_name 派生属性
  3. 嵌套泛型（list[dict[str,int]]）
  4. 可哈希性（dict key、set 成员）
  5. frozen 不可变性（不可原地修改）
  6. TypeRef.of() / TypeRef.generic() 工厂
  7. TypeRef.from_spec() 桥接：各主要 IbSpec 子类
  8. substitute() 泛型替换
  9. is_generic() / is_builtin() / with_module()
  10. IbSpec.type_ref 桥接属性
  11. FuncSpec.return_type_ref / param_type_refs
  12. ClassSpec.parent_type_ref
  13. ListSpec.element_type_ref
  14. TupleSpec.element_type_ref
  15. DictSpec.key_type_ref / value_type_ref
  16. DeferredSpec.value_type_ref
  17. MemberSpec.type_ref
  18. MethodMemberSpec.return_type_ref / param_type_refs
  19. SpecRegistry.resolve_typeref()（含泛型、跨模块）
  20. TypeRef 相等与哈希一致性（等值对象哈希相同）
"""

import pytest
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec import (
    IbSpec,
    FuncSpec, ClassSpec, ListSpec, TupleSpec, DictSpec, DeferredSpec, OptionalSpec,
    MemberSpec, MethodMemberSpec,
    INT_SPEC, STR_SPEC, ANY_SPEC,
)
from core.kernel.spec.specs import BehaviorSpec
from core.kernel.spec.base import TypeKind
from core.kernel.spec.registry import SpecRegistry, create_default_spec_registry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def spec_reg() -> SpecRegistry:
    ax = AxiomRegistry()
    register_core_axioms(ax)
    return create_default_spec_registry(ax)


# ---------------------------------------------------------------------------
# 1. 基础构造
# ---------------------------------------------------------------------------

class TestTypeRefConstruction:
    def test_simple_non_generic(self):
        r = TypeRef("int")
        assert r.head == "int"
        assert r.args == ()
        assert r.module is None

    def test_generic_one_arg(self):
        r = TypeRef("list", (TypeRef("int"),))
        assert r.head == "list"
        assert len(r.args) == 1
        assert r.args[0].head == "int"

    def test_generic_two_args(self):
        r = TypeRef("dict", (TypeRef("str"), TypeRef("int")))
        assert r.args[0].head == "str"
        assert r.args[1].head == "int"

    def test_with_module(self):
        r = TypeRef("Foo", (), module="mymod")
        assert r.module == "mymod"
        assert r.head == "Foo"

    def test_default_args_is_empty_tuple(self):
        r = TypeRef("int")
        assert isinstance(r.args, tuple)
        assert len(r.args) == 0


# ---------------------------------------------------------------------------
# 2. canonical_name / qualified_name
# ---------------------------------------------------------------------------

class TestTypeRefNames:
    def test_canonical_simple(self):
        assert TypeRef("int").canonical_name == "int"

    def test_canonical_generic_one(self):
        r = TypeRef("list", (TypeRef("int"),))
        assert r.canonical_name == "list[int]"

    def test_canonical_generic_two(self):
        r = TypeRef("dict", (TypeRef("str"), TypeRef("int")))
        assert r.canonical_name == "dict[str,int]"

    def test_canonical_nested(self):
        # list[dict[str,int]]
        inner = TypeRef("dict", (TypeRef("str"), TypeRef("int")))
        outer = TypeRef("list", (inner,))
        assert outer.canonical_name == "list[dict[str,int]]"

    def test_qualified_name_no_module(self):
        assert TypeRef("int").qualified_name == "int"

    def test_qualified_name_with_module(self):
        r = TypeRef("Foo", (), module="mymod")
        assert r.qualified_name == "mymod.Foo"

    def test_qualified_name_generic_with_module(self):
        r = TypeRef("list", (TypeRef("int"),), module="mymod")
        assert r.qualified_name == "mymod.list[int]"

    def test_str_equals_qualified_name(self):
        r = TypeRef("Foo", (), module="m")
        assert str(r) == r.qualified_name


# ---------------------------------------------------------------------------
# 3. 嵌套泛型
# ---------------------------------------------------------------------------

class TestNestedGenerics:
    def test_three_levels(self):
        # list[list[list[int]]]
        level1 = TypeRef("int")
        level2 = TypeRef("list", (level1,))
        level3 = TypeRef("list", (level2,))
        level4 = TypeRef("list", (level3,))
        assert level4.canonical_name == "list[list[list[int]]]"

    def test_dict_of_list(self):
        # dict[str, list[int]]
        r = TypeRef("dict", (TypeRef("str"), TypeRef("list", (TypeRef("int"),))))
        assert r.canonical_name == "dict[str,list[int]]"

    def test_list_of_dict_of_list(self):
        inner = TypeRef("dict", (TypeRef("str"), TypeRef("list", (TypeRef("int"),))))
        outer = TypeRef("list", (inner,))
        assert outer.canonical_name == "list[dict[str,list[int]]]"


# ---------------------------------------------------------------------------
# 4. 可哈希性
# ---------------------------------------------------------------------------

class TestHashability:
    def test_use_as_dict_key(self):
        r = TypeRef("int")
        d = {r: "int_value"}
        assert d[TypeRef("int")] == "int_value"

    def test_equal_typeref_same_hash(self):
        r1 = TypeRef("list", (TypeRef("int"),))
        r2 = TypeRef("list", (TypeRef("int"),))
        assert r1 == r2
        assert hash(r1) == hash(r2)

    def test_in_set(self):
        s = {TypeRef("int"), TypeRef("str"), TypeRef("int")}
        assert len(s) == 2

    def test_different_module_different_hash(self):
        r1 = TypeRef("Foo", (), module=None)
        r2 = TypeRef("Foo", (), module="mod")
        assert r1 != r2

    def test_generic_hashable(self):
        r = TypeRef("dict", (TypeRef("str"), TypeRef("int")))
        s = {r}
        assert r in s


# ---------------------------------------------------------------------------
# 5. frozen 不可变性
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_cannot_set_head(self):
        r = TypeRef("int")
        with pytest.raises((AttributeError, TypeError)):
            r.head = "str"  # type: ignore[misc]

    def test_cannot_set_args(self):
        r = TypeRef("list", (TypeRef("int"),))
        with pytest.raises((AttributeError, TypeError)):
            r.args = ()  # type: ignore[misc]

    def test_cannot_set_module(self):
        r = TypeRef("int")
        with pytest.raises((AttributeError, TypeError)):
            r.module = "mod"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6. 工厂方法
# ---------------------------------------------------------------------------

class TestFactories:
    def test_of_simple(self):
        r = TypeRef.of("int")
        assert r == TypeRef("int")
        assert r.module is None

    def test_of_with_module(self):
        r = TypeRef.of("Foo", "mymod")
        assert r.head == "Foo"
        assert r.module == "mymod"

    def test_generic_factory(self):
        r = TypeRef.generic("list", TypeRef.of("int"))
        assert r == TypeRef("list", (TypeRef("int"),))

    def test_generic_factory_two_args(self):
        r = TypeRef.generic("dict", TypeRef.of("str"), TypeRef.of("int"))
        assert r.canonical_name == "dict[str,int]"

    def test_generic_factory_no_args(self):
        r = TypeRef.generic("list")
        assert r == TypeRef("list")
        assert r.args == ()


# ---------------------------------------------------------------------------
# 7. from_spec() 桥接
# ---------------------------------------------------------------------------

class TestFromSpec:
    def test_primitive_spec(self):
        r = TypeRef.from_spec(INT_SPEC)
        assert r.head == "int"
        assert r.args == ()
        assert r.module is None

    def test_any_spec(self):
        r = TypeRef.from_spec(ANY_SPEC)
        assert r.head == "any"

    def test_list_spec_bare(self):
        from core.kernel.spec.specs import LIST_SPEC
        r = TypeRef.from_spec(LIST_SPEC)
        assert r.head == "list"
        # bare list → no args
        assert r.args == ()

    def test_list_spec_typed(self):
        from core.kernel.spec.specs import ListSpec
        spec = ListSpec(name="list[int]", element_type_name="int", kind=TypeKind.LIST.value)
        r = TypeRef.from_spec(spec)
        assert r.head == "list"
        assert len(r.args) == 1
        assert r.args[0].head == "int"

    def test_dict_spec(self):
        from core.kernel.spec.specs import DictSpec
        spec = DictSpec(name="dict[str,int]", key_type_name="str", value_type_name="int", kind=TypeKind.DICT.value)
        r = TypeRef.from_spec(spec)
        assert r.head == "dict"
        assert r.args[0].head == "str"
        assert r.args[1].head == "int"

    def test_tuple_spec_typed(self):
        from core.kernel.spec.specs import TupleSpec
        spec = TupleSpec(name="tuple[str]", element_type_name="str", kind=TypeKind.TUPLE.value)
        r = TypeRef.from_spec(spec)
        assert r.head == "tuple"
        assert r.args[0].head == "str"

    def test_class_spec(self):
        spec = ClassSpec(name="MyClass", module_path="mymod")
        r = TypeRef.from_spec(spec)
        assert r.head == "MyClass"
        assert r.module == "mymod"

    def test_deferred_spec_typed(self):
        spec = DeferredSpec(name="deferred[int]", value_type_name="int",
                            kind=TypeKind.CALLABLE_INSTANCE.value, _axiom_name="deferred")
        r = TypeRef.from_spec(spec)
        assert r.head == "deferred"
        assert r.args[0].head == "int"

    def test_deferred_spec_untyped(self):
        spec = DeferredSpec(name="deferred", value_type_name="auto",
                            kind=TypeKind.CALLABLE_INSTANCE.value)
        r = TypeRef.from_spec(spec)
        assert r.head == "deferred"
        assert r.args == ()

    def test_behavior_spec_typed(self):
        spec = BehaviorSpec(name="behavior[str]", value_type_name="str",
                            kind=TypeKind.CALLABLE_INSTANCE.value, _axiom_name="behavior")
        r = TypeRef.from_spec(spec)
        assert r.head == "behavior"
        assert r.args[0].head == "str"

    def test_optional_spec_typed(self):
        spec = OptionalSpec(name="Optional[int]", wrapped_type_name="int", kind=TypeKind.OPTIONAL.value)
        r = TypeRef.from_spec(spec)
        assert r.head == "Optional"
        assert r.args[0].head == "int"


# ---------------------------------------------------------------------------
# 8. substitute()
# ---------------------------------------------------------------------------

class TestSubstitute:
    def test_simple_substitution(self):
        t = TypeRef("T")
        mapping = {"T": TypeRef("int")}
        result = t.substitute(mapping)
        assert result == TypeRef("int")

    def test_no_match_unchanged(self):
        t = TypeRef("int")
        result = t.substitute({"T": TypeRef("str")})
        assert result is t  # identity: no change

    def test_nested_substitution(self):
        # list[T].substitute(T→int) → list[int]
        t = TypeRef("list", (TypeRef("T"),))
        result = t.substitute({"T": TypeRef("int")})
        assert result == TypeRef("list", (TypeRef("int"),))

    def test_nested_substitution_two_params(self):
        # dict[K,V].substitute(K→str, V→int) → dict[str,int]
        t = TypeRef("dict", (TypeRef("K"), TypeRef("V")))
        result = t.substitute({"K": TypeRef("str"), "V": TypeRef("int")})
        assert result == TypeRef("dict", (TypeRef("str"), TypeRef("int")))

    def test_partial_substitution(self):
        # dict[K,V].substitute(K→str) → dict[str,V]
        t = TypeRef("dict", (TypeRef("K"), TypeRef("V")))
        result = t.substitute({"K": TypeRef("str")})
        assert result.args[0] == TypeRef("str")
        assert result.args[1] == TypeRef("V")

    def test_deep_nested_substitution(self):
        # list[list[T]].substitute(T→bool) → list[list[bool]]
        inner = TypeRef("list", (TypeRef("T"),))
        outer = TypeRef("list", (inner,))
        result = outer.substitute({"T": TypeRef("bool")})
        assert result.canonical_name == "list[list[bool]]"

    def test_no_change_returns_same_object(self):
        t = TypeRef("int")
        result = t.substitute({})
        assert result is t

    def test_args_unchanged_returns_same_object(self):
        # When substitution produces same args, the same TypeRef is returned
        t = TypeRef("list", (TypeRef("int"),))
        result = t.substitute({"T": TypeRef("str")})
        assert result is t


# ---------------------------------------------------------------------------
# 9. is_generic / is_builtin / with_module
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_is_generic_true(self):
        assert TypeRef("list", (TypeRef("int"),)).is_generic()

    def test_is_generic_false(self):
        assert not TypeRef("int").is_generic()

    def test_is_builtin_true(self):
        assert TypeRef("int").is_builtin()

    def test_is_builtin_false(self):
        assert not TypeRef("Foo", (), module="m").is_builtin()

    def test_with_module_adds(self):
        r = TypeRef("int").with_module("mymod")
        assert r.module == "mymod"
        assert r.head == "int"

    def test_with_module_same_is_identity(self):
        r = TypeRef("int", (), module="m")
        assert r.with_module("m") is r

    def test_with_module_removes(self):
        r = TypeRef("Foo", (), module="m").with_module(None)
        assert r.module is None


# ---------------------------------------------------------------------------
# 10. IbSpec.type_ref 桥接属性
# ---------------------------------------------------------------------------

class TestIbSpecBridge:
    def test_primitive_type_ref(self):
        from core.kernel.spec import INT_SPEC
        r = INT_SPEC.type_ref
        assert isinstance(r, TypeRef)
        assert r.head == "int"

    def test_class_spec_type_ref(self):
        spec = ClassSpec(name="MyClass", module_path="mod")
        r = spec.type_ref
        assert r.head == "MyClass"
        assert r.module == "mod"

    def test_list_spec_typed_type_ref(self):
        spec = ListSpec(name="list[int]", element_type_name="int", kind=TypeKind.LIST.value)
        r = spec.type_ref
        assert r.head == "list"
        assert r.args == (TypeRef("int"),)

    def test_dict_spec_type_ref(self):
        spec = DictSpec(name="dict[str,int]", key_type_name="str", value_type_name="int")
        r = spec.type_ref
        assert r.canonical_name == "dict[str,int]"


# ---------------------------------------------------------------------------
# 11. FuncSpec.return_type_ref / param_type_refs
# ---------------------------------------------------------------------------

class TestFuncSpecBridge:
    def test_return_type_ref_simple(self):
        spec = FuncSpec(name="f", return_type_name="int")
        assert spec.return_type_ref == TypeRef("int")

    def test_return_type_ref_with_module(self):
        spec = FuncSpec(name="f", return_type_name="MyClass", return_type_module="mod")
        assert spec.return_type_ref == TypeRef.of("MyClass", "mod")

    def test_param_type_refs_empty(self):
        spec = FuncSpec(name="f")
        assert spec.param_type_refs == ()

    def test_param_type_refs_basic(self):
        spec = FuncSpec(
            name="f",
            param_type_names=["int", "str"],
            param_type_modules=[None, None],
        )
        refs = spec.param_type_refs
        assert refs == (TypeRef("int"), TypeRef("str"))

    def test_param_type_refs_with_module(self):
        spec = FuncSpec(
            name="f",
            param_type_names=["Foo"],
            param_type_modules=["mymod"],
        )
        refs = spec.param_type_refs
        assert refs[0] == TypeRef.of("Foo", "mymod")

    def test_param_type_refs_shorter_modules(self):
        # modules list shorter than names list — should pad with None
        spec = FuncSpec(
            name="f",
            param_type_names=["int", "str", "bool"],
            param_type_modules=[],
        )
        refs = spec.param_type_refs
        assert len(refs) == 3
        assert all(r.module is None for r in refs)


# ---------------------------------------------------------------------------
# 12. ClassSpec.parent_type_ref
# ---------------------------------------------------------------------------

class TestClassSpecBridge:
    def test_parent_type_ref_with_parent(self):
        spec = ClassSpec(name="Dog", parent_name="Animal")
        assert spec.parent_type_ref == TypeRef("Animal")

    def test_parent_type_ref_with_module(self):
        spec = ClassSpec(name="Sub", parent_name="Base", parent_module="base_mod")
        assert spec.parent_type_ref == TypeRef.of("Base", "base_mod")

    def test_parent_type_ref_none_when_no_parent(self):
        spec = ClassSpec(name="Root")
        assert spec.parent_type_ref is None


# ---------------------------------------------------------------------------
# 13 / 14. ListSpec.element_type_ref / TupleSpec.element_type_ref
# ---------------------------------------------------------------------------

class TestContainerSpecBridge:
    def test_list_element_type_ref(self):
        spec = ListSpec(name="list[int]", element_type_name="int")
        assert spec.element_type_ref == TypeRef("int")

    def test_list_element_type_ref_any(self):
        from core.kernel.spec import LIST_SPEC
        assert LIST_SPEC.element_type_ref == TypeRef("any")

    def test_tuple_element_type_ref(self):
        spec = TupleSpec(name="tuple[str]", element_type_name="str")
        assert spec.element_type_ref == TypeRef("str")

    def test_dict_key_type_ref(self):
        spec = DictSpec(name="dict[str,int]", key_type_name="str", value_type_name="int")
        assert spec.key_type_ref == TypeRef("str")

    def test_dict_value_type_ref(self):
        spec = DictSpec(name="dict[str,int]", key_type_name="str", value_type_name="int")
        assert spec.value_type_ref == TypeRef("int")


# ---------------------------------------------------------------------------
# 15. DeferredSpec.value_type_ref
# ---------------------------------------------------------------------------

class TestDeferredSpecBridge:
    def test_value_type_ref_typed(self):
        spec = DeferredSpec(name="deferred[int]", value_type_name="int")
        assert spec.value_type_ref == TypeRef("int")

    def test_value_type_ref_auto(self):
        spec = DeferredSpec(name="deferred", value_type_name="auto")
        assert spec.value_type_ref == TypeRef("auto")

    def test_behavior_spec_value_type_ref(self):
        spec = BehaviorSpec(name="behavior[str]", value_type_name="str")
        assert spec.value_type_ref == TypeRef("str")


class TestOptionalSpecBridge:
    def test_wrapped_type_ref(self):
        spec = OptionalSpec(name="Optional[int]", wrapped_type_name="int")
        assert spec.wrapped_type_ref == TypeRef("int")


# ---------------------------------------------------------------------------
# 16. MemberSpec.type_ref
# ---------------------------------------------------------------------------

class TestMemberSpecBridge:
    def test_field_type_ref(self):
        m = MemberSpec(name="age", kind="field", type_name="int")
        assert m.type_ref == TypeRef("int")

    def test_field_type_ref_with_module(self):
        m = MemberSpec(name="obj", kind="field", type_name="MyClass", type_module="mod")
        assert m.type_ref == TypeRef.of("MyClass", "mod")

    def test_default_type_ref_is_any(self):
        m = MemberSpec(name="x", kind="field")
        assert m.type_ref == TypeRef("any")


# ---------------------------------------------------------------------------
# 17. MethodMemberSpec.return_type_ref / param_type_refs
# ---------------------------------------------------------------------------

class TestMethodMemberSpecBridge:
    def test_return_type_ref(self):
        m = MethodMemberSpec(name="greet", return_type_name="str")
        assert m.return_type_ref == TypeRef("str")

    def test_return_type_ref_void(self):
        m = MethodMemberSpec(name="do_nothing")
        assert m.return_type_ref == TypeRef("void")

    def test_param_type_refs_basic(self):
        m = MethodMemberSpec(
            name="add",
            param_type_names=["int", "int"],
            param_type_modules=[None, None],
        )
        assert m.param_type_refs == (TypeRef("int"), TypeRef("int"))

    def test_param_type_refs_empty(self):
        m = MethodMemberSpec(name="get_value")
        assert m.param_type_refs == ()

    def test_param_type_refs_with_module(self):
        m = MethodMemberSpec(
            name="process",
            param_type_names=["Request"],
            param_type_modules=["http"],
        )
        refs = m.param_type_refs
        assert refs[0] == TypeRef.of("Request", "http")


# ---------------------------------------------------------------------------
# 18. SpecRegistry.resolve_typeref()
# ---------------------------------------------------------------------------

class TestSpecRegistryResolveTypeRef:
    def test_resolve_primitive(self, spec_reg):
        r = TypeRef.of("int")
        spec = spec_reg.resolve_typeref(r)
        assert spec is not None
        assert spec.name == "int"

    def test_resolve_str(self, spec_reg):
        r = TypeRef.of("str")
        spec = spec_reg.resolve_typeref(r)
        assert spec is not None
        assert spec.name == "str"

    def test_resolve_any(self, spec_reg):
        r = TypeRef.of("any")
        spec = spec_reg.resolve_typeref(r)
        assert spec is not None

    def test_resolve_unknown_returns_none(self, spec_reg):
        r = TypeRef.of("NonExistentType")
        spec = spec_reg.resolve_typeref(r)
        assert spec is None

    def test_resolve_generic_falls_back_to_base(self, spec_reg):
        # list[int] → 先找 "list[int]"（若已注册）否则找 "list"
        r = TypeRef.generic("list", TypeRef.of("int"))
        spec = spec_reg.resolve_typeref(r)
        # 至少应该找到 list 基础 spec
        assert spec is not None
        assert spec.get_base_name() == "list"

    def test_resolve_registered_specialization(self, spec_reg):
        # 注册 list[int] 后 resolve_typeref 应精确匹配
        list_base = spec_reg.resolve("list")
        int_spec = spec_reg.resolve("int")
        specialized = spec_reg.resolve_specialization(list_base, [int_spec])
        if specialized is not None:
            r = TypeRef.generic("list", TypeRef.of("int"))
            found = spec_reg.resolve_typeref(r)
            assert found is not None
            assert found.get_base_name() == "list"

    def test_resolve_exception_type(self, spec_reg):
        r = TypeRef.of("Exception")
        spec = spec_reg.resolve_typeref(r)
        assert spec is not None
        assert spec.name == "Exception"

    def test_resolve_llm_error(self, spec_reg):
        r = TypeRef.of("LLMError")
        spec = spec_reg.resolve_typeref(r)
        assert spec is not None

    def test_resolve_with_module_cross_module(self, spec_reg):
        # 跨模块引用：模块内已注册的类应能找到
        spec = spec_reg.factory.create_class("RemoteClass", module="remote_mod")
        spec_reg.register(spec)
        r = TypeRef.of("RemoteClass", "remote_mod")
        found = spec_reg.resolve_typeref(r)
        assert found is not None
        assert found.name == "RemoteClass"

    def test_resolve_optional_specialization(self, spec_reg):
        optional_base = spec_reg.resolve("Optional")
        int_spec = spec_reg.resolve("int")
        optional_int = spec_reg.resolve_specialization(optional_base, [int_spec])
        assert optional_int is not None
        found = spec_reg.resolve_typeref(TypeRef.generic("Optional", TypeRef.of("int")))
        assert found is not None
        assert found.name == "Optional[int]"


# ---------------------------------------------------------------------------
# 19. TypeRef 等值与哈希一致性
# ---------------------------------------------------------------------------

class TestEqualityAndHash:
    def test_same_head_equal(self):
        assert TypeRef("int") == TypeRef("int")

    def test_same_head_same_hash(self):
        assert hash(TypeRef("int")) == hash(TypeRef("int"))

    def test_different_head_not_equal(self):
        assert TypeRef("int") != TypeRef("str")

    def test_generic_equality(self):
        r1 = TypeRef("list", (TypeRef("int"),))
        r2 = TypeRef("list", (TypeRef("int"),))
        assert r1 == r2
        assert hash(r1) == hash(r2)

    def test_different_args_not_equal(self):
        r1 = TypeRef("list", (TypeRef("int"),))
        r2 = TypeRef("list", (TypeRef("str"),))
        assert r1 != r2

    def test_module_difference_not_equal(self):
        r1 = TypeRef("Foo", (), module="a")
        r2 = TypeRef("Foo", (), module="b")
        assert r1 != r2

    def test_module_none_vs_present_not_equal(self):
        r1 = TypeRef("int")
        r2 = TypeRef("int", (), module="m")
        assert r1 != r2

    def test_hashable_in_frozenset(self):
        fs = frozenset([TypeRef("int"), TypeRef("str"), TypeRef("int")])
        assert len(fs) == 2


# ---------------------------------------------------------------------------
# 20. TypeRef repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_simple_repr(self):
        r = TypeRef("int")
        assert "int" in repr(r)
        assert "TypeRef" in repr(r)

    def test_generic_repr_contains_args(self):
        r = TypeRef("list", (TypeRef("int"),))
        s = repr(r)
        assert "list" in s
        assert "int" in s

    def test_module_in_repr(self):
        r = TypeRef("Foo", (), module="m")
        assert "m" in repr(r)

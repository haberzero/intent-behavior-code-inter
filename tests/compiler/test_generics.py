"""
tests/compiler/test_generics.py — 泛型编译期契约（compile-only）。

编译期语义：

* ``resolve_specialization`` 早缓存
* ``dict[K,V].get`` / ``.values`` / ``.keys`` 返回类型 specialization
* list[int] 协变
* 泛型注解符号声明保留泛型身份（运行时内省/序列化不退化）

运行时执行用例见 tests/e2e/test_generics_runtime.py（mixed-concerns 拆分）。
"""
import pytest

from core.kernel.factory import create_default_registry
from core.kernel.issue import CompilerError
from core.kernel.spec import SpecRegistry, TypeDef
from tests.conftest import compile_ibci, expect_compile_error


# ---------------------------------------------------------------------------
# 共享 helper（compile-only；diag 为 diagnostics 列表）
# ---------------------------------------------------------------------------

def make_spec_registry() -> SpecRegistry:
    """Create a fully initialized SpecRegistry with all built-in axioms registered."""
    return create_default_registry()


def make_registry():
    return create_default_registry()


def _compile_code(code: str):
    """Compile only; return (artifact_or_None, diagnostics_list)."""
    try:
        return compile_ibci(code), []
    except CompilerError as e:
        return None, list(e.diagnostics)


def _sem_errors(diagnostics):
    return [d for d in diagnostics if d.severity.name == "ERROR"]


################################################################################
# generics: early cache
################################################################################

class TestSpecializationCache:
    def test_second_call_returns_same_object(self):
        """resolve_specialization hit → returns same registered spec on second call."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        int_spec = reg.resolve("int")

        first = reg.resolve_specialization(list_spec, [int_spec])
        second = reg.resolve_specialization(list_spec, [int_spec])
        assert first is second, "second specialization call should return cached object"

    def test_cache_is_distinct_per_element_type(self):
        """list[int] and list[str] are distinct cached specs."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        int_spec = reg.resolve("int")
        str_spec = reg.resolve("str")

        list_int = reg.resolve_specialization(list_spec, [int_spec])
        list_str = reg.resolve_specialization(list_spec, [str_spec])
        assert list_int is not list_str

    def test_resolve_finds_cached_spec_by_name(self):
        """After first specialization, reg.resolve('list[int]') returns the same spec."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        int_spec = reg.resolve("int")

        created = reg.resolve_specialization(list_spec, [int_spec])
        looked_up = reg.resolve("list[int]")
        assert created is looked_up


# ===========================================================================
# 内置泛型赋值特化实参校验（X[int] → X[str] 编译期拦截）
# ===========================================================================

class TestGenericAssignability:
    """内置泛型同家族特化赋值必须校验实参。

    axiom ``is_compatible`` 用 ``startswith("list[")`` 前缀匹配会无视实参，
    使 ``X[int]`` 可赋给 ``X[str]``（Optional 与用户类本就正确拦截）。
    ``is_assignable`` 在 axiom 兼容前先做同家族结构化实参比较。
    """

    def _specialize(self, reg, base: str, *arg_names: str):
        base_spec = reg.resolve(base)
        args = [reg.resolve(a) for a in arg_names]
        return reg.resolve_specialization(base_spec, args)

    @pytest.mark.parametrize("base,args_src,args_tgt", [
        ("thread", ["int"], ["str"]),
        ("thread_result", ["int"], ["str"]),
        ("chan", ["int"], ["str"]),
        ("slot", ["int"], ["str"]),
        ("generator", ["int"], ["str"]),
        ("fn_callable", ["int"], ["str"]),
        ("behavior", ["int"], ["str"]),
        ("list", ["int"], ["str"]),
        ("tuple", ["int", "str"], ["str", "int"]),
    ])
    def test_same_family_mismatched_args_rejected(self, base, args_src, args_tgt):
        """同泛型家族、实参不兼容（X[int]→X[str]）必须拒绝。"""
        reg = make_registry()
        src = self._specialize(reg, base, *args_src)
        tgt = self._specialize(reg, base, *args_tgt)
        assert not reg.is_assignable(src, tgt), (
            f"{src.name} should NOT be assignable to {tgt.name}"
        )

    def test_dict_mismatched_value_type_rejected(self):
        """dict[str,int] → dict[str,str] 必须拒绝（key 同、value 异）。"""
        reg = make_registry()
        src = self._specialize(reg, "dict", "str", "int")
        tgt = self._specialize(reg, "dict", "str", "str")
        assert not reg.is_assignable(src, tgt)

    def test_same_family_same_args_allowed(self):
        """同泛型家族、实参相同仍放行（is_assignable 早期 :62 name 命中）。"""
        reg = make_registry()
        src = self._specialize(reg, "list", "int")
        tgt = self._specialize(reg, "list", "int")
        assert reg.is_assignable(src, tgt)

    def test_covariance_specialized_to_bare_allowed(self):
        """协变：list[int] → list（特化 → 裸基类）放行。"""
        reg = make_registry()
        src = self._specialize(reg, "list", "int")
        tgt = reg.resolve("list")
        assert reg.is_assignable(src, tgt), "list[int] should be assignable to list"

    def test_bare_to_specialized_keeps_existing_semantics(self):
        """裸 → 特化（list → list[int]）保持既有放行语义（不收紧方向）。"""
        reg = make_registry()
        src = reg.resolve("list")
        tgt = self._specialize(reg, "list", "int")
        assert reg.is_assignable(src, tgt)

    def test_optional_mismatch_still_rejected(self):
        """Optional[int] → Optional[str] 由 OPTIONAL 专门分支拦截（不回归）。"""
        reg = make_registry()
        src = self._specialize(reg, "Optional", "int")
        tgt = self._specialize(reg, "Optional", "str")
        assert not reg.is_assignable(src, tgt)

    def test_non_generic_subtype_compat_preserved(self):
        """非泛型子类型兼容（bool isa int）不受影响。"""
        reg = make_registry()
        assert reg.is_assignable(reg.resolve("bool"), reg.resolve("int"))

    def test_nested_generic_mismatch_rejected(self):
        """嵌套泛型实参递归：list[list[int]] → list[list[str]] 拒绝。"""
        reg = make_registry()
        li = self._specialize(reg, "list", "int")
        ls = self._specialize(reg, "list", "str")
        src = reg.resolve_specialization(reg.resolve("list"), [li])
        tgt = reg.resolve_specialization(reg.resolve("list"), [ls])
        assert not reg.is_assignable(src, tgt), (
            "list[list[int]] should NOT be assignable to list[list[str]]"
        )

    def test_cross_family_behavior_to_fn_callable_mismatch_rejected(self):
        """跨家族子类型：behavior[int] → fn_callable[str] 实参不兼容拒绝。"""
        reg = make_registry()
        src = self._specialize(reg, "behavior", "int")
        tgt = self._specialize(reg, "fn_callable", "str")
        assert not reg.is_assignable(src, tgt), (
            "behavior[int] should NOT be assignable to fn_callable[str]"
        )

    def test_cross_family_behavior_to_fn_callable_same_args_allowed(self):
        """跨家族子类型：behavior[int] → fn_callable[int]（子→父，实参兼容）放行。"""
        reg = make_registry()
        src = self._specialize(reg, "behavior", "int")
        tgt = self._specialize(reg, "fn_callable", "int")
        assert reg.is_assignable(src, tgt), (
            "behavior[int] should be assignable to fn_callable[int]"
        )

    def test_cross_family_fn_callable_to_behavior_rejected(self):
        """跨家族父→子：fn_callable[int] → behavior[int] 拒绝（非子类型方向）。"""
        reg = make_registry()
        src = self._specialize(reg, "fn_callable", "int")
        tgt = self._specialize(reg, "behavior", "int")
        assert not reg.is_assignable(src, tgt)

    def test_dict_covariant_value_any_allowed(self):
        """dict[str,int] → dict[str]（= dict[str,any]）value 动态协变放行。"""
        reg = make_registry()
        src = self._specialize(reg, "dict", "str", "int")
        tgt = self._specialize(reg, "dict", "str")
        assert reg.is_assignable(src, tgt), (
            "dict[str,int] should be assignable to dict[str,any]"
        )

    def test_compile_thread_mismatch_rejected(self):
        """语言层判别：thread[int] 赋给 thread[str] 编译期报 SEM_TYPE_MISMATCH。"""
        expect_compile_error(
            "func compute() -> int:\n"
            "    return 42\n"
            "thread[int] t = thread(callable=compute, args=[])\n"
            "thread[str] t2 = t\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_compile_list_param_mismatch_rejected(self):
        """语言层判别：list[str] 传 list[int] 参数编译期报 SEM_TYPE_MISMATCH。"""
        expect_compile_error(
            "func consume(list[int] items) -> void:\n"
            "    return\n"
            "list[str] strs = [\"a\"]\n"
            "consume(strs)\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_compile_same_family_same_args_ok(self):
        """同家族同实参编译通过（非误报）。"""
        _, diagnostics = _compile_code(
            "func compute() -> int:\n"
            "    return 42\n"
            "thread[int] t = thread(callable=compute, args=[])\n"
            "thread[int] t2 = t\n"
        )
        errors = _sem_errors(diagnostics)
        assert len(errors) == 0, f"Unexpected errors: {errors}"


# ===========================================================================
# dict[K,V].get() return-type specialization
# ===========================================================================

class TestDictGet:
    def test_get_return_type_is_value_type(self):
        """dict[str,int].get() method spec should return 'int', not 'any'."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        assert isinstance(dict_si, TypeDef)

        get_spec = reg.resolve_member(dict_si, "get")
        assert get_spec is not None
        assert get_spec.return_type.head == "int", (
            f"Expected 'int', got '{get_spec.return_type.head}'"
        )

    def test_get_return_type_for_str_value(self):
        """dict[int,str].get() should return 'str'."""
        reg = make_registry()
        dict_is = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("int"), reg.resolve("str")]
        )
        get_spec = reg.resolve_member(dict_is, "get")
        assert get_spec is not None
        assert get_spec.return_type.head == "str"

    def test_unspecialized_dict_get_stays_any(self):
        """Plain dict.get() keeps 'any' return type."""
        reg = make_registry()
        dict_spec = reg.resolve("dict")
        get_spec = reg.resolve_member(dict_spec, "get")
        assert get_spec is not None
        assert get_spec.return_type.head == "any"

    def test_dict_subscript_returns_value_type(self):
        """dict[str,int] subscript returns int at compile time."""
        _, diagnostics = _compile_code(
            'dict[str,int] scores = {"a": 1}\n'
            "int v = scores[\"a\"]\n"
        )
        errors = _sem_errors(diagnostics)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_dict_subscript_key_type_mismatch_rejected(self):
        """dict[str,int] 用 int 键下标 → SEM_TYPE_MISMATCH（PT-DEBT-33 10.1 闭合）。

        修复前键类型不校验，静默返回 value 类型；静态错位编译期拦截。
        """
        expect_compile_error(
            'dict[str,int] scores = {"a": 1}\n'
            "int v = scores[42]\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_dict_subscript_matching_key_type_passes(self):
        """键类型匹配的下标通过：dict[str,int] 用 str 键 / dict[int,str] 用 int 键。"""
        _compile_code(
            'dict[str,int] s = {"a": 1}\n'
            'int v = s["a"]\n'
            'dict[int,str] d = {1: "x"}\n'
            'str w = d[1]\n'
        )

    def test_dict_subscript_dynamic_key_passes(self):
        """dict[str,int] 用动态（any）键下标放行（运行期裁决）。"""
        _compile_code(
            'dict[str,int] s = {"a": 1}\n'
            'any k = "a"\n'
            "int v = s[k]\n"
        )


# ===========================================================================
# dict[K,V].values() and .keys() return specialization
# ===========================================================================

class TestDictValuesKeys:
    def test_values_return_type_is_list_of_value_type(self):
        """dict[str,int].values() should return 'list[int]', not bare 'list'."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        values_spec = reg.resolve_member(dict_si, "values")
        assert values_spec is not None
        rt = values_spec.return_type
        assert rt.head == "list" and rt.args and rt.args[0].head == "int", (
            f"Expected structured list[int], got '{rt}'"
        )

    def test_keys_return_type_is_list_of_key_type(self):
        """dict[str,int].keys() should return 'list[str]', not bare 'list'."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        keys_spec = reg.resolve_member(dict_si, "keys")
        assert keys_spec is not None
        rt = keys_spec.return_type
        assert rt.head == "list" and rt.args and rt.args[0].head == "str", (
            f"Expected structured list[str], got '{rt}'"
        )

    def test_unspecialized_dict_values_stays_list(self):
        """Plain dict.values() keeps bare 'list' return type."""
        reg = make_registry()
        dict_spec = reg.resolve("dict")
        values_spec = reg.resolve_member(dict_spec, "values")
        assert values_spec is not None
        assert values_spec.return_type.head == "list"

    def test_values_list_spec_is_registered(self):
        """After resolving dict[str,int].values(), the list[int] TypeRef resolves
        to a registered specialization (lazy build via resolve_typeref)."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        values_spec = reg.resolve_member(dict_si, "values")
        assert values_spec is not None
        resolved = reg.resolve_typeref(values_spec.return_type)
        assert resolved is not None and resolved.name == "list[int]", (
            "list[int] should resolve after values() resolution"
        )

    def test_keys_list_spec_is_registered(self):
        """After resolving dict[str,int].keys(), the list[str] TypeRef resolves
        to a registered specialization (lazy build via resolve_typeref)."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        keys_spec = reg.resolve_member(dict_si, "keys")
        assert keys_spec is not None
        resolved = reg.resolve_typeref(keys_spec.return_type)
        assert resolved is not None and resolved.name == "list[str]", (
            "list[str] should resolve after keys() resolution"
        )


# ===========================================================================
# Covariance — list[T] assignable to list
# ===========================================================================

class TestCovariance:
    def test_list_int_assignable_to_bare_list(self):
        """list[int] should be assignable to list (covariance via axiom)."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        list_bare = reg.resolve("list")
        assert reg.is_assignable(list_int, list_bare), "list[int] should be assignable to list"

    def test_list_int_not_assignable_to_str(self):
        """list[int] should NOT be assignable to str."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        str_spec = reg.resolve("str")
        assert not reg.is_assignable(list_int, str_spec)

    def test_compile_list_typed_to_bare_list_no_error(self):
        """Assigning list[int] to a bare list variable should compile without SEM_TYPE_MISMATCH."""
        _, diagnostics = _compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "list bare = nums\n"
        )
        errors = [d for d in diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_TYPE_MISMATCH"]
        assert len(errors) == 0, f"Unexpected SEM_TYPE_MISMATCH: {errors}"


class TestGenericAnnotationDeclaredType:
    """泛型注解符号声明保留泛型身份（运行时内省/序列化不退化）。

    symbol_collection 处理全部泛型注解（含 list[int] 等），不退化为基础类型；
    serializer 持久化 list/dict/tuple 泛型实参，rehydrator 还原完整泛型身份——
    运行时符号 declared_type 保留泛型参数。
    """

    def test_generic_annotations_preserve_type_args(self, engine):
        engine.run_string(
            "list[int] xs = [1, 2]\n"
            'dict[str, int] d = {"a": 1}\n'
            "Optional[int] o = 5\n"
            "tuple[int] tu = (1,)\n",
            silent=True,
        )
        rc = engine.interpreter.execution_context.runtime_context
        expect = {
            "xs": "list[int]",
            "d": "dict[str,int]",
            "o": "Optional[int]",
            "tu": "tuple[int]",
        }
        for name, want in expect.items():
            sp = rc.get_symbol(name).declared_type
            assert sp.name == want, f"{name}: 期望 {want!r}，got {sp.name!r}（泛型身份回归）"

    def test_multi_type_list_removed(self, engine):
        """多类型 list（list[int,str]）不支持——必须显式 list[any]。

        无 union 类型机制，多元素 list 的"元素读取返回 any"实为隐式异构，
        击穿元素类型设计。异构容器须显式声明 list[any]。
        """
        expect_compile_error(
            "list[int,str] mixed = [1, \"a\"]\n",
            "SEM_MULTI_TYPE_LIST_REMOVED",
        )
        # list[any] 显式异构仍可用；list[any] 折叠为裸 list（元素类型默认为 any）
        engine.run_string("list[any] mixed = [1, \"a\"]\n", silent=True)
        rc = engine.interpreter.execution_context.runtime_context
        sp = rc.get_symbol("mixed").declared_type
        assert sp.name == "list"

    def test_positional_tuple_preserves_elements(self, engine):
        """tuple[int,str] 位置元素类型经 artifact 序列化→还原不退化。

        serializer 持久化 positional_element_types_names/modules（payload
        字段名即序列化键，S4 声明驱动；位置顺序与元素类型模块均保真，
        与 dict key/value 双字段对齐）。
        """
        from core.compiler.serialization.serializer import FlatSerializer
        from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
        from core.kernel.factory import create_default_registry

        artifact = engine.compile_string('tuple[int,str] t = (1, "a")\n')
        d = FlatSerializer().serialize_artifact(artifact)
        types = d["modules"][artifact.entry_module]["pools"]["types"]
        target = next(k for k, v in types.items() if v.get("name") == "tuple[int,str]")
        assert types[target]["positional_element_types_names"] == ["int", "str"]
        reg = create_default_registry()
        reh = ArtifactRehydrator(type_pool=types, registry=reg)
        restored = reh.hydrate(target)
        assert restored.name == "tuple[int,str]"
        assert [t.head for t in restored.positional_element_types] == ["int", "str"]

    def test_chan_slot_annotation_preserves_type_args(self, engine):
        """chan[T]/slot[T] 注解纳入统一泛型模型，泛型身份保真。

        chan/slot 与统一 GenericTypeDeclaration 模型一致：注解实参持久化
        （符号保留 chan[T]/slot[T] 泛型身份），value_type 由
        ChannelAxiom/SlotAxiom 承载——符号与公理声称保持一致。
        """
        engine.run_string(
            'chan[str] c = chan(str, "stream")\n'
            'slot[int] s = slot("score", 0)\n',
            silent=True,
        )
        rc = engine.interpreter.execution_context.runtime_context
        expect = {"c": "chan[str]", "s": "slot[int]"}
        for name, want in expect.items():
            sp = rc.get_symbol(name).declared_type
            assert sp.name == want, f"{name}: 期望 {want!r}，got {sp.name!r}（chan/slot 泛型身份回归）"

        # artifact 序列化 → rehydrator 还原闭环（chan/slot 身份保真）
        from core.compiler.serialization.serializer import FlatSerializer
        from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
        from core.kernel.factory import create_default_registry

        artifact = engine.compile_string(
            'chan[str] c = chan(str, "stream")\nslot[int] s = slot("score", 0)\n'
        )
        d = FlatSerializer().serialize_artifact(artifact)
        types = d["modules"][artifact.entry_module]["pools"]["types"]
        for name, want in (("chan[str]", "str"), ("slot[int]", "int")):
            target = next(k for k, v in types.items() if v.get("name") == name)
            assert types[target]["value_type_name"] == want
            reg = create_default_registry()
            reh = ArtifactRehydrator(type_pool=types, registry=reg)
            restored = reh.hydrate(target)
            assert restored.name == name
            assert restored.value_type.head == want


class TestNestedGenericStructurePreserved:
    """创建点结构化 TypeRef：嵌套泛型实参不扁平化。

    `resolve_specialization` 用 `a.name` 字符串喂 factory、`TypeRef.of`
    把 `"list[int]"` 塞进 head（args 空）会使 substitute 无法穿透嵌套、
    错误实参静默放行。实参结构化后编译期可精确拦截嵌套泛型不匹配。
    """

    def test_nested_spec_element_type_is_structured(self):
        """list[list[int]] 的 element_type 是结构化 TypeRef（非扁平）。"""
        from core.kernel.spec.type_ref import TypeRef

        reg = make_registry()
        base = reg.resolve("list")
        inner = reg.resolve_specialization(base, [reg.resolve("int")])
        outer = reg.resolve_specialization(base, [inner])
        assert outer.element_type == TypeRef.parse("list[int]"), (
            f"嵌套实参应结构化保真，got {outer.element_type!r}"
        )

    def test_nested_substitute_penetrates(self):
        """嵌套泛型经 TypeRef.substitute 可替换内层形参。"""
        from core.kernel.spec.type_ref import TypeRef

        ref = TypeRef.generic("list", TypeRef.generic("list", TypeRef.of("T")))
        after = ref.substitute({"T": TypeRef.of("int")})
        assert after == TypeRef.parse("list[list[int]]"), (
            f"嵌套 substitute 应穿透，got {after!r}"
        )

    def test_user_generic_nested_param_rejected(self, engine):
        """Box[int].make(list[list[str]]) 编译期拦截（descriptor 结构保真后）。"""
        code = (
            "class Box[T]:\n"
            "    func make(self, list[list[T]] grid) -> list[list[T]]:\n"
            "        return grid\n"
            "\n"
            "Box[int] b = Box[int]()\n"
            'list[list[str]] g = [["a"], ["b"]]\n'
            "list[list[int]] r = b.make(g)\n"
        )
        expect_compile_error(code, "SEM_TYPE_MISMATCH")

    def test_nested_spec_serialization_roundtrip(self, engine):
        """嵌套泛型 spec 序列化→还原 element_type 结构保真（canonical_name 持久化）。"""
        from core.compiler.serialization.serializer import FlatSerializer
        from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
        from core.kernel.spec.type_ref import TypeRef

        artifact = engine.compile_string("list[list[int]] m = [[1],[2]]\n")
        d = FlatSerializer().serialize_artifact(artifact)
        types = d["modules"][artifact.entry_module]["pools"]["types"]
        target = next(k for k, v in types.items() if v.get("name") == "list[list[int]]")
        assert types[target]["element_type_name"] == "list[int]", (
            f"序列化 element_type_name 应含嵌套实参，got {types[target]['element_type_name']}"
        )
        reg = create_default_registry()
        reh = ArtifactRehydrator(type_pool=types, registry=reg)
        restored = reh.hydrate(target)
        assert restored.element_type == TypeRef.parse("list[int]"), (
            f"还原 element_type 应结构化，got {restored.element_type!r}"
        )


class TestCallableSigParamTypesStructured:
    """CALLABLE_SIG 参数在 symbol_collection 结构化（descriptor 单一语义源）。

    `_annotation_to_typeref` 对 `fn[(int)->int]` 产出结构化
    `TypeRef('fn', (TypeRef('__args__',(int,)), int))`，与 type-check 阶段
    `_param_type_ref` 的 CALLABLE_SIG 分支同构——param_types 与
    param_descriptors 单一语义源（无双构造源分裂）。
    """

    def test_callable_sig_param_type_structured(self, engine):
        """fn[(int)->int] 参数的 param_types 结构化（不再退化 any）。"""
        from core.kernel.spec.type_ref import TypeRef

        engine.compile_string(
            "func apply(fn[(int) -> int] f, int x) -> int:\n"
            "    return f(x)\n",
            silent=True,
        )
        reg = engine.registry.get_metadata_registry()
        sp = reg.resolve("apply")
        assert sp is not None
        assert sp.param_types[0] == TypeRef(
            "fn", (TypeRef("__args__", (TypeRef("int"),)), TypeRef("int"))
        ), f"CALLABLE_SIG param_types 应结构化，got {sp.param_types[0]!r}"

    def test_nested_generic_member_descriptor_consistent(self, engine):
        """Box[int].make 的 param_types 与 param_descriptors 结构一致（S2）。

        [S2 类身份统一] 入口模块用户类已 module 化，特化 spec 键为 qualified
        （__string_exec__.Box[int]），resolve 按入口模块限定。
        """
        engine.compile_string(
            "class Box[T]:\n"
            "    func make(self, list[list[T]] grid) -> list[list[T]]:\n"
            "        return grid\n"
            "\n"
            "Box[int] b = Box[int]()\n",
            silent=True,
        )
        reg = engine.registry.get_metadata_registry()
        box_int = reg.resolve("Box[int]", "__string_exec__")
        assert box_int is not None
        m = box_int.members.get("make")
        assert m is not None
        assert m.param_types[0] == m.param_descriptors[0].type_ref, (
            "param_types 与 param_descriptors 应一致（同一签名单一真相），"
            f"got {m.param_types[0]!r} vs {m.param_descriptors[0].type_ref!r}"
        )


class TestTupleUnpackTypeChecking:
    """元组解包按位置类型检查。

    IbTuple 解包各元素用 _any_desc 跳过 is_assignable 会使错误类型静默流入；
    RHS 元组字面量元素类型经 is_assignable 校验。
    """

    def test_tuple_unpack_wrong_type_rejected(self):
        """list[int] a, list[str] b = [\"x\"], [1] 编译期拦截。"""
        expect_compile_error(
            'list[int] a, list[str] b = ["x"], [1]\n',
            "SEM_TYPE_MISMATCH",
        )

    def test_tuple_unpack_correct_type_passes(self):
        """list[int] a, list[str] b = [1], [\"x\"] 编译通过。"""
        _compile_code('list[int] a, list[str] b = [1], ["x"]\n')

    def test_auto_container_infers_type_args(self, engine):
        """auto x = [1,2] 推断 list[int]（容器字面量带实参推断，S6）。"""
        engine.run_string("auto x = [1, 2]\n", silent=True)
        rc = engine.interpreter.execution_context.runtime_context
        sp = rc.get_symbol("x").declared_type
        assert sp.name == "list[int]", (
            f"auto 容器应推断带实参，got {sp.name}"
        )

    def test_tuple_unpack_bare_declaration_stays_bare(self, engine):
        """tuple 解包显式裸声明值层保持裸。

        `list a, list b = [1,2],["x"]` 的 RHS 推断 list[int] 覆盖声明时
        type(a)=list[int]；声明类型最后生效时 type(a)=list。
        """
        engine.run_string(
            'list a, list b = [1, 2], ["x"]\n',
            silent=True,
        )
        rc = engine.interpreter.execution_context.runtime_context
        a = rc.get_symbol("a").value
        assert a.ib_class.name == "list", (
            f"裸声明解包应保持裸 list，got {a.ib_class.name}"
        )


class TestStarredElementTypeChecking:
    """*expr 展开实参元素级类型校验。

    `*lst` 只用于跳过必填检查、元素类型不校验时 `list[str] *-> f(int)` 编译期
    放行；特化容器的元素类型与首位置形参做可赋值校验。
    """

    def test_starred_wrong_element_type_rejected(self):
        """list[str] 展开传给 f(int) 编译期拦截。"""
        expect_compile_error(
            "func f(int a, int b) -> int:\n"
            "    return a + b\n"
            'list[str] l = ["x", "y"]\n'
            "int r = f(*l)\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_starred_correct_element_type_passes(self):
        """list[int] 展开传给 f(int) 编译通过。"""
        _compile_code(
            "func f(int a, int b) -> int:\n"
            "    return a + b\n"
            "list[int] l = [1, 2]\n"
            "int r = f(*l)\n"
        )

    def test_starred_bare_container_skips(self):
        """裸 list（元素类型不可确定）展开跳过校验。"""
        _compile_code(
            "func f(int a, int b) -> int:\n"
            "    return a + b\n"
            "list l = [1, 2]\n"
            "int r = f(*l)\n"
        )

    def test_starred_mid_element_type_rejected(self):
        """中置星 f(10, *l, 30)：元素映射其**前**位置形参（b:int）——list[str] 拦截。

        修复前偏移按全部显式位置实参计数（错误映射到 c），错放；PT-DEBT-33 10.3
        闭合后按星前实参数映射。
        """
        expect_compile_error(
            "func f(int a, int b, int c) -> int:\n"
            "    return a + b + c\n"
            'list[str] l = ["x"]\n'
            "int r = f(10, *l, 30)\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_starred_mid_correct_element_type_passes(self):
        """中置星：list[int] 元素映射 b:int，通过。"""
        _compile_code(
            "func f(int a, int b, int c) -> int:\n"
            "    return a + b + c\n"
            "list[int] l = [1]\n"
            "int r = f(10, *l, 30)\n"
        )

    def test_starred_leading_element_type_rejected(self):
        """前导星 f(*l, 30)：元素映射首位置形参（a:int）——list[str] 拦截。"""
        expect_compile_error(
            "func f(int a, int b) -> int:\n"
            "    return a + b\n"
            'list[str] l = ["x"]\n'
            "int r = f(*l, 30)\n",
            "SEM_TYPE_MISMATCH",
        )

    def test_starred_leading_correct_element_type_passes(self):
        """前导星：list[int] 元素映射 a:int，通过。"""
        _compile_code(
            "func f(int a, int b) -> int:\n"
            "    return a + b\n"
            "list[int] l = [1]\n"
            "int r = f(*l, 30)\n"
        )

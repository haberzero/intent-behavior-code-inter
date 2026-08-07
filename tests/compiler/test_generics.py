"""
tests/compiler/test_generics.py — 泛型编译期契约（compile-only）。

编译期语义：

* ``resolve_specialization`` 早缓存
* ``dict[K,V].get`` / ``.values`` / ``.keys`` 返回类型 specialization
* list[int] 协变
* 泛型注解符号声明保留泛型身份（运行时内省/序列化不退化）

运行时执行用例见 tests/e2e/test_generics_runtime.py（mixed-concerns 拆分）。
"""
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

    此前缺陷：symbol_collection 只处理 IbName 注解，list[int] 等退化为
    any/基础类型；serializer 未持久化 list/dict/tuple 泛型实参，rehydrator
    shell 硬编码基础 TypeDef——运行时符号 declared_type 丢泛型参数。
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
        """多类型 list（list[int,str]）已移除——必须显式 list[any]。

        无 union 类型机制，多元素 list 的"元素读取返回 any"实为隐式异构，
        击穿元素类型设计。异构容器改为显式声明 list[any]。
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

        此前 serializer 只存 positional_type_names（head），位置顺序保真但
        positional_type_modules 未持久化（与 dict key/value 双字段对齐）。
        """
        from core.compiler.serialization.serializer import FlatSerializer
        from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
        from core.kernel.factory import create_default_registry

        artifact = engine.compile_string('tuple[int,str] t = (1, "a")\n')
        d = FlatSerializer().serialize_artifact(artifact)
        types = d["modules"][artifact.entry_module]["pools"]["types"]
        target = next(k for k, v in types.items() if v.get("name") == "tuple[int,str]")
        assert types[target]["positional_type_names"] == ["int", "str"]
        reg = create_default_registry()
        reh = ArtifactRehydrator(type_pool=types, registry=reg)
        restored = reh.hydrate(target)
        assert restored.name == "tuple[int,str]"
        assert [t.head for t in restored.positional_element_types] == ["int", "str"]

    def test_chan_slot_annotation_preserves_type_args(self, engine):
        """chan[T]/slot[T] 注解纳入统一泛型模型，泛型身份保真。

        此前 chan/slot 不在 GenericTypeDeclaration，注解实参丢弃（符号退化
        为裸 chan/slot），与 ChannelAxiom/SlotAxiom docstring 声称的
        "value_type 承载"矛盾——属半接通，根本修复。
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

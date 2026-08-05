"""
tests/compiler/test_generics.py
================================

泛型类型综合测试：

* ``resolve_specialization`` 早缓存
* ``list[T]`` 写方法参数类型 specialization + note 级 warning
* ``list[T].__getitem__(int)`` / ``dict[K,V].get`` / ``.values`` / ``.keys`` 返回类型
  specialization；list[int] 协变；嵌套泛型
"""
import pytest

from core.engine import IBCIEngine
from tests.conftest import run_ibci
from core.kernel.factory import create_default_registry
from core.kernel.spec import (    SpecRegistry,
    TypeDef,
    INT_SPEC,
    STR_SPEC,
)


# ---------------------------------------------------------------------------
# 共享 helper（风格：compile_code 返回 errors 集合）
# ---------------------------------------------------------------------------

def make_spec_registry() -> SpecRegistry:
    """Create a fully initialized SpecRegistry with all built-in axioms registered."""
    return create_default_registry()


def make_registry():
    return create_default_registry()


def _compile_code(code: str):
    """Compile only; return (artifact_or_None, issue_tracker).

    Unified signature shared by both test classes - matches
    the historical helpers in both original files.
    """
    from core.kernel.issue import CompilerError
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    try:
        artifact = engine.compile_string(code, silent=True)
    except CompilerError:
        artifact = None
    return artifact, engine.scheduler.issue_tracker


# ---------------------------------------------------------------------------
# specific helper（aliases for backward-compatible naming inside g3 body）
# ---------------------------------------------------------------------------

def _g3_compile_code(code: str):
    return _compile_code(code)


def _g3_run_code(code: str):
    return run_ibci(code, root_dir=".")


def _g3_sem_errors(issue_tracker):
    return [d for d in issue_tracker.diagnostics if d.severity.name == "ERROR"]


################################################################################
# MERGED: generics - early cache + write-method specialization
################################################################################

class TestG1SpecializationCache:
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
# list[T] write method parameter specialization
# ===========================================================================

class TestG2ListWriteMethodSpecialization:
    def test_append_param_specialized_to_element_type(self):
        """list[int].append should have param type 'int', not 'any'."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert isinstance(list_spec, TypeDef)

        append_spec = reg.resolve_member(list_spec, "append")
        assert append_spec is not None
        assert [t.head for t in append_spec.param_types] == ["int"], (
            f"Expected ['int'], got {[t.head for t in append_spec.param_types]}"
        )

    def test_insert_last_param_specialized(self):
        """list[str].insert should have param types ['int', 'str']."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("str")])
        insert_spec = reg.resolve_member(list_spec, "insert")
        assert insert_spec is not None
        assert [t.head for t in insert_spec.param_types][-1] == "str", (
            f"Expected last param 'str', got {[t.head for t in insert_spec.param_types]}"
        )

    def test_setitem_last_param_specialized(self):
        """list[float].__setitem__ should have value param 'float'."""
        reg = make_spec_registry()
        float_spec = reg.resolve("float")
        list_spec = reg.resolve_specialization(reg.resolve("list"), [float_spec])
        setitem_spec = reg.resolve_member(list_spec, "__setitem__")
        assert setitem_spec is not None
        assert [t.head for t in setitem_spec.param_types][-1] == "float"

    def test_pop_return_type_still_specialized(self):
        """does not regress pop return type specialization."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        pop_spec = reg.resolve_member(list_spec, "pop")
        assert pop_spec is not None
        assert pop_spec.return_type.head == "int"

    def test_unspecialized_list_append_stays_any(self):
        """Plain list (element_type=any) append keeps 'any' param."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        append_spec = reg.resolve_member(list_spec, "append")
        assert append_spec is not None
        assert "any" in [t.head for t in append_spec.param_types]

    def test_correct_type_append_no_warning(self):
        """list[int].append(42) compiles cleanly without warnings."""
        _, issue_tracker = _compile_code(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
        )
        warnings = [d for d in issue_tracker.diagnostics if d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"

    def test_wrong_type_append_produces_warning_not_error(self):
        """list[int].append('x') produces a SEM_CONTAINER_METHOD_HINT warning, not a compile error."""
        artifact, issue_tracker = _compile_code(
            "list[int] nums = []\n"
            "nums.append(\"hello\")\n"
        )
        # Compilation should succeed (no hard errors about this mismatch)
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(errors) == 0, f"mismatch should be a warning, not an error: {errors}"
        # The warning should be present
        warnings = [d for d in issue_tracker.diagnostics if d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(warnings) > 0, "Expected a SEM_CONTAINER_METHOD_HINT warning for int-list append with str"

    def test_correct_append_runs_and_produces_output(self):
        """list[int] append with correct type runs correctly end-to-end."""
        lines = _g3_run_code(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
            "print(nums)\n"
        )
        assert len(lines) > 0


################################################################################
# MERGED: generics - getitem/get/values/keys/covariance/nested
################################################################################

# ===========================================================================

class TestG3ListGetitem:
    def test_getitem_return_type_is_element_type(self):
        """list[int].__getitem__ method spec should return 'int', not 'any'."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert isinstance(list_int, TypeDef)

        getitem_spec = reg.resolve_member(list_int, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type.head == "int", (
            f"Expected 'int', got '{getitem_spec.return_type.head}'"
        )

    def test_getitem_return_type_for_str_list(self):
        """list[str].__getitem__ should return 'str'."""
        reg = make_registry()
        list_str = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("str")])
        getitem_spec = reg.resolve_member(list_str, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type.head == "str"

    def test_unspecialized_list_getitem_stays_any(self):
        """Plain list (element_type=any) __getitem__ keeps 'any' return."""
        reg = make_registry()
        list_spec = reg.resolve("list")
        getitem_spec = reg.resolve_member(list_spec, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type.head == "any"

    def test_subscript_operator_returns_element_type(self):
        """list[int] subscript via [] operator returns int at compile time (no SEM_TYPE_MISMATCH)."""
        _, issue_tracker = _g3_compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "int x = nums[0]\n"
        )
        errors = _g3_sem_errors(issue_tracker)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_subscript_operator_wrong_type_is_caught(self):
        """list[int] subscript result assigned to str should be SEM_TYPE_MISMATCH."""
        _, issue_tracker = _g3_compile_code(
            "list[int] nums = [10, 20]\n"
            "str s = nums[0]\n"
        )
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_TYPE_MISMATCH"]
        assert len(errors) > 0, "Expected SEM_TYPE_MISMATCH for int→str mismatch"

    def test_subscript_e2e_returns_correct_value(self):
        """list[int] subscript runs correctly and returns the element."""
        lines = _g3_run_code(
            "list[int] nums = [10, 20, 30]\n"
            "int x = nums[1]\n"
            "print(x)\n"
        )
        assert lines == ["20"], f"Expected ['20'], got {lines}"


# ===========================================================================
# dict[K,V].get() return-type specialization
# ===========================================================================

class TestG3DictGet:
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
        _, issue_tracker = _g3_compile_code(
            'dict[str,int] scores = {"a": 1}\n'
            "int v = scores[\"a\"]\n"
        )
        errors = _g3_sem_errors(issue_tracker)
        assert len(errors) == 0, f"Unexpected errors: {errors}"


# ===========================================================================
# dict[K,V].values() and .keys() return specialization
# ===========================================================================

class TestG3DictValuesKeys:
    def test_values_return_type_is_list_of_value_type(self):
        """dict[str,int].values() should return 'list[int]', not bare 'list'."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        values_spec = reg.resolve_member(dict_si, "values")
        assert values_spec is not None
        assert values_spec.return_type.head == "list[int]", (
            f"Expected 'list[int]', got '{values_spec.return_type.head}'"
        )

    def test_keys_return_type_is_list_of_key_type(self):
        """dict[str,int].keys() should return 'list[str]', not bare 'list'."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        keys_spec = reg.resolve_member(dict_si, "keys")
        assert keys_spec is not None
        assert keys_spec.return_type.head == "list[str]", (
            f"Expected 'list[str]', got '{keys_spec.return_type.head}'"
        )

    def test_unspecialized_dict_values_stays_list(self):
        """Plain dict.values() keeps bare 'list' return type."""
        reg = make_registry()
        dict_spec = reg.resolve("dict")
        values_spec = reg.resolve_member(dict_spec, "values")
        assert values_spec is not None
        assert values_spec.return_type.head == "list"

    def test_values_list_spec_is_registered(self):
        """After resolving dict[str,int].values(), list[int] should be in registry."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        reg.resolve_member(dict_si, "values")
        assert reg.resolve("list[int]") is not None, "list[int] should be registered after values() resolution"

    def test_keys_list_spec_is_registered(self):
        """After resolving dict[str,int].keys(), list[str] should be in registry."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        reg.resolve_member(dict_si, "keys")
        assert reg.resolve("list[str]") is not None, "list[str] should be registered after keys() resolution"


# ===========================================================================
# Covariance — list[T] assignable to list
# ===========================================================================

class TestG3Covariance:
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
        _, issue_tracker = _g3_compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "list bare = nums\n"
        )
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_TYPE_MISMATCH"]
        assert len(errors) == 0, f"Unexpected SEM_TYPE_MISMATCH: {errors}"


# ===========================================================================
# Nested generic subscript — list[list[int]][0] → list[int]
# ===========================================================================

class TestG3NestedGenerics:
    def test_nested_list_subscript_returns_inner_list_spec(self):
        """list[list[int]] subscript by int returns list[int] spec."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        list_list_int = reg.resolve_specialization(reg.resolve("list"), [list_int])
        assert isinstance(list_list_int, TypeDef)
        assert list_list_int.element_type.head == "list[int]"

        result = reg.resolve_subscript(list_list_int, reg.resolve("int"))
        assert result is not None
        assert result.name == "list[int]", f"Expected 'list[int]', got '{result.name}'"

    def test_nested_list_compile_no_error(self):
        """list[list[int]] declaration and double-subscript compiles without errors."""
        _, issue_tracker = _g3_compile_code(
            "list[list[int]] nested = [[1, 2], [3, 4]]\n"
            "list[int] row = nested[0]\n"
            "int val = row[0]\n"
        )
        errors = _g3_sem_errors(issue_tracker)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_nested_list_e2e(self):
        """list[list[int]] access works end-to-end."""
        lines = _g3_run_code(
            "list[list[int]] nested = [[10, 20], [30, 40]]\n"
            "list[int] row = nested[1]\n"
            "int val = row[0]\n"
            "print(val)\n"
        )
        assert lines == ["30"], f"Expected ['30'], got {lines}"


class TestGenericAnnotationDeclaredType:
    """L7-A：泛型注解符号声明保留泛型身份（运行时内省/序列化不退化）。

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
        rc = engine.interpreter._execution_context.runtime_context
        expect = {
            "xs": "list[int]",
            "d": "dict[str,int]",
            "o": "Optional[int]",
            "tu": "tuple[int]",
        }
        for name, want in expect.items():
            sp = rc.get_symbol(name).declared_type
            assert sp.name == want, f"{name}: 期望 {want!r}，got {sp.name!r}（L7-A 回归）"

    def test_multi_type_list_preserves_allowed_types(self, engine):
        """L7-A/C1：multi-type list（list[int,str]）泛型身份经 artifact 序列化→还原不退化。

        此前 serializer 只持久化 element_type_name（multi-type 下为 "any"），
        allowed_element_types 丢失，还原后退化为裸 list（C1 根本修复）。
        """
        from core.compiler.serialization.serializer import FlatSerializer
        from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
        from core.kernel.factory import create_default_registry

        engine.run_string("list[int,str] mixed = [1, \"a\"]\n", silent=True)
        rc = engine.interpreter._execution_context.runtime_context
        sp = rc.get_symbol("mixed").declared_type
        assert sp.name == "list[int,str]"
        assert [t.head for t in sp.allowed_element_types] == ["int", "str"]

        # artifact 序列化 → rehydrator 还原闭环（multi-type 身份保真）
        artifact = engine.compile_string("list[int,str] mixed = [1, \"a\"]\n")
        d = FlatSerializer().serialize_artifact(artifact)
        types = d["modules"][artifact.entry_module]["pools"]["types"]
        target = next(k for k, v in types.items() if v.get("name") == "list[int,str]")
        assert types[target]["allowed_element_type_names"] == ["int", "str"]
        reg = create_default_registry()
        reh = ArtifactRehydrator(type_pool=types, registry=reg)
        restored = reh.hydrate(target)
        assert restored.name == "list[int,str]"
        assert [t.head for t in restored.allowed_element_types] == ["int", "str"]

    def test_positional_tuple_preserves_elements(self, engine):
        """L7-A/C1：tuple[int,str] 位置元素类型经 artifact 序列化→还原不退化。

        此前 serializer 只存 positional_type_names（head），位置顺序保真但
        positional_type_modules 未持久化（C1 根本修复，与 dict key/value 双字段对齐）。
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
        """R1-D1：chan[T]/slot[T] 注解纳入统一泛型模型，泛型身份保真。

        此前 chan/slot 不在 GenericTypeDeclaration，注解实参丢弃（符号退化
        为裸 chan/slot），与 ChannelAxiom/SlotAxiom docstring 声称的
        "value_type 承载"矛盾——属半接通，根本修复。
        """
        engine.run_string(
            'chan[str] c = chan(str, "stream")\n'
            'slot[int] s = slot("score", 0)\n',
            silent=True,
        )
        rc = engine.interpreter._execution_context.runtime_context
        expect = {"c": "chan[str]", "s": "slot[int]"}
        for name, want in expect.items():
            sp = rc.get_symbol(name).declared_type
            assert sp.name == want, f"{name}: 期望 {want!r}，got {sp.name!r}（R1-D1 回归）"

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

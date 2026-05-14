"""
tests/compiler/test_generics.py
================================

泛型类型综合测试（合并自 2 个历史文件）：

* G1: ``resolve_specialization`` 早缓存
* G2: ``list[T]`` 写方法参数类型 specialization + note 级 warning
  （原 ``test_g1_g2_generics.py``）
* G3: ``list[T].__getitem__(int)`` / ``dict[K,V].get`` / ``.values`` / ``.keys`` 返回类型
  specialization；list[int] 协变；嵌套泛型
  （原 ``test_g3_generics.py``）

详见 docs/TESTS_REORGANIZATION_TASK.md Step 9。
"""
import pytest

from core.engine import IBCIEngine
from tests.conftest import run_ibci
from core.kernel.factory import create_default_registry
from core.kernel.spec import (
    SpecRegistry,
    TypeDef,
    INT_SPEC,
    STR_SPEC,
)


# ---------------------------------------------------------------------------
# 共享 helper（G1/G2 风格：compile_code 返回 errors 集合）
# ---------------------------------------------------------------------------

def make_spec_registry() -> SpecRegistry:
    """Create a fully initialized SpecRegistry with all built-in axioms registered."""
    return create_default_registry()


def make_registry():
    return create_default_registry()


def _compile_code(code: str):
    """Compile only; return (artifact_or_None, issue_tracker).

    Unified signature shared by both G1/G2 and G3 test classes — matches
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
# G3-specific helper（aliases for backward-compatible naming inside g3 body）
# ---------------------------------------------------------------------------

def _g3_compile_code(code: str):
    return _compile_code(code)


def _g3_run_code(code: str):
    return run_ibci(code, root_dir=".")


def _g3_sem_errors(issue_tracker):
    return [d for d in issue_tracker.diagnostics if d.severity.name == "ERROR"]


################################################################################
# MERGED: G1/G2 generics — early cache + write-method specialization
# Source: tests/compiler/test_g1_g2_generics.py
################################################################################

class TestG1SpecializationCache:
    def test_second_call_returns_same_object(self):
        """resolve_specialization hit → returns same registered spec on second call."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        int_spec = reg.resolve("int")

        first = reg.resolve_specialization(list_spec, [int_spec])
        second = reg.resolve_specialization(list_spec, [int_spec])
        assert first is second, "G1: second specialization call should return cached object"

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
# G2: list[T] write method parameter specialization
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
        """G2 does not regress G1-era pop return type specialization."""
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
        warnings = [d for d in issue_tracker.diagnostics if d.code == "SEM_081"]
        assert len(warnings) == 0, f"Unexpected G2 warnings: {warnings}"

    def test_wrong_type_append_produces_warning_not_error(self):
        """list[int].append('x') produces a SEM_081 warning, not a compile error."""
        artifact, issue_tracker = _compile_code(
            "list[int] nums = []\n"
            "nums.append(\"hello\")\n"
        )
        # Compilation should succeed (no hard errors about this mismatch)
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_081"]
        assert len(errors) == 0, f"G2 mismatch should be a warning, not an error: {errors}"
        # The warning should be present
        warnings = [d for d in issue_tracker.diagnostics if d.code == "SEM_081"]
        assert len(warnings) > 0, "Expected a SEM_081 warning for int-list append with str"

    def test_correct_append_runs_and_produces_output(self):
        """list[int] append with correct type runs correctly end-to-end."""
        lines = _g3_run_code(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
            "print(nums)\n"
        )
        assert len(lines) > 0


################################################################################
# MERGED: G3 generics — getitem/get/values/keys/covariance/nested
# Source: tests/compiler/test_g3_generics.py
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
        """list[int] subscript via [] operator returns int at compile time (no SEM_003)."""
        _, issue_tracker = _g3_compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "int x = nums[0]\n"
        )
        errors = _g3_sem_errors(issue_tracker)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_subscript_operator_wrong_type_is_caught(self):
        """list[int] subscript result assigned to str should be SEM_003."""
        _, issue_tracker = _g3_compile_code(
            "list[int] nums = [10, 20]\n"
            "str s = nums[0]\n"
        )
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_003"]
        assert len(errors) > 0, "Expected SEM_003 for int→str mismatch"

    def test_subscript_e2e_returns_correct_value(self):
        """list[int] subscript runs correctly and returns the element."""
        lines = _g3_run_code(
            "list[int] nums = [10, 20, 30]\n"
            "int x = nums[1]\n"
            "print(x)\n"
        )
        assert lines == ["20"], f"Expected ['20'], got {lines}"


# ===========================================================================
# G3: dict[K,V].get() return-type specialization
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
# G3: dict[K,V].values() and .keys() return specialization
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
# §3.5: Covariance — list[T] assignable to list
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
        """Assigning list[int] to a bare list variable should compile without SEM_003."""
        _, issue_tracker = _g3_compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "list bare = nums\n"
        )
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_003"]
        assert len(errors) == 0, f"Unexpected SEM_003: {errors}"


# ===========================================================================
# §3.6: Nested generic subscript — list[list[int]][0] → list[int]
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

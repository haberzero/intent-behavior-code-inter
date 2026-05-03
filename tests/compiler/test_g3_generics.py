"""
tests/compiler/test_g3_generics.py

G3: Generic type inference improvements — resolve_member return-type specialization

Covers:
  - list[T].__getitem__(int) → T  (was always "any" before G3)
  - dict[K,V].get(key) → V       (was always "any" before G3)
  - dict[K,V].values() → list[V] (was bare "list" before G3)
  - dict[K,V].keys()   → list[K] (was bare "list" before G3)
  - list[int][0] → int (subscript operator path, verified working since G1/G2)
  - dict[str,int]["key"] → int   (subscript operator path)
  - list[int] assignable to list  (covariance via ListAxiom.is_compatible)
  - Nested generic: list[list[int]][0] → list[int]
"""
import pytest
from core.engine import IBCIEngine
from core.kernel.factory import create_default_registry
from core.kernel.spec import ListSpec, DictSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_registry():
    return create_default_registry()


def compile_code(code: str):
    """Compile IBCI source and return (artifact, issue_tracker).

    If compilation raises CompilerError, returns (None, issue_tracker) so that
    callers can still inspect the diagnostics.
    """
    from core.kernel.issue import CompilerError
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    try:
        artifact = engine.compile_string(code, silent=True)
    except CompilerError:
        artifact = None
    return artifact, engine.scheduler.issue_tracker


def run_code(code: str):
    """Compile + run IBCI source; return captured output lines."""
    lines = []
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


def sem_errors(issue_tracker):
    return [d for d in issue_tracker.diagnostics if d.severity.name == "ERROR"]


# ===========================================================================
# G3: list[T].__getitem__ return-type specialization
# ===========================================================================

class TestG3ListGetitem:
    def test_getitem_return_type_is_element_type(self):
        """list[int].__getitem__ method spec should return 'int', not 'any'."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert isinstance(list_int, ListSpec)

        getitem_spec = reg.resolve_member(list_int, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type_name == "int", (
            f"Expected 'int', got '{getitem_spec.return_type_name}'"
        )

    def test_getitem_return_type_for_str_list(self):
        """list[str].__getitem__ should return 'str'."""
        reg = make_registry()
        list_str = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("str")])
        getitem_spec = reg.resolve_member(list_str, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type_name == "str"

    def test_unspecialized_list_getitem_stays_any(self):
        """Plain list (element_type=any) __getitem__ keeps 'any' return."""
        reg = make_registry()
        list_spec = reg.resolve("list")
        getitem_spec = reg.resolve_member(list_spec, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type_name == "any"

    def test_subscript_operator_returns_element_type(self):
        """list[int] subscript via [] operator returns int at compile time (no SEM_003)."""
        _, issue_tracker = compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "int x = nums[0]\n"
        )
        errors = sem_errors(issue_tracker)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_subscript_operator_wrong_type_is_caught(self):
        """list[int] subscript result assigned to str should be SEM_003."""
        _, issue_tracker = compile_code(
            "list[int] nums = [10, 20]\n"
            "str s = nums[0]\n"
        )
        errors = [d for d in issue_tracker.diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_003"]
        assert len(errors) > 0, "Expected SEM_003 for int→str mismatch"

    def test_subscript_e2e_returns_correct_value(self):
        """list[int] subscript runs correctly and returns the element."""
        lines = run_code(
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
        assert isinstance(dict_si, DictSpec)

        get_spec = reg.resolve_member(dict_si, "get")
        assert get_spec is not None
        assert get_spec.return_type_name == "int", (
            f"Expected 'int', got '{get_spec.return_type_name}'"
        )

    def test_get_return_type_for_str_value(self):
        """dict[int,str].get() should return 'str'."""
        reg = make_registry()
        dict_is = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("int"), reg.resolve("str")]
        )
        get_spec = reg.resolve_member(dict_is, "get")
        assert get_spec is not None
        assert get_spec.return_type_name == "str"

    def test_unspecialized_dict_get_stays_any(self):
        """Plain dict.get() keeps 'any' return type."""
        reg = make_registry()
        dict_spec = reg.resolve("dict")
        get_spec = reg.resolve_member(dict_spec, "get")
        assert get_spec is not None
        assert get_spec.return_type_name == "any"

    def test_dict_subscript_returns_value_type(self):
        """dict[str,int] subscript returns int at compile time."""
        _, issue_tracker = compile_code(
            'dict[str,int] scores = {"a": 1}\n'
            "int v = scores[\"a\"]\n"
        )
        errors = sem_errors(issue_tracker)
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
        assert values_spec.return_type_name == "list[int]", (
            f"Expected 'list[int]', got '{values_spec.return_type_name}'"
        )

    def test_keys_return_type_is_list_of_key_type(self):
        """dict[str,int].keys() should return 'list[str]', not bare 'list'."""
        reg = make_registry()
        dict_si = reg.resolve_specialization(
            reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")]
        )
        keys_spec = reg.resolve_member(dict_si, "keys")
        assert keys_spec is not None
        assert keys_spec.return_type_name == "list[str]", (
            f"Expected 'list[str]', got '{keys_spec.return_type_name}'"
        )

    def test_unspecialized_dict_values_stays_list(self):
        """Plain dict.values() keeps bare 'list' return type."""
        reg = make_registry()
        dict_spec = reg.resolve("dict")
        values_spec = reg.resolve_member(dict_spec, "values")
        assert values_spec is not None
        assert values_spec.return_type_name == "list"

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
        _, issue_tracker = compile_code(
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
        assert isinstance(list_list_int, ListSpec)
        assert list_list_int.element_type_name == "list[int]"

        result = reg.resolve_subscript(list_list_int, reg.resolve("int"))
        assert result is not None
        assert result.name == "list[int]", f"Expected 'list[int]', got '{result.name}'"

    def test_nested_list_compile_no_error(self):
        """list[list[int]] declaration and double-subscript compiles without errors."""
        _, issue_tracker = compile_code(
            "list[list[int]] nested = [[1, 2], [3, 4]]\n"
            "list[int] row = nested[0]\n"
            "int val = row[0]\n"
        )
        errors = sem_errors(issue_tracker)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_nested_list_e2e(self):
        """list[list[int]] access works end-to-end."""
        lines = run_code(
            "list[list[int]] nested = [[10, 20], [30, 40]]\n"
            "list[int] row = nested[1]\n"
            "int val = row[0]\n"
            "print(val)\n"
        )
        assert lines == ["30"], f"Expected ['30'], got {lines}"

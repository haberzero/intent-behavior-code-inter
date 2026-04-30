"""
tests/compiler/test_g1_g2_generics.py

G1: resolve_specialization early-cache lookup
G2: list[T] write-method parameter type specialization + note-level warning
"""
import pytest
from core.engine import IBCIEngine
from core.kernel.spec import (
    SpecRegistry,
    ListSpec,
    INT_SPEC, STR_SPEC,
)
from core.kernel.factory import create_default_registry


def make_spec_registry() -> SpecRegistry:
    """Create a fully initialized SpecRegistry with all built-in axioms registered."""
    return create_default_registry()


def run_code(code: str):
    """Compile + run IBCI code; return output lines."""
    lines = []
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


def compile_code(code: str):
    """Compile only; return (artifact, issue_tracker) tuple."""
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    artifact = engine.compile_string(code, silent=True)
    return artifact, engine.scheduler.issue_tracker


# ===========================================================================
# G1: resolve_specialization cache hit
# ===========================================================================

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
        assert isinstance(list_spec, ListSpec)

        append_spec = reg.resolve_member(list_spec, "append")
        assert append_spec is not None
        assert append_spec.param_type_names == ["int"], (
            f"Expected ['int'], got {append_spec.param_type_names}"
        )

    def test_insert_last_param_specialized(self):
        """list[str].insert should have param types ['int', 'str']."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("str")])
        insert_spec = reg.resolve_member(list_spec, "insert")
        assert insert_spec is not None
        assert insert_spec.param_type_names[-1] == "str", (
            f"Expected last param 'str', got {insert_spec.param_type_names}"
        )

    def test_setitem_last_param_specialized(self):
        """list[float].__setitem__ should have value param 'float'."""
        reg = make_spec_registry()
        float_spec = reg.resolve("float")
        list_spec = reg.resolve_specialization(reg.resolve("list"), [float_spec])
        setitem_spec = reg.resolve_member(list_spec, "__setitem__")
        assert setitem_spec is not None
        assert setitem_spec.param_type_names[-1] == "float"

    def test_pop_return_type_still_specialized(self):
        """G2 does not regress G1-era pop return type specialization."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        pop_spec = reg.resolve_member(list_spec, "pop")
        assert pop_spec is not None
        assert pop_spec.return_type_name == "int"

    def test_unspecialized_list_append_stays_any(self):
        """Plain list (element_type=any) append keeps 'any' param."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        append_spec = reg.resolve_member(list_spec, "append")
        assert append_spec is not None
        assert "any" in append_spec.param_type_names

    def test_correct_type_append_no_warning(self):
        """list[int].append(42) compiles cleanly without warnings."""
        _, issue_tracker = compile_code(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
        )
        warnings = [d for d in issue_tracker.diagnostics if d.code == "SEM_081"]
        assert len(warnings) == 0, f"Unexpected G2 warnings: {warnings}"

    def test_wrong_type_append_produces_warning_not_error(self):
        """list[int].append('x') produces a SEM_081 warning, not a compile error."""
        artifact, issue_tracker = compile_code(
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
        lines = run_code(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
            "print(nums)\n"
        )
        assert len(lines) > 0

"""
tests/e2e/test_generics_runtime.py — 泛型运行时黑盒回归。

自 tests/compiler/test_generics.py 拆分（mixed-concerns）：完整程序执行用例归
e2e/（含类内少量 compile-only 校验）；纯编译期契约归 tests/compiler/test_generics.py。
"""
from core.kernel.factory import create_default_registry
from core.kernel.issue import CompilerError
from core.kernel.spec import SpecRegistry, TypeDef
from tests.conftest import compile_ibci, run_ibci


# ---------------------------------------------------------------------------
# 共享 helper（黑盒；diag 为 diagnostics 列表）
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


# ===========================================================================
# list[T] write method parameter specialization
# ===========================================================================

class TestListWriteMethodSpecialization:
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

    def test_correct_type_append_no_warning(self, engine):
        """list[int].append(42) compiles cleanly without warnings."""
        engine.compile_string(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n",
            silent=True,
        )
        warnings = [d for d in engine.scheduler.issue_tracker.diagnostics
                    if d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"

    def test_wrong_type_append_produces_warning_not_error(self, engine):
        """list[int].append('x') produces a SEM_CONTAINER_METHOD_HINT warning, not a compile error."""
        engine.compile_string(
            "list[int] nums = []\n"
            "nums.append(\"hello\")\n",
            silent=True,
        )
        diagnostics = engine.scheduler.issue_tracker.diagnostics
        # Compilation should succeed (no hard errors about this mismatch)
        errors = [d for d in diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(errors) == 0, f"mismatch should be a warning, not an error: {errors}"
        # The warning should be present
        warnings = [d for d in diagnostics if d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(warnings) > 0, "Expected a SEM_CONTAINER_METHOD_HINT warning for int-list append with str"

    def test_correct_append_runs_and_produces_output(self):
        """list[int] append with correct type runs correctly end-to-end."""
        lines = run_ibci(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
            "print(nums)\n"
        )
        assert len(lines) > 0


# ===========================================================================
# list[T].__getitem__ / 下标运算
# ===========================================================================

class TestListGetitem:
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
        _, diagnostics = _compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "int x = nums[0]\n"
        )
        errors = _sem_errors(diagnostics)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_subscript_operator_wrong_type_is_caught(self):
        """list[int] subscript result assigned to str should be SEM_TYPE_MISMATCH."""
        _, diagnostics = _compile_code(
            "list[int] nums = [10, 20]\n"
            "str s = nums[0]\n"
        )
        errors = [d for d in diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_TYPE_MISMATCH"]
        assert len(errors) > 0, "Expected SEM_TYPE_MISMATCH for int→str mismatch"

    def test_subscript_e2e_returns_correct_value(self):
        """list[int] subscript runs correctly and returns the element."""
        lines = run_ibci(
            "list[int] nums = [10, 20, 30]\n"
            "int x = nums[1]\n"
            "print(x)\n"
        )
        assert lines == ["20"], f"Expected ['20'], got {lines}"


# ===========================================================================
# Nested generic subscript — list[list[int]][0] → list[int]
# ===========================================================================

class TestNestedGenerics:
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
        _, diagnostics = _compile_code(
            "list[list[int]] nested = [[1, 2], [3, 4]]\n"
            "list[int] row = nested[0]\n"
            "int val = row[0]\n"
        )
        errors = _sem_errors(diagnostics)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_nested_list_e2e(self):
        """list[list[int]] access works end-to-end."""
        lines = run_ibci(
            "list[list[int]] nested = [[10, 20], [30, 40]]\n"
            "list[int] row = nested[1]\n"
            "int val = row[0]\n"
            "print(val)\n"
        )
        assert lines == ["30"], f"Expected ['30'], got {lines}"

"""
tests/contracts/test_scope_semantics.py
========================================

Contract tests for IBCI scope and closure semantics.

Validates:
- INV-CELL-*: IbCell shared reference semantics
- INV-LAMBDA-*: Lambda reference capture behavior
- INV-SNAPSHOT-*: Snapshot value capture and deep clone guarantees
- INV-SCOPE-*: Lexical scoping rules
"""

import pytest
from tests.conftest import run_ibci, expect_runtime_error


# ===========================================================================
# Cell Shared Reference Semantics (INV-CELL-*)
# ===========================================================================


class TestCellSharedReferences:
    """Validate IbCell shared reference semantics.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §4 Scope Model
    - core/runtime/objects/cell.py
    """

    def test_cell_captures_reference(self):
        """INV-CELL-1: Cells capture references, not values."""
        code = """
int x = 10
func get_x() -> auto:
    return x

x = 20
print(get_x())
"""
        # Should print 20 (updated value), not 10 (capture time value)
        assert run_ibci(code) == ["20"]

    def test_multiple_closures_share_cell(self):
        """INV-CELL-2: Multiple closures sharing a variable see updates."""
        pytest.skip("PT-5.1: Multiple closures over the same outer variable do not currently share mutations across calls")


# ===========================================================================
# Lambda Reference Capture (INV-LAMBDA-*)
# ===========================================================================


class TestLambdaCapture:
    """Validate lambda reference capture behavior.

    References:
    - docs/COMPLETED.md §NS-3 Lambda/Snapshot Semantics
    - tests/e2e/test_e2e_higher_order.py (legacy)
    """

    def test_lambda_captures_by_reference(self):
        """INV-LAMBDA-1: Lambda captures variables by reference (shared Cell)."""
        code = """
int x = 5
fn[()->int] f = lambda: x
x = 10
print(f())
"""
        assert run_ibci(code) == ["10"]

    def test_lambda_in_loop_shares_variable(self):
        """INV-LAMBDA-2: Lambdas in loop share loop variable reference."""
        code = """
list[fn[()->int]] funcs = []
for int i in range(3):
    funcs.append(lambda: i)

# All lambdas share same 'i', which is now 2 (last value)
print(funcs[0]())
print(funcs[1]())
print(funcs[2]())
"""
        result = run_ibci(code)
        # All should print 2 (loop variable final value)
        assert result == ["2", "2", "2"]

    def test_lambda_modifies_captured_variable(self):
        """INV-LAMBDA-3: Lambda can modify captured variables."""
        pytest.skip("PT-5.1: Walrus operator (:=) and lambda body assignments not in IBCI syntax")


# ===========================================================================
# Snapshot Value Capture (INV-SNAPSHOT-*)
# ===========================================================================


class TestSnapshotSemantics:
    """Validate snapshot value capture and isolation.

    References:
    - docs/COMPLETED.md §2026-05-11 Snapshot Semantics
    - tests/e2e/test_e2e_snapshot_semantics.py (legacy)
    - core/runtime/objects/deep_clone.py
    """

    def test_snapshot_captures_value_not_reference(self):
        """INV-SNAPSHOT-1: Snapshot captures value at definition time."""
        code = """
int x = 5
fn[()->int] f = snapshot: x
x = 10
print(f())
"""
        # Should print 5 (captured value), not 10 (current value)
        assert run_ibci(code) == ["5"]

    def test_snapshot_deep_clones_mutable_objects(self):
        """INV-SNAPSHOT-2: Snapshot deep clones mutable objects."""
        code = """
list[int] nums = [1, 2]
fn[()->list[int]] get = snapshot: nums
nums.append(3)
print(get())
print(nums)
"""
        result = run_ibci(code)
        assert "[1, 2]" in result[0]  # Snapshot has original
        assert "3" in result[1]  # Original list modified

    def test_snapshot_each_call_independent(self):
        """INV-SNAPSHOT-3: Each snapshot call gets fresh isolated clone."""
        code = """
list[int] base = [1]
fn[()->list[int]] maker = snapshot: base

auto a = maker()
a.append(2)
auto b = maker()
b.append(3)

print(a)
print(b)
"""
        result = run_ibci(code)
        assert "2" in result[0] and "3" not in result[0]
        assert "3" in result[1] and "2" not in result[1]
        result = run_ibci(code)
        assert "2" in result[0] and "3" not in result[0]
        assert "3" in result[1] and "2" not in result[1]


# ===========================================================================
# Lexical Scoping Rules (INV-SCOPE-*)
# ===========================================================================


class TestLexicalScoping:
    """Validate lexical scoping rules.

    References:
    - IBCI_SYNTAX_REFERENCE.md §2.3 Scoping
    """

    def test_inner_scope_shadows_outer(self):
        """INV-SCOPE-1: Inner scope shadows outer scope variables."""
        pytest.skip("PT-5.1: SEM_002 forbids redeclaring same-name variable in if-block (no shadowing allowed)")

    def test_function_creates_new_scope(self):
        """INV-SCOPE-2: Function creates independent scope."""
        code = """
int x = 10
func test() -> auto:
    int x = 20
    return x

print(test())
print(x)
"""
        assert run_ibci(code) == ["20", "10"]

    def test_nested_function_accesses_parent_scope(self):
        """INV-SCOPE-3: Nested functions access parent scope."""
        code = """
func outer() -> auto:
    int x = 5
    func inner() -> auto:
        return x
    return inner()

print(outer())
"""
        assert run_ibci(code) == ["5"]

    def test_loop_variable_accessible_after_loop(self):
        """INV-SCOPE-4: Loop variables remain accessible after loop."""
        code = """
for int i in range(3):
    pass
print(i)
"""
        assert run_ibci(code) == ["2"]

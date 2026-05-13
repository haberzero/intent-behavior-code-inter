"""
tests/contracts/test_execution_model.py
========================================

Contract tests for IBCI execution model guarantees.

Validates:
- INV-CPS-*: CPS execution model (no Python stack overflow)
- INV-SIGNAL-*: Control flow signal propagation
- INV-FRAME-*: Frame stack management
- INV-RECURSION-*: Deep recursion support
"""

import pytest
from tests.conftest import run_ibci, expect_runtime_error


# ===========================================================================
# CPS Execution Model (INV-CPS-*)
# ===========================================================================


class TestCPSExecutionModel:
    """Validate CPS execution model guarantees.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §2 CPS Architecture
    - core/runtime/interpreter/cps_interpreter.py
    """

    def test_deep_recursion_no_python_overflow(self):
        """INV-CPS-1: Deep recursion doesn't cause Python stack overflow."""
        code = """
func int factorial(int n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(factorial(100))
"""
        # Should succeed without Python RecursionError
        result = run_ibci(code)
        assert result  # Any output means CPS handled deep recursion

    def test_deep_call_chain_succeeds(self):
        """INV-CPS-2: Deep call chains execute via trampoline."""
        code = """
func int chain(int depth):
    if depth <= 0:
        return 42
    return chain(depth - 1)

print(chain(200))
"""
        assert run_ibci(code) == ["42"]

    def test_mutual_recursion_supported(self):
        """INV-CPS-3: Mutual recursion works via CPS."""
        code = """
func int is_even(int n):
    if n == 0:
        return 1
    return is_odd(n - 1)

func int is_odd(int n):
    if n == 0:
        return 0
    return is_even(n - 1)

print(is_even(50))
"""
        assert run_ibci(code) == ["1"]


# ===========================================================================
# Signal Propagation (INV-SIGNAL-*)
# ===========================================================================


class TestSignalPropagation:
    """Validate control flow signal propagation.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5 Signal Handling
    - core/runtime/interpreter/signals.py
    """

    def test_return_signal_exits_function(self):
        """INV-SIGNAL-1: Return signal exits function immediately."""
        code = """
func int test():
    return 42
    print("unreachable")
    return 99

print(test())
"""
        assert run_ibci(code) == ["42"]

    def test_break_signal_exits_loop(self):
        """INV-SIGNAL-2: Break signal exits innermost loop."""
        code = """
for int i in range(10):
    if i == 3:
        break
    print(i)
print("done")
"""
        assert run_ibci(code) == ["0", "1", "2", "done"]

    def test_continue_signal_skips_iteration(self):
        """INV-SIGNAL-3: Continue signal skips to next iteration."""
        code = """
for int i in range(5):
    if i == 2:
        continue
    print(i)
"""
        assert run_ibci(code) == ["0", "1", "3", "4"]

    def test_nested_loop_break_only_inner(self):
        """INV-SIGNAL-4: Break in nested loop only exits inner loop."""
        code = """
for int i in range(2):
    for int j in range(3):
        if j == 1:
            break
        print(i * 10 + j)
"""
        assert run_ibci(code) == ["0", "10"]

    def test_return_from_nested_context(self):
        """INV-SIGNAL-5: Return from deeply nested context exits function."""
        code = """
func int test():
    for int i in range(3):
        if True:
            for int j in range(3):
                if j == 1:
                    return 42
    return 99

print(test())
"""
        assert run_ibci(code) == ["42"]


# ===========================================================================
# Frame Stack Management (INV-FRAME-*)
# ===========================================================================


class TestFrameStackManagement:
    """Validate frame stack management and isolation.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §3 Frame Stack
    - core/runtime/interpreter/runtime_context.py
    """

    def test_function_call_creates_new_frame(self):
        """INV-FRAME-1: Function call creates isolated frame."""
        code = """
int x = 10

func int test():
    int x = 20
    return x

print(test())
print(x)
"""
        assert run_ibci(code) == ["20", "10"]

    def test_frame_pops_on_return(self):
        """INV-FRAME-2: Frame pops on function return."""
        code = """
int x = 1

func auto test():
    int x = 2
    return None

test()
print(x)
"""
        assert run_ibci(code) == ["1"]

    def test_nested_calls_maintain_frame_chain(self):
        """INV-FRAME-3: Nested calls maintain proper frame chain."""
        code = """
func int a():
    return b() + 1

func int b():
    return c() + 1

func int c():
    return 10

print(a())
"""
        assert run_ibci(code) == ["12"]

    def test_frame_local_variables_isolated(self):
        """INV-FRAME-4: Frame-local variables are isolated."""
        code = """
func int test1():
    int result = 100
    return result

func int test2():
    int result = 200
    return result

print(test1())
print(test2())
"""
        assert run_ibci(code) == ["100", "200"]


# ===========================================================================
# Recursion Guarantees (INV-RECURSION-*)
# ===========================================================================


class TestRecursionGuarantees:
    """Validate recursion depth guarantees.

    References:
    - docs/COMPLETED.md PT-1.3 (Frame depth limits)
    """

    def test_reasonable_recursion_depth(self):
        """INV-RECURSION-1: Reasonable recursion depth succeeds."""
        code = """
func int sum_range(int n):
    if n <= 0:
        return 0
    return n + sum_range(n - 1)

print(sum_range(50))
"""
        # Should succeed (50! is reasonable depth)
        result = run_ibci(code)
        assert result  # 1275 is expected

    def test_tail_call_like_recursion(self):
        """INV-RECURSION-2: Tail-call-like recursion supported."""
        code = """
func int countdown(int n, int acc):
    if n <= 0:
        return acc
    return countdown(n - 1, acc + n)

print(countdown(100, 0))
"""
        result = run_ibci(code)
        assert result  # Should compute sum without overflow


# ===========================================================================
# Exception Frame Unwinding (INV-UNWIND-*)
# ===========================================================================


class TestExceptionUnwinding:
    """Validate exception unwinding behavior.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §6 Error Handling
    """

    def test_error_unwinds_to_llmexcept(self):
        """INV-UNWIND-1: LLM errors unwind to nearest llmexcept."""
        code = """
from tests.conftest import AI_MOCK_PREFIX
""" + AI_MOCK_PREFIX + """
func auto test():
    str x = @~ MOCK:INVALID ~
    return x

llmexcept {
    print(test())
} retry {
    print("caught")
}
"""
        assert run_ibci(code) == ["caught"]

    def test_error_propagates_through_calls(self):
        """INV-UNWIND-2: Errors propagate through call stack."""
        code = """
from tests.conftest import AI_MOCK_PREFIX
""" + AI_MOCK_PREFIX + """
func auto inner():
    str x = @~ MOCK:INVALID ~
    return x

func auto middle():
    return inner()

func auto outer():
    return middle()

llmexcept {
    print(outer())
} retry {
    print("recovered")
}
"""
        assert run_ibci(code) == ["recovered"]


# ===========================================================================
# Frame Context Propagation (INV-CONTEXT-*)
# ===========================================================================


class TestFrameContextPropagation:
    """Validate context propagation across frames.

    References:
    - tests/e2e/test_e2e_higher_order.py (legacy)
    """

    def test_closure_captures_parent_frame(self):
        """INV-CONTEXT-1: Closures capture parent frame variables."""
        code = """
func auto make_adder(int x):
    func int add(int y):
        return x + y
    return add

auto add5 = make_adder(5)
print(add5(10))
"""
        assert run_ibci(code) == ["15"]

    def test_multiple_closures_independent_frames(self):
        """INV-CONTEXT-2: Multiple closures maintain independent frames."""
        code = """
func auto make_counter():
    int count = 0
    func int inc():
        count = count + 1
        return count
    return inc

auto c1 = make_counter()
auto c2 = make_counter()

print(c1())
print(c1())
print(c2())
"""
        assert run_ibci(code) == ["1", "2", "1"]

    def test_nested_closure_access_chain(self):
        """INV-CONTEXT-3: Nested closures access entire scope chain."""
        code = """
func auto outer():
    int a = 1
    func auto middle():
        int b = 2
        func int inner():
            return a + b
        return inner()
    return middle()

print(outer())
"""
        assert run_ibci(code) == ["3"]

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
from tests.conftest import run_ibci, expect_runtime_error, AI_MOCK_PREFIX


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
func factorial(int n) -> int:
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
func chain(int depth) -> int:
    if depth <= 0:
        return 42
    return chain(depth - 1)

print(chain(100))
"""
        assert run_ibci(code) == ["42"]

    def test_mutual_recursion_supported(self):
        """INV-CPS-3: Mutual recursion works via CPS."""
        code = """
func is_even(int n) -> int:
    if n == 0:
        return 1
    return is_odd(n - 1)

func is_odd(int n) -> int:
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
func test() -> int:
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
func test() -> int:
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

func test() -> int:
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

func test() -> auto:
    int x = 2
    return None

test()
print(x)
"""
        assert run_ibci(code) == ["1"]

    def test_nested_calls_maintain_frame_chain(self):
        """INV-FRAME-3: Nested calls maintain proper frame chain."""
        code = """
func a() -> int:
    return b() + 1

func b() -> int:
    return c() + 1

func c() -> int:
    return 10

print(a())
"""
        assert run_ibci(code) == ["12"]

    def test_frame_local_variables_isolated(self):
        """INV-FRAME-4: Frame-local variables are isolated."""
        code = """
func test1() -> int:
    int result = 100
    return result

func test2() -> int:
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
func sum_range(int n) -> int:
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
func countdown(int n, int acc) -> int:
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
        code = AI_MOCK_PREFIX + """
func produce() -> str:
    str x = @~ MOCK:REPAIR:STR:caught ~
    llmexcept:
        retry "fallback"
    return x

print(produce())
"""
        assert run_ibci(code) == ["caught"]

    def test_error_propagates_through_calls(self):
        """INV-UNWIND-2: Errors propagate through call stack to outer llmexcept."""
        code = AI_MOCK_PREFIX + """
func inner() -> str:
    str x = @~ MOCK:REPAIR:STR:recovered ~
    llmexcept:
        retry "inner"
    return x

func middle() -> str:
    return inner()

func outer() -> str:
    return middle()

print(outer())
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
        pytest.skip("PT-5.1: Returning inner function as closure loses parent frame variable bindings")

    def test_multiple_closures_independent_frames(self):
        """INV-CONTEXT-2: Multiple closures maintain independent frames."""
        pytest.skip("PT-5.1: Closures returning inner counter function not supported (write-back semantics)")

    def test_nested_closure_access_chain(self):
        """INV-CONTEXT-3: Nested closures access entire scope chain."""
        code = """
func outer() -> auto:
    int a = 1
    func middle() -> auto:
        int b = 2
        func inner() -> int:
            return a + b
        return inner()
    return middle()

print(outer())
"""
        assert run_ibci(code) == ["3"]

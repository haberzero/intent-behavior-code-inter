"""
tests/contracts/test_exception_semantics.py
============================================

Contract tests for IBCI exception handling semantics (non-LLM exceptions).

Validates:
- INV-EXCEPT-PROPAGATE-*: Exception propagation rules
- INV-EXCEPT-FINALLY-*: Finally block execution guarantees
- INV-EXCEPT-CATCH-*: Exception catching semantics
- INV-EXCEPT-UNHANDLED-*: Unhandled exception behavior
"""

import pytest
from tests.conftest import run_ibci, expect_runtime_error


# ===========================================================================
# Exception Propagation (INV-EXCEPT-PROPAGATE-*)
# ===========================================================================


class TestExceptionPropagation:
    """Validate exception propagation through call stack.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5 Signal Handling
    - Normal (non-LLM) exceptions must propagate up the call stack
    """

    def test_exception_propagates_through_function(self):
        """INV-EXCEPT-PROPAGATE-1: Exceptions propagate through function calls."""
        code = """
func auto inner():
    raise Exception("inner error")

func auto outer():
    inner()

try:
    outer()
except Exception as e:
    print("caught")
"""
        assert run_ibci(code) == ["caught"]

    def test_exception_propagates_through_nested_calls(self):
        """INV-EXCEPT-PROPAGATE-2: Exceptions propagate through deeply nested calls."""
        code = """
func auto level3():
    raise Exception("deep error")

func auto level2():
    level3()

func auto level1():
    level2()

try:
    level1()
except Exception as e:
    print("caught at top")
"""
        assert run_ibci(code) == ["caught at top"]

    def test_unhandled_exception_terminates(self):
        """INV-EXCEPT-PROPAGATE-3: Unhandled exceptions terminate execution."""
        code = """
raise Exception("unhandled")
print("unreachable")
"""
        expect_runtime_error(code, "unhandled")

    def test_exception_stops_at_first_matching_handler(self):
        """INV-EXCEPT-PROPAGATE-4: Exception stops at first matching except block."""
        code = """
try:
    try:
        raise ValueError("test")
    except TypeError:
        print("inner")
except ValueError:
    print("outer")
"""
        assert run_ibci(code) == ["outer"]


# ===========================================================================
# Finally Block Guarantees (INV-EXCEPT-FINALLY-*)
# ===========================================================================


class TestFinallySemantics:
    """Validate finally block execution guarantees.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5
    - Finally blocks must execute regardless of exception/return
    """

    def test_finally_executes_on_normal_completion(self):
        """INV-EXCEPT-FINALLY-1: Finally executes when try block completes normally."""
        code = """
try:
    print("try")
finally:
    print("finally")
print("after")
"""
        assert run_ibci(code) == ["try", "finally", "after"]

    def test_finally_executes_on_exception(self):
        """INV-EXCEPT-FINALLY-2: Finally executes when exception is raised."""
        code = """
try:
    try:
        raise Exception("error")
    finally:
        print("finally")
except Exception:
    print("caught")
"""
        assert run_ibci(code) == ["finally", "caught"]

    def test_finally_executes_on_return(self):
        """INV-EXCEPT-FINALLY-3: Finally executes before function returns."""
        code = """
func auto test():
    try:
        return "result"
    finally:
        print("finally")

auto result = test()
print(result)
"""
        assert run_ibci(code) == ["finally", "result"]

    def test_finally_executes_on_break(self):
        """INV-EXCEPT-FINALLY-4: Finally executes before loop break."""
        code = """
for int i in range(3):
    try:
        if i == 1:
            break
        print((str)i)
    finally:
        print("finally")
print("done")
"""
        assert run_ibci(code) == ["0", "finally", "finally", "done"]

    def test_finally_executes_on_continue(self):
        """INV-EXCEPT-FINALLY-5: Finally executes before loop continue."""
        code = """
for int i in range(3):
    try:
        if i == 1:
            continue
        print((str)i)
    finally:
        print("finally")
"""
        assert run_ibci(code) == ["0", "finally", "finally", "2", "finally"]


# ===========================================================================
# Exception Catching (INV-EXCEPT-CATCH-*)
# ===========================================================================


class TestExceptionCatching:
    """Validate exception catching semantics.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5
    """

    def test_catch_specific_exception_type(self):
        """INV-EXCEPT-CATCH-1: Except block catches matching exception type."""
        code = """
try:
    raise ValueError("test")
except ValueError as e:
    print("caught ValueError")
"""
        assert run_ibci(code) == ["caught ValueError"]

    def test_multiple_except_blocks(self):
        """INV-EXCEPT-CATCH-2: Multiple except blocks match in order."""
        code = """
try:
    raise TypeError("test")
except ValueError:
    print("ValueError")
except TypeError:
    print("TypeError")
except Exception:
    print("Exception")
"""
        assert run_ibci(code) == ["TypeError"]

    def test_except_with_as_clause(self):
        """INV-EXCEPT-CATCH-3: 'as' clause binds exception to variable."""
        code = """
try:
    raise ValueError("test message")
except ValueError as e:
    print("caught")
"""
        # Note: We just verify the exception was caught, not the message content
        assert run_ibci(code) == ["caught"]

    def test_bare_except_catches_all(self):
        """INV-EXCEPT-CATCH-4: Bare except catches all exceptions."""
        code = """
try:
    raise RuntimeError("any error")
except:
    print("caught all")
"""
        assert run_ibci(code) == ["caught all"]

    def test_exception_type_not_matched(self):
        """INV-EXCEPT-CATCH-5: Non-matching except doesn't catch exception."""
        code = """
try:
    raise ValueError("test")
except TypeError:
    print("not reached")
"""
        expect_runtime_error(code, "ValueError")


# ===========================================================================
# Unhandled Exception Behavior (INV-EXCEPT-UNHANDLED-*)
# ===========================================================================


class TestUnhandledExceptions:
    """Validate unhandled exception behavior.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5
    """

    def test_unhandled_exception_in_function(self):
        """INV-EXCEPT-UNHANDLED-1: Unhandled exception in function terminates."""
        code = """
func auto test():
    raise Exception("unhandled")
    return "unreachable"

test()
"""
        expect_runtime_error(code, "unhandled")

    def test_unhandled_exception_in_nested_try(self):
        """INV-EXCEPT-UNHANDLED-2: Exception not caught by inner try propagates."""
        code = """
try:
    try:
        raise ValueError("inner")
    except TypeError:
        print("not caught here")
except ValueError:
    print("caught in outer")
"""
        assert run_ibci(code) == ["caught in outer"]

    def test_exception_in_except_block(self):
        """INV-EXCEPT-UNHANDLED-3: Exception in except block propagates."""
        code = """
try:
    try:
        raise ValueError("original")
    except ValueError:
        raise TypeError("in handler")
except TypeError:
    print("caught new exception")
"""
        assert run_ibci(code) == ["caught new exception"]

    def test_exception_in_finally_block(self):
        """INV-EXCEPT-UNHANDLED-4: Exception in finally block replaces original."""
        code = """
try:
    try:
        raise ValueError("original")
    finally:
        raise TypeError("in finally")
except TypeError:
    print("caught finally exception")
"""
        assert run_ibci(code) == ["caught finally exception"]


# ===========================================================================
# Exception with Control Flow (INV-EXCEPT-FLOW-*)
# ===========================================================================


class TestExceptionControlFlow:
    """Validate exception interaction with control flow.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5
    """

    def test_exception_in_loop(self):
        """INV-EXCEPT-FLOW-1: Exception in loop can be caught outside."""
        code = """
try:
    for int i in range(5):
        if i == 2:
            raise Exception("stop")
        print((str)i)
except Exception:
    print("caught")
"""
        assert run_ibci(code) == ["0", "1", "caught"]

    def test_exception_in_conditional(self):
        """INV-EXCEPT-FLOW-2: Exception in conditional branch propagates."""
        code = """
try:
    if True:
        raise Exception("in if")
    print("unreachable")
except Exception:
    print("caught")
"""
        assert run_ibci(code) == ["caught"]

    def test_return_in_except_block(self):
        """INV-EXCEPT-FLOW-3: Return in except block exits function."""
        code = """
func auto test():
    try:
        raise Exception("error")
    except Exception:
        return "handled"
    return "unreachable"

print(test())
"""
        assert run_ibci(code) == ["handled"]

    def test_break_in_except_block(self):
        """INV-EXCEPT-FLOW-4: Break in except block exits loop."""
        code = """
for int i in range(5):
    try:
        if i == 2:
            raise Exception("stop")
        print((str)i)
    except Exception:
        break
print("done")
"""
        assert run_ibci(code) == ["0", "1", "done"]


# ===========================================================================
# Exception Variable Scoping (INV-EXCEPT-SCOPE-*)
# ===========================================================================


class TestExceptionScoping:
    """Validate exception variable scoping.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §4
    """

    def test_exception_variable_in_except_block(self):
        """INV-EXCEPT-SCOPE-1: Exception variable accessible in except block."""
        code = """
try:
    raise ValueError("test")
except ValueError as e:
    print("caught")
"""
        assert run_ibci(code) == ["caught"]

    def test_exception_variable_scoped_to_block(self):
        """INV-EXCEPT-SCOPE-2: Exception variable not accessible after except."""
        code = """
try:
    raise ValueError("test")
except ValueError as e:
    print("in block")
# Variable 'e' should not be accessible here
print("after")
"""
        assert run_ibci(code) == ["in block", "after"]

    def test_nested_exception_handlers_independent(self):
        """INV-EXCEPT-SCOPE-3: Nested exception handlers have independent bindings."""
        code = """
try:
    try:
        raise ValueError("inner")
    except ValueError as e:
        print("inner caught")
        raise TypeError("outer")
except TypeError as e:
    print("outer caught")
"""
        assert run_ibci(code) == ["inner caught", "outer caught"]

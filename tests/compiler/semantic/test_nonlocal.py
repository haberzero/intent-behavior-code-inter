"""
tests/compiler/semantic/test_nonlocal.py
=========================================

Tests for nonlocal keyword implementation:
- Lexer: nonlocal is a reserved keyword
- Parser: IbNonlocalStmt is correctly parsed
- Semantic: nonlocal names resolve to outer scope symbols
- Runtime: nonlocal assignment writes through to outer scope (Cell mechanism)
- Error handling: nonlocal in invalid contexts produces diagnostics
"""

import pytest
from tests.conftest import run_ibci, compile_ibci, compile_or_errors


class TestNonlocalBasicSemantics:
    """Basic nonlocal keyword compile and execution."""

    def test_nonlocal_simple_write_back(self):
        """Inner function modifies outer variable via nonlocal."""
        code = """
func outer() -> int:
    int count = 0
    func inc():
        nonlocal count
        count = count + 1
    inc()
    inc()
    return count

print(outer())
"""
        assert run_ibci(code) == ["2"]

    def test_nonlocal_read_outer_variable(self):
        """Inner function reads outer variable without writing (nonlocal still works)."""
        code = """
func outer() -> int:
    int x = 42
    func inner() -> int:
        nonlocal x
        return x
    return inner()

print(outer())
"""
        assert run_ibci(code) == ["42"]

    def test_nonlocal_multiple_variables(self):
        """nonlocal with multiple variable names."""
        code = """
func outer() -> int:
    int a = 1
    int b = 2
    func swap():
        nonlocal a, b
        int temp = a
        a = b
        b = temp
    swap()
    return a + b * 10

print(outer())
"""
        assert run_ibci(code) == ["12"]

    def test_nonlocal_counter_pattern(self):
        """Classic counter closure with nonlocal (called within outer scope)."""
        code = """
func test_counter() -> int:
    int count = 0
    func increment():
        nonlocal count
        count = count + 1
    func get_count() -> int:
        nonlocal count
        return count
    increment()
    increment()
    increment()
    return get_count()

print(test_counter())
"""
        assert run_ibci(code) == ["3"]

    def test_nonlocal_nested_two_levels(self):
        """nonlocal works across two nesting levels."""
        code = """
func outer() -> int:
    int x = 0
    func middle():
        nonlocal x
        func inner():
            nonlocal x
            x = x + 10
        inner()
        x = x + 1
    middle()
    return x

print(outer())
"""
        assert run_ibci(code) == ["11"]


class TestNonlocalClosureReturn:
    """nonlocal with returned functions (closure with Cell write-back)."""

    def test_nonlocal_returned_function_read(self):
        """Returned closure can read captured nonlocal variable."""
        code = """
func make_getter() -> fn:
    int val = 99
    func getter() -> int:
        nonlocal val
        return val
    return getter

fn g = make_getter()
print(g())
"""
        assert run_ibci(code) == ["99"]

    def test_nonlocal_returned_function_write(self):
        """Returned closure can write to captured nonlocal variable (Cell)."""
        code = """
func make_counter() -> fn:
    int count = 0
    func inc() -> int:
        nonlocal count
        count = count + 1
        return count
    return inc

fn counter = make_counter()
print(counter())
print(counter())
print(counter())
"""
        assert run_ibci(code) == ["1", "2", "3"]

    def test_nonlocal_multiple_closures_share_cell(self):
        """Multiple closures share the same Cell for nonlocal variable."""
        code = """
func make_pair() -> list:
    int shared = 0
    func inc() -> int:
        nonlocal shared
        shared = shared + 1
        return shared
    func get() -> int:
        nonlocal shared
        return shared
    return [inc, get]

auto pair = make_pair()
fn do_inc = pair[0]
fn do_get = pair[1]
do_inc()
do_inc()
print(do_get())
"""
        assert run_ibci(code) == ["2"]


class TestNonlocalErrorDiagnostics:
    """Compile-time diagnostics for invalid nonlocal usage."""

    def test_nonlocal_at_module_scope_error(self):
        """nonlocal at module scope should produce SEM_060."""
        code = """
nonlocal x
int x = 1
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_060" in errors

    def test_nonlocal_undefined_in_outer_scope(self):
        """nonlocal referencing non-existent outer variable should produce SEM_061."""
        code = """
func outer():
    func inner():
        nonlocal does_not_exist
        does_not_exist = 1
    inner()
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_061" in errors


class TestNonlocalInteractionWithLambda:
    """Interaction between nonlocal and lambda captures."""

    def test_nonlocal_and_lambda_coexist(self):
        """nonlocal variable can also be captured by a lambda."""
        code = """
func outer() -> int:
    int x = 0
    func inc():
        nonlocal x
        x = x + 1
    fn getter = lambda: x
    inc()
    inc()
    return getter()

print(outer())
"""
        assert run_ibci(code) == ["2"]

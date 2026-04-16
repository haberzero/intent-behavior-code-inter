"""
tests/e2e/test_e2e_functions.py

End-to-end tests for IBCI function definitions and calls.

Coverage:
  - Simple function definitions (def)
  - Function return values
  - Multiple parameters
  - Recursive functions
  - Function calls as expressions
  - Void functions
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    def callback(text):
        lines.append(str(text))
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=callback, silent=True)
    return lines


# ---------------------------------------------------------------------------
# 1. Basic function definitions
# ---------------------------------------------------------------------------

class TestE2EFunctions:
    def test_simple_function_call(self):
        code = """func greet(str name) -> str:
    return "Hello, " + name

str msg = greet("Alice")
print(msg)
"""
        lines = run_and_capture(code)
        assert "Hello, Alice" in lines

    def test_int_function(self):
        code = """func add(int a, int b) -> int:
    return a + b

int result = add(3, 4)
print((str)result)
"""
        lines = run_and_capture(code)
        assert "7" in lines

    def test_void_function(self):
        code = """func say_hello():
    print("hello from function")

say_hello()
"""
        lines = run_and_capture(code)
        assert "hello from function" in lines

    def test_function_with_local_vars(self):
        code = """func compute(int x) -> int:
    int doubled = x * 2
    int result = doubled + 1
    return result

print((str)compute(5))
"""
        lines = run_and_capture(code)
        assert "11" in lines


# ---------------------------------------------------------------------------
# 2. Return values
# ---------------------------------------------------------------------------

class TestE2EReturn:
    def test_return_in_if(self):
        code = """func abs_val(int x) -> int:
    if x < 0:
        return -x
    return x

print((str)abs_val(-5))
print((str)abs_val(3))
"""
        lines = run_and_capture(code)
        assert "5" in lines
        assert "3" in lines

    def test_early_return(self):
        code = """func check(int x) -> str:
    if x > 10:
        return "big"
    return "small"

print(check(15))
print(check(5))
"""
        lines = run_and_capture(code)
        assert "big" in lines
        assert "small" in lines


# ---------------------------------------------------------------------------
# 3. Recursive functions
# ---------------------------------------------------------------------------

class TestE2ERecursion:
    def test_factorial(self):
        code = """func factorial(int n) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print((str)factorial(5))
"""
        lines = run_and_capture(code)
        assert "120" in lines

    def test_fibonacci(self):
        code = """func fib(int n) -> int:
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

print((str)fib(10))
"""
        lines = run_and_capture(code)
        assert "55" in lines


# ---------------------------------------------------------------------------
# 4. Function as expression
# ---------------------------------------------------------------------------

class TestE2EFuncExpression:
    def test_function_in_expression(self):
        code = """func double(int x) -> int:
    return x * 2

int result = double(5) + 10
print((str)result)
"""
        lines = run_and_capture(code)
        assert "20" in lines

    def test_nested_function_calls(self):
        code = """func add(int a, int b) -> int:
    return a + b

func mul(int a, int b) -> int:
    return a * b

int result = add(mul(2, 3), 4)
print((str)result)
"""
        lines = run_and_capture(code)
        assert "10" in lines

    def test_multiple_calls_same_function(self):
        code = """func inc(int x) -> int:
    return x + 1

int a = inc(1)
int b = inc(a)
int c = inc(b)
print((str)c)
"""
        lines = run_and_capture(code)
        assert "4" in lines

"""
tests/e2e/test_e2e_advanced.py

End-to-end tests for advanced IBCI features.

Coverage:
  - Tuple unpacking
  - List operations (len, append, etc.)
  - Dict operations (subscript, keys)
  - Nested scopes
  - String methods
  - Multiple statements on separate lines
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
# 1. Tuple unpacking
# ---------------------------------------------------------------------------

class TestE2ETupleUnpack:
    def test_tuple_unpack_basic(self):
        code = """(int x, int y) = (10, 20)
print((str)x)
print((str)y)
"""
        lines = run_and_capture(code)
        assert "10" in lines
        assert "20" in lines

    def test_tuple_in_for(self):
        code = """list pairs = [[1, 2], [3, 4]]
for (int a, int b) in pairs:
    int sum = a + b
    print((str)sum)
"""
        lines = run_and_capture(code)
        assert "3" in lines
        assert "7" in lines


# ---------------------------------------------------------------------------
# 2. List operations
# ---------------------------------------------------------------------------

class TestE2EListOps:
    def test_list_subscript(self):
        code = """list items = [10, 20, 30]
int first = (int)items[0]
print((str)first)
"""
        lines = run_and_capture(code)
        assert "10" in lines

    def test_list_len(self):
        code = """list items = [1, 2, 3, 4, 5]
int length = items.len()
print((str)length)
"""
        lines = run_and_capture(code)
        assert "5" in lines

    def test_list_append(self):
        code = """list items = [1, 2]
items.append(3)
print((str)items.len())
"""
        lines = run_and_capture(code)
        assert "3" in lines


# ---------------------------------------------------------------------------
# 3. Dict operations
# ---------------------------------------------------------------------------

class TestE2EDictOps:
    def test_dict_subscript(self):
        code = """dict d = {"name": "Alice", "age": 30}
str name = (str)d["name"]
print(name)
"""
        lines = run_and_capture(code)
        assert "Alice" in lines

    def test_dict_assignment(self):
        code = """dict d = {"a": 1}
d["b"] = 2
print((str)d)
"""
        lines = run_and_capture(code)
        assert any("b" in l for l in lines)


# ---------------------------------------------------------------------------
# 4. String methods
# ---------------------------------------------------------------------------

class TestE2EStringMethods:
    def test_string_len(self):
        code = """str s = "hello"
int length = s.len()
print((str)length)
"""
        lines = run_and_capture(code)
        assert "5" in lines

    def test_string_contains(self):
        code = """str s = "hello world"
bool has = s.contains("world")
print((str)has)
"""
        lines = run_and_capture(code)
        assert any("true" in l.lower() or "True" in l for l in lines)


# ---------------------------------------------------------------------------
# 5. Nested scopes
# ---------------------------------------------------------------------------

class TestE2ENestedScopes:
    def test_function_does_not_leak(self):
        code = """int x = 10
def modify() -> int:
    int x = 20
    return x

int result = modify()
print((str)x)
print((str)result)
"""
        lines = run_and_capture(code)
        assert "10" in lines  # outer x unchanged
        assert "20" in lines  # function returned its local x


# ---------------------------------------------------------------------------
# 6. Multi-line complex program
# ---------------------------------------------------------------------------

class TestE2EComplexProgram:
    def test_factorial_program(self):
        code = """def factorial(int n) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

list results = []
int i = 1
while i <= 5:
    int f = factorial(i)
    results.append(f)
    i = i + 1

for int val in results:
    print((str)val)
"""
        lines = run_and_capture(code)
        assert "1" in lines
        assert "2" in lines
        assert "6" in lines
        assert "24" in lines
        assert "120" in lines

    def test_string_builder(self):
        code = """str result = ""
list words = ["hello", " ", "world"]
for str w in words:
    result = result + w
print(result)
"""
        lines = run_and_capture(code)
        assert "hello world" in lines

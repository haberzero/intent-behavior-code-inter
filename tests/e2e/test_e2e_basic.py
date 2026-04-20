"""
tests/e2e/test_e2e_basic.py

End-to-end tests for basic IBCI programs via IBCIEngine.run_string().
These tests verify the full pipeline: compile → execute → output.

Coverage:
  - Variable declarations and assignments (all types)
  - Arithmetic operations
  - String operations
  - Print output capture
  - Type casting
  - Boolean logic
  - List and dict operations
"""

import os
import pytest
from core.engine import IBCIEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def captured_output():
    """Capture print output from IBCI programs."""
    lines = []
    def callback(text):
        lines.append(str(text))
    return lines, callback


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)


def run_and_capture(code: str):
    """Helper: run IBCI code and return captured output lines."""
    lines = []
    def callback(text):
        lines.append(str(text))
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=callback, silent=True)
    return lines


# ---------------------------------------------------------------------------
# 1. Variable declarations
# ---------------------------------------------------------------------------

class TestE2EVariables:
    def test_int_variable(self):
        lines = run_and_capture('int x = 42\nprint((str)x)')
        assert "42" in lines

    def test_str_variable(self):
        lines = run_and_capture('str name = "Alice"\nprint(name)')
        assert "Alice" in lines

    def test_float_variable(self):
        lines = run_and_capture('float pi = 3.14\nprint((str)pi)')
        assert any("3.14" in l for l in lines)

    def test_bool_variable_true(self):
        lines = run_and_capture('bool flag = true\nprint((str)flag)')
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_bool_variable_false(self):
        lines = run_and_capture('bool flag = false\nprint((str)flag)')
        assert any("false" in l.lower() or "False" in l for l in lines)

    def test_list_variable(self):
        lines = run_and_capture('list items = [1, 2, 3]\nprint((str)items)')
        assert any("1" in l and "2" in l and "3" in l for l in lines)

    def test_dict_variable(self):
        lines = run_and_capture('dict d = {"key": "value"}\nprint((str)d)')
        assert any("key" in l for l in lines)


# ---------------------------------------------------------------------------
# 2. Arithmetic operations
# ---------------------------------------------------------------------------

class TestE2EArithmetic:
    def test_addition(self):
        lines = run_and_capture('int x = 3 + 4\nprint((str)x)')
        assert "7" in lines

    def test_subtraction(self):
        lines = run_and_capture('int x = 10 - 3\nprint((str)x)')
        assert "7" in lines

    def test_multiplication(self):
        lines = run_and_capture('int x = 6 * 7\nprint((str)x)')
        assert "42" in lines

    def test_division(self):
        lines = run_and_capture('float x = 10.0 / 3.0\nprint((str)x)')
        assert any("3.3" in l for l in lines)

    def test_modulo(self):
        lines = run_and_capture('int x = 10 % 3\nprint((str)x)')
        assert "1" in lines

    def test_precedence(self):
        lines = run_and_capture('int x = 2 + 3 * 4\nprint((str)x)')
        assert "14" in lines

    def test_parentheses(self):
        lines = run_and_capture('int x = (2 + 3) * 4\nprint((str)x)')
        assert "20" in lines

    def test_negative_number(self):
        lines = run_and_capture('int x = -5\nprint((str)x)')
        assert "-5" in lines


# ---------------------------------------------------------------------------
# 3. String operations
# ---------------------------------------------------------------------------

class TestE2EStrings:
    def test_string_concat(self):
        lines = run_and_capture('str s = "hello" + " " + "world"\nprint(s)')
        assert "hello world" in lines

    def test_string_with_variable(self):
        lines = run_and_capture('str name = "Bob"\nstr msg = "Hi " + name\nprint(msg)')
        assert "Hi Bob" in lines


# ---------------------------------------------------------------------------
# 4. Type casting
# ---------------------------------------------------------------------------

class TestE2ETypeCast:
    def test_int_to_str(self):
        lines = run_and_capture('int x = 42\nstr s = (str)x\nprint(s)')
        assert "42" in lines

    def test_str_to_int(self):
        lines = run_and_capture('str s = "42"\nint x = (int)s\nprint((str)x)')
        assert "42" in lines

    def test_float_to_int(self):
        lines = run_and_capture('float f = 3.7\nint x = (int)f\nprint((str)x)')
        assert "3" in lines

    def test_int_to_float(self):
        lines = run_and_capture('int x = 42\nfloat f = (float)x\nprint((str)f)')
        assert any("42" in l for l in lines)


# ---------------------------------------------------------------------------
# 5. Comparison and boolean logic
# ---------------------------------------------------------------------------

class TestE2EBoolLogic:
    def test_less_than(self):
        lines = run_and_capture('bool r = 1 < 2\nprint((str)r)')
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_greater_than(self):
        lines = run_and_capture('bool r = 5 > 3\nprint((str)r)')
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_equal(self):
        lines = run_and_capture('bool r = 2 == 2\nprint((str)r)')
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_not_equal(self):
        lines = run_and_capture('bool r = 2 != 3\nprint((str)r)')
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_and_logic(self):
        lines = run_and_capture('bool r = true and true\nprint((str)r)')
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_or_logic(self):
        lines = run_and_capture('bool r = false or true\nprint((str)r)')
        assert any("true" in l.lower() or "True" in l for l in lines)


# ---------------------------------------------------------------------------
# 6. Variable reassignment
# ---------------------------------------------------------------------------

class TestE2EReassignment:
    def test_reassign_int(self):
        code = """int x = 10
x = 20
print((str)x)
"""
        lines = run_and_capture(code)
        assert "20" in lines

    def test_reassign_str(self):
        code = """str name = "Alice"
name = "Bob"
print(name)
"""
        lines = run_and_capture(code)
        assert "Bob" in lines

    def test_compound_assignment(self):
        code = """int x = 10
x = x + 5
print((str)x)
"""
        lines = run_and_capture(code)
        assert "15" in lines


# ---------------------------------------------------------------------------
# 7. String method tests
# ---------------------------------------------------------------------------

class TestE2EStringMethods:
    def test_str_split_with_separator(self):
        """str.split() correctly unboxes IbString separator."""
        code = """str s = "Hello World Foo"
list parts = s.split(" ")
print((str)parts.len())
print(parts[0])
print(parts[1])
print(parts[2])
"""
        lines = run_and_capture(code)
        assert "3" in lines
        assert "Hello" in lines
        assert "World" in lines
        assert "Foo" in lines

    def test_str_split_no_separator(self):
        """str.split() with no args splits on whitespace."""
        code = """str s = "a  b  c"
list parts = s.split()
print((str)parts.len())
"""
        lines = run_and_capture(code)
        assert "3" in lines


# ---------------------------------------------------------------------------
# 8. Not operator type correctness
# ---------------------------------------------------------------------------

class TestE2ENotOperator:
    def test_not_true_returns_bool(self):
        """not true should return bool false, assignable to bool variable."""
        code = """bool x = not true
print((str)x)
"""
        lines = run_and_capture(code)
        assert any("false" in l.lower() for l in lines)

    def test_not_false_returns_bool(self):
        """not false should return bool true."""
        code = """bool y = not false
print((str)y)
"""
        lines = run_and_capture(code)
        assert any("true" in l.lower() for l in lines)

    def test_not_in_condition(self):
        """not operator result should work in if conditions."""
        code = """bool flag = true
if not flag:
    print("wrong")
else:
    print("correct")
"""
        lines = run_and_capture(code)
        assert "correct" in lines


# ---------------------------------------------------------------------------
# 9. Ternary operator tests
# ---------------------------------------------------------------------------

class TestE2ETernaryOperator:
    def test_ternary_true_branch(self):
        """Ternary returns body when condition is true."""
        lines = run_and_capture('int x = 1\nstr r = x > 0 ? "pos" : "neg"\nprint(r)')
        assert "pos" in lines

    def test_ternary_false_branch(self):
        """Ternary returns orelse when condition is false."""
        lines = run_and_capture('int x = -1\nstr r = x > 0 ? "pos" : "neg"\nprint(r)')
        assert "neg" in lines

    def test_ternary_with_bool_var(self):
        """Ternary works directly with a bool variable."""
        code = """bool flag = true
int a = flag ? 10 : 20
print((str)a)
"""
        lines = run_and_capture(code)
        assert "10" in lines

    def test_ternary_nested(self):
        """Ternary is right-associative and can be nested."""
        code = """int x = 5
str label = x > 10 ? "big" : (x > 3 ? "mid" : "small")
print(label)
"""
        lines = run_and_capture(code)
        assert "mid" in lines

    def test_ternary_with_arithmetic(self):
        """Ternary can return arithmetic expressions."""
        code = """int n = 3
int result = n > 0 ? n * 2 : 0
print((str)result)
"""
        lines = run_and_capture(code)
        assert "6" in lines

    def test_ternary_lower_precedence_than_or(self):
        """'or' binds tighter than ternary: (a or b) ? x : y."""
        code = """bool a = false
bool b = true
str r = a or b ? "yes" : "no"
print(r)
"""
        lines = run_and_capture(code)
        assert "yes" in lines

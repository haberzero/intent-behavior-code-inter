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


# ---------------------------------------------------------------------------
# String methods (Bug Fix: replace/startswith/endswith + spec alignment)
# ---------------------------------------------------------------------------

class TestE2EStringMethods:
    def test_str_replace(self):
        code = 'str s = "hello world"\nstr r = s.replace("world", "ibci")\nprint(r)'
        lines = run_and_capture(code)
        assert "hello ibci" in lines

    def test_str_startswith_true(self):
        code = 'str s = "hello"\nbool r = s.startswith("hel")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_str_startswith_false(self):
        code = 'str s = "hello"\nbool r = s.startswith("world")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_str_endswith_true(self):
        code = 'str s = "hello"\nbool r = s.endswith("llo")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_str_endswith_false(self):
        code = 'str s = "hello"\nbool r = s.endswith("xyz")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_str_find_last(self):
        code = 'str s = "abcabc"\nint idx = s.find_last("c")\nprint((str)idx)'
        lines = run_and_capture(code)
        assert "5" in lines

    def test_str_is_empty_true(self):
        code = 'str s = ""\nbool r = s.is_empty()\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_str_is_empty_false(self):
        code = 'str s = "hi"\nbool r = s.is_empty()\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines


# ---------------------------------------------------------------------------
# List methods (new: insert, remove, index, count, contains)
# ---------------------------------------------------------------------------

class TestE2EListMethods:
    def test_list_insert(self):
        code = 'list nums = [1, 3]\nnums.insert(1, 2)\nprint((str)nums.len())'
        lines = run_and_capture(code)
        assert "3" in lines

    def test_list_remove(self):
        code = 'list nums = [1, 2, 3]\nnums.remove(2)\nprint((str)nums.len())'
        lines = run_and_capture(code)
        assert "2" in lines

    def test_list_index(self):
        code = 'list nums = [10, 20, 30]\nint idx = nums.index(20)\nprint((str)idx)'
        lines = run_and_capture(code)
        assert "1" in lines

    def test_list_count(self):
        code = 'list nums = [1, 2, 2, 3]\nint c = nums.count(2)\nprint((str)c)'
        lines = run_and_capture(code)
        assert "2" in lines

    def test_list_contains_true(self):
        code = 'list nums = [1, 2, 3]\nbool r = nums.contains(2)\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_list_contains_false(self):
        code = 'list nums = [1, 2, 3]\nbool r = nums.contains(9)\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_list_add_concatenate(self):
        code = 'list a = [1, 2]\nlist b = [3, 4]\nlist c = a + b\nprint((str)c.len())'
        lines = run_and_capture(code)
        assert "4" in lines


# ---------------------------------------------------------------------------
# Dict methods (new: pop)
# ---------------------------------------------------------------------------

class TestE2EDictMethods:
    def test_dict_pop(self):
        code = 'dict d = {"a": 1, "b": 2}\nint v = (int)d.pop("a")\nprint((str)v)\nprint((str)d.len())'
        lines = run_and_capture(code)
        assert "1" in lines
        assert "1" in lines  # remaining len == 1


# ---------------------------------------------------------------------------
# in / not in operators
# ---------------------------------------------------------------------------

class TestE2EInOperator:
    def test_str_in_true(self):
        code = 'str s = "hello world"\nbool r = "world" in s\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_str_in_false(self):
        code = 'str s = "hello"\nbool r = "xyz" in s\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_str_not_in(self):
        code = 'str s = "hello"\nbool r = "xyz" not in s\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_list_in_true(self):
        code = 'list nums = [1, 2, 3]\nbool r = 2 in nums\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_list_in_false(self):
        code = 'list nums = [1, 2, 3]\nbool r = 9 in nums\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_list_not_in(self):
        code = 'list nums = [1, 2, 3]\nbool r = 9 not in nums\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_dict_in_true(self):
        code = 'dict d = {"a": 1}\nbool r = "a" in d\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_dict_in_false(self):
        code = 'dict d = {"a": 1}\nbool r = "z" in d\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_in_in_if(self):
        code = 'list items = ["apple", "banana"]\nif "apple" in items:\n    print("found")\n'
        lines = run_and_capture(code)
        assert "found" in lines

    def test_not_in_in_if(self):
        code = 'list items = ["apple", "banana"]\nif "cherry" not in items:\n    print("missing")\n'
        lines = run_and_capture(code)
        assert "missing" in lines


# ---------------------------------------------------------------------------
# in/not in with generic (specialised) containers
# ---------------------------------------------------------------------------

class TestE2EInOperatorGeneric:
    """Regression tests: 'in'/'not in' must work with generic-typed containers
    (list[str], dict[str,int], etc.).  Before the fix these produced a spurious
    SEM_003 because the semantic analyser compared spec.name (e.g. 'list[str]')
    against the hard-coded base-name set ('list', 'dict', ...)."""

    def test_list_str_in_true(self):
        code = 'list[str] names = ["alice", "bob"]\nbool r = "alice" in names\nprint((str)r)\n'
        assert "True" in run_and_capture(code) or "1" in run_and_capture(code)

    def test_list_str_in_false(self):
        code = 'list[str] names = ["alice", "bob"]\nbool r = "dave" in names\nprint((str)r)\n'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_list_str_not_in(self):
        code = 'list[str] names = ["alice", "bob"]\nbool r = "dave" not in names\nprint((str)r)\n'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_list_int_in(self):
        code = 'list[int] nums = [10, 20, 30]\nbool r = 20 in nums\nprint((str)r)\n'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_dict_str_int_in_true(self):
        code = 'dict[str,int] d = {"a": 1, "b": 2}\nbool r = "a" in d\nprint((str)r)\n'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_dict_str_int_in_false(self):
        code = 'dict[str,int] d = {"a": 1}\nbool r = "z" in d\nprint((str)r)\n'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_dict_str_int_not_in(self):
        code = 'dict[str,int] d = {"a": 1}\nbool r = "z" not in d\nprint((str)r)\n'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_generic_list_in_if_branch(self):
        code = 'list[str] items = ["apple", "banana"]\nif "apple" in items:\n    print("found")\n'
        assert "found" in run_and_capture(code)

    def test_generic_list_not_in_if_branch(self):
        code = 'list[str] items = ["apple", "banana"]\nif "cherry" not in items:\n    print("missing")\n'
        assert "missing" in run_and_capture(code)


# ---------------------------------------------------------------------------
# Exception constructable: raise Exception("msg") and e.message
# ---------------------------------------------------------------------------

class TestE2EExceptionConstructable:
    def test_raise_exception_with_message(self):
        code = '''try:
    raise Exception("something went wrong")
except Exception as e:
    print(e.message)
'''
        lines = run_and_capture(code)
        assert "something went wrong" in lines

    def test_exception_message_field_access(self):
        code = '''try:
    int x = (int)"bad"
except Exception as e:
    str msg = e.message
    print("caught")
'''
        lines = run_and_capture(code)
        assert "caught" in lines


# ---------------------------------------------------------------------------
# str.trim / to_upper / to_lower (IBCI-style aliases)
# ---------------------------------------------------------------------------

class TestE2EStringAliases:
    def test_str_trim(self):
        code = 'str s = "  hello  "\nstr r = s.trim()\nprint(r)'
        lines = run_and_capture(code)
        assert "hello" in lines

    def test_str_to_upper(self):
        code = 'str s = "hello"\nstr r = s.to_upper()\nprint(r)'
        lines = run_and_capture(code)
        assert "HELLO" in lines

    def test_str_to_lower(self):
        code = 'str s = "HELLO"\nstr r = s.to_lower()\nprint(r)'
        lines = run_and_capture(code)
        assert "hello" in lines


# ---------------------------------------------------------------------------
# dict.contains / dict.remove
# ---------------------------------------------------------------------------

class TestE2EDictContainsRemove:
    def test_dict_contains_true(self):
        code = 'dict d = {"a": 1, "b": 2}\nbool r = d.contains("a")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "True" in lines or "1" in lines

    def test_dict_contains_false(self):
        code = 'dict d = {"a": 1}\nbool r = d.contains("z")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines

    def test_dict_remove(self):
        code = 'dict d = {"a": 1, "b": 2}\nd.remove("a")\nprint((str)d.len())'
        lines = run_and_capture(code)
        assert "1" in lines

    def test_dict_contains_after_remove(self):
        code = 'dict d = {"x": 10}\nd.remove("x")\nbool r = d.contains("x")\nprint((str)r)'
        lines = run_and_capture(code)
        assert "False" in lines or "0" in lines


# ---------------------------------------------------------------------------
# Bug-fix regression: any variable cross-type reassignment (Bug A)
# ---------------------------------------------------------------------------

class TestE2EAnyVariable:
    """any variables must accept reassignment to any type without SEM_003."""

    def test_any_reassign_int_to_str(self):
        code = 'any val = 42\nval = "hello"\nprint(val)'
        lines = run_and_capture(code)
        assert "hello" in lines

    def test_any_reassign_str_to_int(self):
        code = 'any val = "start"\nval = 99\nprint(val)'
        lines = run_and_capture(code)
        assert "99" in lines

    def test_any_reassign_multiple_types(self):
        code = 'any val = 1\nval = "two"\nval = true\nprint(val)'
        lines = run_and_capture(code)
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_any_holds_initial_value(self):
        code = 'any val = 100\nprint(val)'
        lines = run_and_capture(code)
        assert "100" in lines


# ---------------------------------------------------------------------------
# Undeclared variable → any semantics
# ---------------------------------------------------------------------------

class TestUndeclaredVarAnySemantics:
    """Undeclared variables (no type annotation, no auto keyword) get 'any' semantics."""

    def test_undeclared_var_can_hold_any_type(self):
        """x = 42 followed by x = 'hello' works because x has any semantics."""
        code = """x = 42
x = "hello"
print(x)
"""
        lines = run_and_capture(code)
        assert "hello" in lines

    def test_undeclared_var_printable(self):
        """An undeclared variable can be printed without explicit cast."""
        code = """msg = "world"
print(msg)
"""
        lines = run_and_capture(code)
        assert "world" in lines

    def test_explicit_auto_still_infers_type(self):
        """auto x = 42 still infers int (auto semantics unchanged)."""
        code = """auto x = 42
print((str)x)
"""
        lines = run_and_capture(code)
        assert "42" in lines


# ---------------------------------------------------------------------------
# Container multi-type: list[int, str, list]
# ---------------------------------------------------------------------------

class TestContainerMultiType:
    """Tests for multi-type container declarations: list[int, str, list]."""

    def test_multi_type_list_declaration_compiles(self):
        """list[int, str] declaration compiles without error."""
        from core.engine import IBCIEngine
        import os
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        artifact = engine.compile_string(
            'list[int, str] items = [1, "hello", 2]', silent=True
        )
        assert artifact is not None

    def test_multi_type_list_with_nested_list_compiles(self):
        """list[int, str, list] with nested list type compiles."""
        from core.engine import IBCIEngine
        import os
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        artifact = engine.compile_string(
            'list[int, str, list] mixed = [1, "hello"]', silent=True
        )
        assert artifact is not None

    def test_multi_type_list_element_access_returns_any(self):
        """Element of multi-type list is any; user must cast."""
        code = """list[int, str] items = [42, "world"]
any val = items[0]
print((str)val)
any val2 = items[1]
print(val2)
"""
        lines = run_and_capture(code)
        assert "42" in lines
        assert "world" in lines

    def test_multi_type_list_for_iteration(self):
        """Multi-type list can be iterated; element type is any."""
        code = """list[int, str] mixed = [1, "two", 3]
for any item in mixed:
    print((str)item)
"""
        lines = run_and_capture(code)
        assert "1" in lines
        assert "two" in lines
        assert "3" in lines

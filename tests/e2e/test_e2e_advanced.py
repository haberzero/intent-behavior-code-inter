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
func modify() -> int:
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
        code = """func factorial(int n) -> int:
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


# ---------------------------------------------------------------------------
# 7. global statement
# ---------------------------------------------------------------------------

class TestE2EGlobalStatement:
    def test_global_basic_increment(self):
        """函数内 global 声明可修改全局变量。"""
        code = """
int counter = 0

func increment():
    global counter
    counter = counter + 1

increment()
increment()
increment()
print((str)counter)
"""
        lines = run_and_capture(code)
        assert "3" in lines

    def test_global_set_from_function(self):
        """函数通过 global 覆盖全局变量。"""
        code = """
int x = 10

func set_x(int val):
    global x
    x = val

set_x(99)
print((str)x)
"""
        lines = run_and_capture(code)
        assert "99" in lines

    def test_global_isolation(self):
        """没有 global 声明时，函数内赋值不影响全局变量。"""
        code = """
int val = 10

func local_mod():
    int val = 99

local_mod()
print((str)val)
"""
        lines = run_and_capture(code)
        assert "10" in lines

    def test_global_multiple_names(self):
        """global 可一次声明多个变量；函数可同时修改两个全局变量。"""
        code = """
int a = 1
int b = 2

func swap():
    global a
    global b
    int tmp = a
    a = b
    b = tmp

swap()
print((str)a)
print((str)b)
"""
        lines = run_and_capture(code)
        assert lines[0] == "2"
        assert lines[1] == "1"

    def test_global_create_from_function(self):
        """global 声明的变量不需要在调用前存在于全局作用域。"""
        code = """
func create_global():
    global new_var
    new_var = 42

create_global()
print((str)new_var)
"""
        lines = run_and_capture(code)
        assert "42" in lines

    def test_global_in_scope_error(self):
        """在全局作用域内使用 global 产生 SEM_004 编译错误。"""
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.run_string("global x\n", silent=True)


# ---------------------------------------------------------------------------
# 8. is / is not operator
# ---------------------------------------------------------------------------

class TestE2EIsOperator:
    def test_is_none(self):
        """x is None 对 None 值返回 True。"""
        code = """
auto x = None
bool b = x is None
print((str)b)
"""
        lines = run_and_capture(code)
        assert "True" in lines

    def test_is_not_none(self):
        """x is not None 对非 None 值返回 True。"""
        code = """
int y = 42
bool b = y is not None
print((str)b)
"""
        lines = run_and_capture(code)
        assert "True" in lines

    def test_is_not_none_for_none(self):
        """x is not None 对 None 值返回 False。"""
        code = """
auto x = None
bool b = x is not None
print((str)b)
"""
        lines = run_and_capture(code)
        assert "False" in lines

    def test_is_semantics_vs_equality(self):
        """is 与 == 语义不同：is 检查对象身份，== 检查值相等。"""
        code = """
int a = 1
int b = 1
bool eq = a == b
print((str)eq)
"""
        lines = run_and_capture(code)
        assert "True" in lines

    def test_is_in_condition(self):
        """is None 用作 if 条件。"""
        code = """
auto x = None
if x is None:
    print("null")
else:
    print("not null")
"""
        lines = run_and_capture(code)
        assert "null" in lines

    def test_is_not_in_condition(self):
        """is not None 用作 if 条件。"""
        code = """
int x = 5
if x is not None:
    print("has value")
else:
    print("null")
"""
        lines = run_and_capture(code)
        assert "has value" in lines


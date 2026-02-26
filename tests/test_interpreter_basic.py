import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.support.diagnostics.issue_tracker import IssueTracker
from core.types.diagnostic_types import CompilerError
from core.engine import IBCIEngine

class TestInterpreterBasic(unittest.TestCase):
    """
    重构后的基础单元测试，适配 RuntimeContext 架构。
    """
    def run_code(self, code):
        engine = IBCIEngine()
        # 创建临时文件
        test_file = "tmp_basic_test.ibci"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code.strip() + "\n")
        
        try:
            success = engine.run(test_file)
            if not success:
                if engine.scheduler.issue_tracker.has_errors:
                     self.fail(f"Execution failed with errors: {[d.message for d in engine.scheduler.issue_tracker.diagnostics]}")
                self.fail("Execution failed")
            return None, engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_variable_declaration_assignment(self):
        code = """
int a = 10
int b = a + 5
var c = b
"""
        _, interp = self.run_code(code)
        # 通过 context 获取变量，不再通过 global_scope 属性
        self.assertEqual(interp.context.get_variable("a"), 10)
        self.assertEqual(interp.context.get_variable("b"), 15)
        self.assertEqual(interp.context.get_variable("c"), 15)

    def test_scope_shadowing(self):
        code = """
int x = 10
func test() -> int:
    int x = 20
    return x

int result = test()
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("result"), 20)
        self.assertEqual(interp.context.get_variable("x"), 10)

    def test_if_elif_else(self):
        code = """
func check(int n) -> int:
    if n > 10:
        return 1
    elif n == 10:
        return 0
    else:
        return -1

int res1 = check(15)
int res2 = check(10)
int res3 = check(5)
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("res1"), 1)
        self.assertEqual(interp.context.get_variable("res2"), 0)
        self.assertEqual(interp.context.get_variable("res3"), -1)

    def test_while_loop(self):
        code = """
int i = 0
int sum = 0
while i < 5:
    sum = sum + i
    i = i + 1
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("sum"), 10)

    def test_for_range(self):
        code = """
int sum = 0
for i in 5:
    sum = sum + i
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("sum"), 10)

    def test_break_continue(self):
        code = """
int sum = 0
for i in 10:
    if i == 2:
        continue
    if i == 5:
        break
    sum = sum + i
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("sum"), 8)

    def test_recursion(self):
        code = """
func fib(int n) -> int:
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

int res = fib(6)
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("res"), 8)

    def test_list_operations(self):
        code = """
list l = [1, 2, 3]
l[0] = 10
int val = l[0]
list l2 = l + [4]
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("val"), 10)
        self.assertEqual(interp.context.get_variable("l2"), [10, 2, 3, 4])

    def test_dict_operations(self):
        code = """
dict d = {"a": 1, "b": 2}
int val = d["a"]
d["c"] = 3
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("val"), 1)
        d = interp.context.get_variable("d")
        self.assertEqual(d["c"], 3)

    def test_behavior_expression(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
str name = "Alice"
str res = ~~ greet $name ~~
"""
        _, interp = self.run_code(code)
        self.assertIn("Alice", interp.context.get_variable("res"))

    def test_type_casting(self):
        code = """
str s = "123"
int i = (int) s
float f = (float) i
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("i"), 123)
        self.assertEqual(interp.context.get_variable("f"), 123.0)

if __name__ == '__main__':
    unittest.main()

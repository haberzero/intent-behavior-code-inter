import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from typedef.exception_types import InterpreterError

class TestInterpreterBasic(unittest.TestCase):
    def run_code(self, code):
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        
        parser = Parser(tokens)
        module = parser.parse()
        if parser.errors:
            raise Exception(f"Parser errors: {parser.errors}")
            
        interpreter = Interpreter()
        return interpreter.interpret(module), interpreter

    # --- 1. Variable Assignment & Scoping ---
    def test_variable_declaration_assignment(self):
        code = """
int a = 10
int b = a + 5
var c = b
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("a"), 10)
        self.assertEqual(interp.global_scope.get("b"), 15)
        self.assertEqual(interp.global_scope.get("c"), 15)

    def test_scope_shadowing(self):
        code = """
int x = 10
func test() -> int:
    int x = 20
    return x

int result = test()
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("result"), 20)
        self.assertEqual(interp.global_scope.get("x"), 10) # Global x unchanged

    # --- 2. Control Flow ---
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
        self.assertEqual(interp.global_scope.get("res1"), 1)
        self.assertEqual(interp.global_scope.get("res2"), 0)
        self.assertEqual(interp.global_scope.get("res3"), -1)

    def test_while_loop(self):
        code = """
int i = 0
int sum = 0
while i < 5:
    sum = sum + i
    i = i + 1
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("sum"), 10)

    def test_for_range(self):
        code = """
int sum = 0
for i in 5:
    sum = sum + i
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("sum"), 10)

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
        # 0 + 1 + (skip 2) + 3 + 4 + (break at 5) = 8
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("sum"), 8)

    # --- 3. Functions ---
    def test_recursion(self):
        code = """
func fib(int n) -> int:
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

int res = fib(6)
"""
        # 0, 1, 1, 2, 3, 5, 8
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("res"), 8)

    # --- 4. Data Structures ---
    def test_list_operations(self):
        code = """
list l = [1, 2, 3]
l[0] = 10
int val = l[0]
list l2 = l + [4]
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("val"), 10)
        self.assertEqual(interp.global_scope.get("l2"), [10, 2, 3, 4])

    def test_dict_operations(self):
        code = """
dict d = {"a": 1, "b": 2}
int val = d["a"]
d["c"] = 3
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("val"), 1)
        d = interp.global_scope.get("d")
        self.assertEqual(d["c"], 3)

    # --- 5. Behavior Expression ---
    def test_behavior_expression(self):
        code = """
str name = "Alice"
str res = ~~ greet $name ~~
"""
        _, interp = self.run_code(code)
        # Assuming current implementation replaces variable
        self.assertIn("Alice", interp.global_scope.get("res"))

    # --- 6. Type Casting ---
    def test_type_casting(self):
        code = """
str s = "123"
int i = (int) s
float f = (float) i
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("i"), 123)
        self.assertEqual(interp.global_scope.get("f"), 123.0)

    # --- 7. Generics (Runtime Check) ---
    def test_generic_type_annotation(self):
        # This tests that the interpreter doesn't crash on generic types
        code = """
func process(List[int] data) -> int:
    return len(data)

list l = [1, 2, 3]
int res = process(l)
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("res"), 3)

if __name__ == '__main__':
    unittest.main()

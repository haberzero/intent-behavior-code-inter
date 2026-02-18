import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from typedef.exception_types import InterpreterError

class TestInterpreter(unittest.TestCase):
    def run_code(self, code):
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        
        parser = Parser(tokens)
        module = parser.parse()
        if parser.errors:
            raise Exception(f"Parser errors: {parser.errors}")
            
        interpreter = Interpreter()
        return interpreter.interpret(module), interpreter

    def test_arithmetic(self):
        code = """
int a = 10
int b = 20
int c = a + b
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("c"), 30)

    def test_if_else(self):
        code = """
int x = 10
int result = 0
if x > 5:
    result = 1
else:
    result = 2
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("result"), 1)

    def test_loop(self):
        code = """
int sum = 0
for i in 5:
    sum = sum + i
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("sum"), 10) # 0+1+2+3+4

    def test_function(self):
        code = """
func add(int x, int y) -> int:
    return x + y

int res = add(10, 5)
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("res"), 15)

    def test_recursion(self):
        code = """
func fact(int n) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)

int res = fact(5)
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("res"), 120)

    def test_string_concat(self):
        code = """
str s1 = "Hello"
str s2 = "World"
str res = s1 + " " + s2
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("res"), "Hello World")

    def test_list_access(self):
        code = """
list l = [1, 2, 3]
int x = l[1]
l[2] = 10
int y = l[2]
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("x"), 2)
        self.assertEqual(interp.global_scope.get("y"), 10)

if __name__ == '__main__':
    unittest.main()

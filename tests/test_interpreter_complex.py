import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from typedef.exception_types import InterpreterError
from typedef.diagnostic_types import CompilerError

class TestInterpreterComplex(unittest.TestCase):
    """
    重构后的复杂单元测试，验证架构的稳健性、类型保护和控制流限制。
    """
    def setUp(self):
        self.output = []

    def capture_output(self, msg):
        self.output.append(msg)

    def run_code(self, code):
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        module = parser.parse()
        interpreter = Interpreter(output_callback=self.capture_output)
        return interpreter.interpret(module)

    def test_type_checking(self):
        # 1. 测试非法的显式类型赋值
        code = 'int x = "hello"'
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

        # 2. 测试 var 的灵活性
        code_var = """
var x = 10
x = "now i am string"
"""
        # 不应抛出异常
        self.run_code(code_var)

    def test_builtin_protection(self):
        # 1. 尝试对内置函数符号赋值
        code = "print = 10"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Cannot reassign built-in variable", str(cm.exception))

        # 2. 尝试重定义内置函数
        code_func = """
func print(str s) -> None:
    pass
"""
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code_func)
        self.assertIn("Cannot redefine built-in function", str(cm.exception))

    def test_division_by_zero(self):
        code = "int x = 10 / 0"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Division by zero", str(cm.exception))

    def test_type_error_in_binop(self):
        code = 'var x = "a" + 1'
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type error in binary operation", str(cm.exception))

    def test_recursion_limit(self):
        code = """
func f(int n) -> int:
    return f(n)

f(1)
"""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        module = parser.parse()

        interp = Interpreter(output_callback=self.capture_output)
        interp.max_call_stack = 10

        with self.assertRaises(InterpreterError) as cm:
            interp.interpret(module)
        self.assertIn("maximum recursion depth exceeded", str(cm.exception))

    def test_control_flow_outside_loop(self):
        # 测试在循环外使用 break
        code = "break"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Control flow statement used outside", str(cm.exception))

    def test_len_builtin(self):
        code = """
list l = [1, 2, 3]
int length = len(l)
print(length)
"""
        self.run_code(code)
        self.assertEqual(self.output, ["3"])

if __name__ == '__main__':
    unittest.main()

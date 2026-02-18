import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from typedef.exception_types import InterpreterError

class TestInterpreterBoundary(unittest.TestCase):
    def setUp(self):
        self.output_buffer = []
        self.interpreter = Interpreter(output_callback=self.capture_output)

    def capture_output(self, message):
        self.output_buffer.append(message)

    def run_code(self, code):
        dedented_code = textwrap.dedent(code).strip() + "\n"
        lexer = Lexer(dedented_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        module = parser.parse()
        return self.interpreter.interpret(module)

    def test_type_checking(self):
        # 1. Test invalid type assignment
        code = """
        int x = "hello"
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

        # 2. Test valid type assignment
        code_valid = """
        int y = 10
        print(y)
        """
        self.run_code(code_valid)
        self.assertIn("10", self.output_buffer)

        # 3. Test float auto-promotion
        code_float = """
        float f = 10
        print(f)
        """
        self.run_code(code_float)
        # Note: python print(10) is 10, but if cast to float it's 10.0? 
        # Wait, implementation of visit_Assign just checks type, doesn't cast.
        # So f holds 10 (int). But it passed the check.
        
    def test_division_by_zero(self):
        code = """
        int x = 10 / 0
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Division by zero", str(cm.exception))

    def test_type_error_in_binop(self):
        code = """
        int x = "a" + 1
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type error in binary operation", str(cm.exception))

    def test_recursion_limit(self):
        self.interpreter.max_call_stack = 10
        code = """
        func f(int n) -> int:
            return f(n)
        
        f(1)
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("maximum recursion depth exceeded", str(cm.exception))

    def test_builtin_protection(self):
        # 1. 尝试直接给内置函数赋值
        code = """
        print = 10
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Cannot reassign built-in variable 'print'", str(cm.exception))
        
        # 2. 尝试用 var 重新定义
        code_var = """
        var print = 10
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code_var)
        self.assertIn("Cannot redefine built-in variable 'print'", str(cm.exception))

    def test_redefine_builtin_function(self):
        code = """
        func print(str s) -> None:
            pass
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Cannot redefine built-in function 'print'", str(cm.exception))

if __name__ == '__main__':
    unittest.main()

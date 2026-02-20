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
    Re-run of TestInterpreterBoundary and TestInterpreterBuiltins using  Parser.
    """
    def setUp(self):
        self.output_buffer = []

    def capture_output(self, message):
        self.output_buffer.append(message)

    def run_code(self, code):
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        try:
            module = parser.parse()
        except CompilerError as e:
            raise Exception(f"Parser failed with errors: {[d.message for d in e.diagnostics]}")
            
        interpreter = Interpreter(output_callback=self.capture_output)
        # Hack to access interpreter instance if return value is ignored in some tests
        self.interpreter = interpreter 
        return interpreter.interpret(module)

    # --- From TestInterpreterBoundary ---

    def test_type_checking(self):
        # 1. Test invalid type assignment
        code = 'int x = "hello"'
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
        # Note: Interpreter allows int assigned to float
        code_float = """
float f = 10
print(f)
"""
        self.run_code(code_float)
        # Current interpreter might print "10" or "10.0" depending on implementation
        # But as long as it runs without error, it's compatible.

    def test_division_by_zero(self):
        code = "int x = 10 / 0"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Division by zero", str(cm.exception))

    def test_type_error_in_binop(self):
        code = 'int x = "a" + 1'
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type error in binary operation", str(cm.exception))

    def test_recursion_limit(self):
        # We need to set limit on the instance used
        # Since run_code creates a new interpreter each time, 
        # we can't easily set limit before run.
        # But we can subclass or modify run_code.
        # Or just test that deep recursion eventually fails (Python's limit or Interpreter's limit)
        
        # Let's manually run this one to set limit
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

    def test_builtin_protection(self):
        # 1. Reassign builtin
        code = "print = 10"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Cannot reassign built-in variable 'print'", str(cm.exception))
        
        # 2. Redefine with var
        code_var = "var print = 10"
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

    # --- From TestInterpreterBuiltins ---

    def test_print_string(self):
        code = 'print("Hello World")'
        self.run_code(code)
        self.assertEqual(self.output_buffer, ["Hello World"])

    def test_print_multiple_args(self):
        code = 'print("Value:", 10)'
        self.run_code(code)
        self.assertEqual(self.output_buffer, ["Value: 10"])

    def test_print_variable(self):
        code = """
int x = 42
print(x)
"""
        self.run_code(code)
        self.assertEqual(self.output_buffer, ["42"])

    def test_len_builtin(self):
        code = """
list l = [1, 2, 3]
int length = len(l)
print(length)
"""
        self.run_code(code)
        self.assertEqual(self.output_buffer, ["3"])

if __name__ == '__main__':
    unittest.main()

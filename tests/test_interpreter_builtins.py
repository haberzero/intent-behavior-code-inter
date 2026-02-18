import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter

class TestInterpreterBuiltins(unittest.TestCase):
    def setUp(self):
        self.output_buffer = []
    
    def capture_output(self, message):
        self.output_buffer.append(message)

    def run_code(self, code):
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        
        parser = Parser(tokens)
        module = parser.parse()
        if parser.errors:
            raise Exception(f"Parser errors: {parser.errors}")
            
        interpreter = Interpreter(output_callback=self.capture_output)
        return interpreter.interpret(module), interpreter

    def test_print_string(self):
        code = """
print("Hello World")
"""
        self.run_code(code)
        self.assertEqual(self.output_buffer, ["Hello World"])

    def test_print_multiple_args(self):
        code = """
print("Value:", 10)
"""
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

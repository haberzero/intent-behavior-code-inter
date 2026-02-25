import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from utils.interpreter.interpreter import Interpreter
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.exception_types import InterpreterError, SemanticError
from typedef.diagnostic_types import CompilerError
from app.services.stdlib_provider import get_stdlib_metadata

class TestTypePromotion(unittest.TestCase):
    def setUp(self):
        self.host_interface = get_stdlib_metadata()

    def run_code(self, code):
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker, host_interface=self.host_interface)
        module = parser.parse()
        
        analyzer = SemanticAnalyzer(issue_tracker, host_interface=self.host_interface)
        analyzer.analyze(module)
        
        interpreter = Interpreter(issue_tracker, host_interface=self.host_interface)
        return interpreter.interpret(module), interpreter

    def test_valid_numeric_promotion(self):
        # int + float -> float
        code = """
int a = 10
float b = 5.5
float c = a + b
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("c"), 15.5)

    def test_invalid_string_numeric_addition(self):
        # int + str -> Error
        code = """
int a = 10
str b = "5"
var c = a + b
"""
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        msg = cm.exception.diagnostics[0].message
        self.assertIn("Binary operator '+' not supported for types 'int' and 'str'", msg)

    def test_valid_string_concatenation(self):
        code = """
str a = "hello "
str b = "world"
str c = a + b
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("c"), "hello world")

    def test_invalid_string_subtraction(self):
        code = """
str a = "hello"
str b = "h"
var c = a - b
"""
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        msg = cm.exception.diagnostics[0].message
        self.assertIn("Binary operator '-' not supported for types 'str' and 'str'", msg)

    def test_numeric_comparison_promotion(self):
        code = """
int a = 10
float b = 5.5
bool c = a > b
"""
        _, interp = self.run_code(code)
        self.assertTrue(interp.context.get_variable("c"))

    def test_invalid_comparison(self):
        code = """
int a = 10
str b = "10"
bool c = a == b
"""
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        msg = cm.exception.diagnostics[0].message
        self.assertIn("Comparison operator '==' not supported for types 'int' and 'str'", msg)

    def test_runtime_invalid_addition(self):
        # Using 'var' to bypass semantic check
        code = """
var a = 10
var b = "5"
var c = a + b
"""
        # Note: In our current implementation, even 'var' is inferred statically if initialized.
        # To truly test runtime, we'd need a more complex scenario, but let's just ensure 
        # that either semantic or runtime catch it.
        with self.assertRaises((CompilerError, InterpreterError)):
            self.run_code(code)

    def test_behavior_expr_runtime_dot_access(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
dict user = {"name": "Alice"}
str res = ~~Hello $user.name~~
"""
        _, interp = self.run_code(code)
        self.assertIn("Alice", interp.context.get_variable("res"))

if __name__ == '__main__':
    unittest.main()

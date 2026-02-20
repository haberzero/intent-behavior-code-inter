
import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from typedef.diagnostic_types import CompilerError

class TestSemanticErrors(unittest.TestCase):
    """
    Test error scenarios, including:
    - Multiple errors reporting
    - Cascading errors
    - Scope leakage
    - Invalid function signatures
    - Unsupported operations
    """

    def setUp(self):
        self.analyzer = SemanticAnalyzer()

    def analyze_code(self, code):
        dedented_code = textwrap.dedent(code).strip() + "\n"
        lexer = Lexer(dedented_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        module = parser.parse()
        self.analyzer.analyze(module)
        return module

    def assertSemanticErrors(self, code, expected_msgs):
        """
        Assert that parsing fails with CompilerError and contains ALL expected messages.
        """
        with self.assertRaises(CompilerError) as cm:
            self.analyze_code(code)
        
        diagnostics = cm.exception.diagnostics
        diag_msgs = [d.message for d in diagnostics]
        
        missing = []
        for expected in expected_msgs:
            found = any(expected in msg for msg in diag_msgs)
            if not found:
                missing.append(expected)
        
        if missing:
            self.fail(f"Expected errors {missing} not found in diagnostics: {diag_msgs}")

    def test_multiple_errors_collection(self):
        """Test that multiple independent errors are collected."""
        code = """
        int x = "s"
        str y = 1
        """
        self.assertSemanticErrors(code, ["Type mismatch", "Type mismatch"])

    def test_argument_count_mismatch(self):
        """Test calling function with wrong number of arguments."""
        code = """
        func add(int a, int b) -> int:
            return a + b
        add(1)
        """
        self.assertSemanticErrors(code, ["Argument count mismatch"])

    def test_argument_type_mismatch(self):
        """Test calling function with wrong argument types."""
        code = """
        func add(int a, int b) -> int:
            return a + b
        add("s", 2)
        """
        self.assertSemanticErrors(code, ["Argument 1 type mismatch"])

    def test_scope_leakage_prevention(self):
        """Test that variables defined in inner scope do not leak."""
        code = """
        func foo() -> void:
            int local_var = 1
            
        local_var = 2
        """
        self.assertSemanticErrors(code, ["Variable 'local_var' is not defined"])

    def test_return_outside_function(self):
        """Test return statement outside of any function."""
        code = """
        return 1
        """
        self.assertSemanticErrors(code, ["Return statement outside of function"])

    def test_void_function_returning_value(self):
        """Test void function attempting to return a value."""
        code = """
        func foo() -> void:
            return 1
        """
        self.assertSemanticErrors(code, ["Invalid return type: expected 'void'"])

    def test_invalid_operation_on_strict_types(self):
        """Test unsupported operations on strictly typed variables."""
        code = """
        int x = 1
        str y = "s"
        int z = x - y
        """
        self.assertSemanticErrors(code, ["Binary operator '-' not supported"])

    def test_cascading_error_handling(self):
        """
        Test that an error in declaration doesn't crash the analyzer,
        and subsequent errors might be reported (or suppressed depending on strategy).
        """
        code = """
        UnknownType x = 10
        x = "s" 
        """
        # We expect "Unknown type" error.
        # If declaration fails, the symbol might not be registered, leading to "Variable 'x' is not defined".
        self.assertSemanticErrors(code, ["Unknown type"])

if __name__ == '__main__':
    unittest.main()

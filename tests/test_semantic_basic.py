
import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from utils.semantic.types import PrimitiveType, AnyType
from typedef.diagnostic_types import CompilerError

class TestSemanticBasic(unittest.TestCase):
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

    def assertSemanticError(self, code, expected_msg):
        with self.assertRaises(CompilerError) as cm:
            self.analyze_code(code)
        
        # Check if any of the diagnostics contains the expected message
        found = False
        for diag in cm.exception.diagnostics:
            if expected_msg in diag.message:
                found = True
                break
        
        if not found:
            msgs = [d.message for d in cm.exception.diagnostics]
            self.fail(f"Expected error '{expected_msg}' not found in diagnostics: {msgs}")

    def test_valid_declarations(self):
        code = """
        int x = 10
        str s = "hello"
        float f = 3.14
        var v = 100
        """
        self.analyze_code(code)
        
        # Check if symbols are defined
        sym_x = self.analyzer.scope_manager.resolve('x')
        self.assertIsNotNone(sym_x)
        if sym_x is None: self.fail()
        self.assertTrue(isinstance(sym_x.type_info, PrimitiveType))
        if sym_x.type_info is None: self.fail()
        self.assertEqual(sym_x.type_info.name, 'int')

    def test_type_mismatch(self):
        code = """
        int x = "hello"
        """
        self.assertSemanticError(code, "Type mismatch")

    def test_undefined_variable(self):
        code = """
        x = 10
        """
        self.assertSemanticError(code, "Variable 'x' is not defined")

    def test_reassignment_type_check(self):
        code = """
        int x = 10
        x = "string"
        """
        self.assertSemanticError(code, "Type mismatch")

    def test_var_reassignment(self):
        """Test that 'var' uses type inference and disallows incompatible reassignment."""
        code = """
        var x = 10
        x = "string"
        """
        # Should raise error because x is inferred as int
        self.assertSemanticError(code, "Type mismatch")

    def test_unknown_type(self):
        """Test that unknown types are reported as SemanticErrors."""
        code = """
        UnknownType x = 10
        """
        self.assertSemanticError(code, "Unknown type 'UnknownType'")

    def test_binary_op_compatibility(self):
        code = """
        int x = 10 + "string"
        """
        self.assertSemanticError(code, "Binary operator '+' not supported")

    def test_function_scope(self):
        code = """
        func add(int a, int b) -> int:
            return a + b
            
        int res = add(1, 2)
        """
        self.analyze_code(code)
        # 'a' should not be in global scope
        # The SemanticAnalyzer rebuilds scope, so we check its scope_manager.
        # After analysis, scope_manager should be back to the global scope.
        
        # Verify that 'a' is NOT resolvable in the current (global) scope.
        sym_a = self.analyzer.scope_manager.resolve('a')
        self.assertIsNone(sym_a)
        
        sym_add = self.analyzer.scope_manager.resolve('add')
        self.assertIsNotNone(sym_add)

    def test_list_type_inference(self):
        """Test generic list type inference."""
        code = """
        list[int] l = [1, 2]
        """
        self.analyze_code(code)
        sym_l = self.analyzer.scope_manager.resolve('l')
        self.assertIsNotNone(sym_l)
        if sym_l is None: self.fail()
        self.assertEqual(str(sym_l.type_info), "list[int]")

    def test_return_type_check(self):
        """Test return type validation."""
        code = """
        func foo() -> int:
            return "s"
        """
        self.assertSemanticError(code, "Invalid return type: expected 'int'")

    def test_missing_return(self):
        """Test missing return value for non-void function."""
        code = """
        func foo() -> int:
            return
        """
        self.assertSemanticError(code, "Missing return value")


    def test_builtin_functions(self):
        """Test calling built-in functions."""
        code = """
        print("Hello")
        int x = len([1, 2])
        list[int] r = range(10)
        """
        self.analyze_code(code)
        # Should pass without error

if __name__ == '__main__':
    unittest.main()

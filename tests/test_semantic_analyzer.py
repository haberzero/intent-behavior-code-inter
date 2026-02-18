import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.analyzer import SemanticAnalyzer
from utils.semantic.types import PrimitiveType
from typedef.exception_types import SemanticError
from typedef import parser_types as ast

class TestSemanticAnalyzer(unittest.TestCase):
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

    def test_valid_declarations(self):
        code = """
        int x = 10
        str s = "hello"
        float f = 3.14
        var v = 100
        """
        self.analyze_code(code)
        
        # Check if symbols are defined
        sym_x = self.analyzer.symbol_table.current_scope.resolve('x')
        self.assertIsNotNone(sym_x)
        self.assertTrue(isinstance(sym_x.type_info, PrimitiveType))
        self.assertEqual(sym_x.type_info.name, 'int')

    def test_type_mismatch(self):
        code = """
        int x = "hello"
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

    def test_undefined_variable(self):
        code = """
        x = 10
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Variable 'x' is not defined", str(cm.exception))

    def test_reassignment_type_check(self):
        code = """
        int x = 10
        x = "string"
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

    def test_builtin_protection(self):
        code = """
        print = 10
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Cannot reassign built-in symbol 'print'", str(cm.exception))

    def test_builtin_redefinition(self):
        code = """
        func print() -> void:
            pass
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Cannot redefine built-in function 'print'", str(cm.exception))

    def test_unknown_type(self):
        code = """
        UnknownType x = 10
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Unknown type 'UnknownType'", str(cm.exception))

    def test_binary_op_compatibility(self):
        code = """
        int x = 10 + "string"
        """
        with self.assertRaises(SemanticError) as cm:
            self.analyze_code(code)
        self.assertIn("Binary operator '+' not supported", str(cm.exception))

    def test_function_scope(self):
        code = """
        func add(int a, int b) -> int:
            return a + b
            
        int res = add(1, 2)
        """
        self.analyze_code(code)
        # 'a' should not be in global scope
        self.assertIsNone(self.analyzer.symbol_table.current_scope.resolve_local('a'))
        # 'add' should be in global scope
        self.assertIsNotNone(self.analyzer.symbol_table.current_scope.resolve('add'))

if __name__ == '__main__':
    unittest.main()

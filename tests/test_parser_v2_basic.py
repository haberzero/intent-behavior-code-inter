import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer_v2 import LexerV2
from utils.parser.parser_v2 import ParserV2
from typedef import parser_types as ast

class TestParserV2Basic(unittest.TestCase):
    """
    Basic functionality tests for ParserV2.
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = ParserV2(tokens)
        mod = parser.parse()
        # V2 specific: Check parser.errors manually if we expect success
        if parser.errors:
            self.fail(f"Parser errors: {parser.errors}")
        return mod

    def parse_with_errors(self, code):
        """Helper that returns (module, errors)."""
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = ParserV2(tokens)
        mod = parser.parse()
        return mod, parser.errors

    def parse_expr(self, code):
        """Helper to parse a single expression."""
        mod = self.parse(code)
        stmt = mod.body[0]
        if isinstance(stmt, ast.Assign) and stmt.value is not None:
            return stmt.value
        elif isinstance(stmt, ast.ExprStmt):
             return stmt.value
        return stmt

    def test_basic_assignment(self):
        """Test basic variable assignment."""
        source = "x = 1"
        module = self.parse(source)
        self.assertEqual(len(module.body), 1)
        stmt = module.body[0]
        assert isinstance(stmt, ast.Assign)
        assert isinstance(stmt.targets[0], ast.Name)
        self.assertEqual(stmt.targets[0].id, "x")
        assert isinstance(stmt.value, ast.Constant)
        self.assertEqual(stmt.value.value, 1.0)

    def test_variable_declaration(self):
        """Test explicit type and var declarations."""
        cases = [
            ("int x = 1", "int", "x", 1.0),
            ("var y = \"hello\"", "var", "y", "hello"),
            ("float z = 3.14", "float", "z", 3.14),
            ("list l = [1, 2]", "list", "l", None), # list is IDENTIFIER in V2
            ("int uninit", "int", "uninit", None)
        ]
        
        for code, type_name, var_name, val in cases:
            with self.subTest(code=code):
                module = self.parse(code)
                stmt = module.body[0]
                assert isinstance(stmt, ast.Assign)
                assert isinstance(stmt.targets[0], ast.Name)
                self.assertEqual(stmt.targets[0].id, var_name)
                assert isinstance(stmt.type_annotation, ast.Name)
                self.assertEqual(stmt.type_annotation.id, type_name)
                
                if val is not None:
                    assert isinstance(stmt.value, ast.Constant)
                    self.assertEqual(stmt.value.value, val)
                elif code == "int uninit":
                    self.assertIsNone(stmt.value)
                elif "list" in code:
                    self.assertIsInstance(stmt.value, ast.ListExpr)

    def test_custom_type_declaration(self):
        """Test user defined type declaration (V2 feature)."""
        # UserType is IDENTIFIER, x is IDENTIFIER. 
        # Parser V2 should recognize this as declaration via lookahead.
        code = "UserType x = 1"
        module = self.parse(code)
        stmt = module.body[0]
        assert isinstance(stmt, ast.Assign)
        self.assertEqual(stmt.targets[0].id, "x")
        self.assertEqual(stmt.type_annotation.id, "UserType")

    def test_generic_type_declaration(self):
        """Test generic type declaration (V2 feature)."""
        # List[int] x = []
        code = "List[int] x = []"
        module = self.parse(code)
        stmt = module.body[0]
        assert isinstance(stmt, ast.Assign)
        self.assertEqual(stmt.targets[0].id, "x")
        assert isinstance(stmt.type_annotation, ast.Subscript)
        self.assertEqual(stmt.type_annotation.value.id, "List")
        self.assertEqual(stmt.type_annotation.slice.id, "int")

    def test_error_reporting(self):
        """Test that errors are reported and not swallowed (V2 feature)."""
        # Invalid syntax
        code = "if x:" 
        # Missing indent/block
        mod, errors = self.parse_with_errors(code)
        self.assertTrue(len(errors) > 0)
        # We expect "Expect indent after block start" because parse_with_errors adds a newline
        self.assertIn("Expect indent after block start", str(errors[0]))

    def test_function_def(self):
        """Test function definition."""
        source = """
func add(int a, int b) -> int:
    return a + b
"""
        module = self.parse(source)
        func = module.body[0]
        assert isinstance(func, ast.FunctionDef)
        self.assertEqual(func.name, "add")

if __name__ == '__main__':
    unittest.main()

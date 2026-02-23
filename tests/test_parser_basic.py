import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.parser.symbol_table import ScopeManager
from utils.parser.scanners.pre_scanner import PreScanner
from typedef import parser_types as ast
from typedef.lexer_types import TokenType

from typedef.diagnostic_types import CompilerError

class TestParserBasic(unittest.TestCase):
    """
    Basic functionality tests for Parser.
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        try:
            mod = parser.parse()
        except CompilerError as e:
            self.fail(f"Parser failed with errors: {[d.message for d in e.diagnostics]}")
        return mod

    def parse_with_errors(self, code):
        """Helper that returns (module, errors)."""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        mod = None
        try:
            mod = parser.parse()
        except CompilerError:
            pass
        return mod, parser.issue_tracker.diagnostics

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
            ("list l = [1, 2]", "list", "l", None), # list is IDENTIFIER in Lexer, BUILTIN_TYPE in SymbolTable
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
        """Test user defined type declaration (New feature)."""
        # UserType is IDENTIFIER, x is IDENTIFIER. 
        # Parser should recognize this as declaration via lookahead.
        code = "UserType x = 1"
        module = self.parse(code)
        stmt = module.body[0]
        assert isinstance(stmt, ast.Assign)
        assert isinstance(stmt.targets[0], ast.Name)
        self.assertEqual(stmt.targets[0].id, "x")
        assert isinstance(stmt.type_annotation, ast.Name)
        self.assertEqual(stmt.type_annotation.id, "UserType")

    def test_generic_type_declaration(self):
        """Test generic type declaration ( feature)."""
        # List[int] x = []
        code = "List[int] x = []"
        module = self.parse(code)
        stmt = module.body[0]
        assert isinstance(stmt, ast.Assign)
        assert isinstance(stmt.targets[0], ast.Name)
        self.assertEqual(stmt.targets[0].id, "x")
        assert isinstance(stmt.type_annotation, ast.Subscript)
        assert isinstance(stmt.type_annotation.value, ast.Name)
        self.assertEqual(stmt.type_annotation.value.id, "List")
        assert isinstance(stmt.type_annotation.slice, ast.Name)
        self.assertEqual(stmt.type_annotation.slice.id, "int")

    def test_closure_simulation(self):
        """Test basic closure structure (nested function + scope)."""
        code = """
func outer():
    int x = 10
    func inner():
        return x
"""
        mod = self.parse(code)
        outer_func = mod.body[0]
        assert isinstance(outer_func, ast.FunctionDef)
        # Inner function should be in the body
        inner_func = outer_func.body[1] # 0 is var x
        assert isinstance(inner_func, ast.FunctionDef)
        self.assertEqual(inner_func.name, "inner")
        
        # Verify x is used in inner
        ret = inner_func.body[0]
        assert isinstance(ret, ast.Return)
        assert isinstance(ret.value, ast.Name)
        self.assertEqual(ret.value.id, "x")

    def test_forward_reference_in_function(self):
        """Test forward reference of local variable (supported by pre-scanner)."""
        code = """
func test():
    x = 10
    int x = 20
"""
        # Parser should accept this because x is registered in pre-scan.
        mod = self.parse(code)
        pass

    def test_error_reporting(self):
        """Test that errors are reported and not swallowed."""
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

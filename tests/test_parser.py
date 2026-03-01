import unittest
import sys
import os
import textwrap

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.parser.symbol_table import ScopeManager, SymbolType
from core.compiler.semantic.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic.types import FunctionType, INT_TYPE
from core.types import parser_types as ast
from core.types.diagnostic_types import CompilerError, Severity
from core.support.diagnostics.codes import *
from tests.ibc_test_case import IBCTestCase

class TestParser(IBCTestCase):
    """
    Consolidated tests for Parser.
    Covers basic, complex, module-level, and error scenarios.
    """

    def parse(self, code, module_cache=None):
        """Helper to parse code into a module."""
        lexer = Lexer(code.strip() + "\n\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens, module_cache=module_cache)
        try:
            mod = parser.parse()
        except CompilerError as e:
            self.fail(f"Parser failed with errors: {[d.message for d in e.diagnostics]}")
        return mod, parser

    def parse_expr(self, code):
        """Helper to parse a single expression."""
        mod, _ = self.parse(code)
        stmt = mod.body[0]
        if isinstance(stmt, ast.Assign) and stmt.value is not None:
            return stmt.value
        elif isinstance(stmt, ast.ExprStmt):
             return stmt.value
        return stmt

    # --- Basic Parsing ---

    def test_basic_assignment(self):
        """Test basic variable assignment."""
        source = "x = 1"
        module, _ = self.parse(source)
        self.assertEqual(len(module.body), 1)
        stmt = module.body[0]
        self.assertIsInstance(stmt, ast.Assign)
        self.assertIsInstance(stmt.targets[0], ast.Name)
        self.assertEqual(stmt.targets[0].id, "x")
        self.assertIsInstance(stmt.value, ast.Constant)
        self.assertEqual(stmt.value.value, 1.0)

    def test_variable_declaration(self):
        """Test explicit type and var declarations."""
        cases = [
            ("int x = 1", "int", "x", 1.0),
            ("var y = \"hello\"", "var", "y", "hello"),
            ("float z = 3.14", "float", "z", 3.14),
            ("list l = [1, 2]", "list", "l", None),
            ("int uninit", "int", "uninit", None)
        ]
        
        for code, type_name, var_name, val in cases:
            with self.subTest(code=code):
                module, _ = self.parse(code)
                stmt = module.body[0]
                self.assertIsInstance(stmt, ast.Assign)
                self.assertIsInstance(stmt.targets[0], ast.Name)
                self.assertEqual(stmt.targets[0].id, var_name)
                self.assertIsInstance(stmt.type_annotation, ast.Name)
                self.assertEqual(stmt.type_annotation.id, type_name)
                
                if val is not None:
                    self.assertIsInstance(stmt.value, ast.Constant)
                    self.assertEqual(stmt.value.value, val)
                elif code == "int uninit":
                    self.assertIsNone(stmt.value)

    def test_generic_type_declaration(self):
        """Test generic type declaration."""
        code = "List[int] x = []"
        module, _ = self.parse(code)
        stmt = module.body[0]
        self.assertIsInstance(stmt, ast.Assign)
        self.assertIsInstance(stmt.type_annotation, ast.Subscript)
        self.assertEqual(stmt.type_annotation.value.id, "List")
        self.assertEqual(stmt.type_annotation.slice.id, "int")

    def test_function_def(self):
        """Test function definition."""
        source = """
func add(int a, int b) -> int:
    return a + b
"""
        module, _ = self.parse(source)
        func = module.body[0]
        self.assertIsInstance(func, ast.FunctionDef)
        self.assertEqual(func.name, "add")

    # --- Complex Expressions & Features ---

    def test_behavior_expression(self):
        """Test behavior description expression (@~...~)."""
        source = "res = @~process $data with prompt~"
        mod, _ = self.parse(source)
        assign = mod.body[0]
        self.assertIsInstance(assign.value, ast.BehaviorExpr)
        
        segments = assign.value.segments
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0], "process ")
        self.assertEqual(segments[1].id, "data")
        self.assertEqual(segments[2], " with prompt")

    def test_intent_comments(self):
        """Test that intent comments are correctly attached to calls."""
        code = """
@ optimize for speed
res = generate_text("prompt")
"""
        mod, _ = self.parse(code)
        stmt = mod.body[0]
        call = stmt.value
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(call.intent.strip(), "optimize for speed")

    def test_comparison_chains(self):
        """Test chained comparisons."""
        expr = self.parse_expr("res = x > 1 + 2")
        self.assertIsInstance(expr, ast.Compare)
        self.assertEqual(expr.ops[0], ">")

    def test_cast_expression(self):
        """Test type casting (type) value."""
        expr = self.parse_expr("res = (int) x")
        self.assertIsInstance(expr, ast.CastExpr)
        self.assertEqual(expr.type_name, "int")

    # --- Module & Imports ---

    def test_import_registers_symbols(self):
        """Test that import statements register symbols correctly."""
        code = "import pkg.math"
        mod, parser = self.parse(code)
        
        pkg_sym = parser.scope_manager.resolve('pkg')
        self.assertIsNotNone(pkg_sym)
        self.assertEqual(pkg_sym.type, SymbolType.MODULE)
        
        math_sym = pkg_sym.exported_scope.resolve('math')
        self.assertIsNotNone(math_sym)
        self.assertEqual(math_sym.type, SymbolType.MODULE)

    def test_cross_module_resolution(self):
        """Test resolving symbols from imported module via cache."""
        math_scope = ScopeManager().global_scope
        sqrt_sym = math_scope.define('sqrt', SymbolType.FUNCTION)
        sqrt_sym.type_info = FunctionType([INT_TYPE], INT_TYPE)
        
        module_cache = {'mock_math': math_scope}
        code = """
import mock_math
int x = mock_math.sqrt(16)
"""
        mod, parser = self.parse(code, module_cache=module_cache)
        
        math_sym = parser.scope_manager.resolve('mock_math')
        self.assertEqual(math_sym.exported_scope, math_scope)

    # --- Error Handling ---

    def test_unexpected_eof(self):
        """Test EOF handling in various contexts."""
        lexer = Lexer("func my_func(")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        with self.assertRaises(CompilerError):
            parser.parse()
        self.assertTrue(any(d.code == PAR_EXPECTED_TOKEN for d in parser.issue_tracker.diagnostics))

    def test_intent_comment_warning(self):
        """Test warning when intent comment is unused."""
        code = """
@ unused intent
x = 1
"""
        # We don't fail on warnings, but we check if they exist
        mod, parser = self.parse(code)
        warnings = [d for d in parser.issue_tracker.diagnostics if d.severity == Severity.WARNING]
        self.assertTrue(any("Intent comment" in d.message for d in warnings))

if __name__ == '__main__':
    unittest.main()

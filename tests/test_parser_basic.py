import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from typedef import parser_types as ast

class TestParserBasic(unittest.TestCase):
    """
    Basic functionality tests for Parser.
    Covers:
    1. Basic Statements (Assign, Func, If, For)
    2. Expressions (Math, Logic, Comparison)
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        mod = parser.parse()
        if parser.errors:
            # For basic tests, errors are unexpected
            self.fail(f"Parser errors: {parser.errors}")
        return mod

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
        self.assertIsInstance(stmt.value, ast.Constant)
        assert isinstance(stmt.value, ast.Constant)
        self.assertEqual(stmt.value.value, 1.0)
        self.assertEqual(stmt.lineno, 1)

    def test_variable_declaration(self):
        """Test explicit type and var declarations."""
        cases = [
            ("int x = 1", "int", "x", 1.0),
            ("var y = \"hello\"", "var", "y", "hello"),
            ("float z = 3.14", "float", "z", 3.14),
            ("list l = [1, 2]", "list", "l", None), # Value is ListExpr
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
        self.assertEqual(len(func.args), 2)
        self.assertEqual(func.args[0].arg, "a")
        assert isinstance(func.args[0].annotation, ast.Name)
        self.assertEqual(func.args[0].annotation.id, "int")
        self.assertEqual(func.args[1].arg, "b")
        assert isinstance(func.args[1].annotation, ast.Name)
        self.assertEqual(func.args[1].annotation.id, "int")
        self.assertIsInstance(func.body[0], ast.Return)

    def test_if_statement(self):
        """Test if-else statement."""
        source = """
if x > 10:
    print(x)
else:
    print(0)
"""
        module = self.parse(source)
        if_stmt = module.body[0]
        assert isinstance(if_stmt, ast.If)
        self.assertIsInstance(if_stmt.test, ast.Compare)
        self.assertEqual(len(if_stmt.body), 1)
        self.assertEqual(len(if_stmt.orelse), 1)

    def test_for_loops(self):
        """Test various for loop patterns."""
        # Case 1: for 10
        code1 = """
for 10:
    pass
"""
        mod1 = self.parse(code1)
        stmt1 = mod1.body[0]
        assert isinstance(stmt1, ast.For)
        assert isinstance(stmt1.iter, ast.Constant)
        self.assertEqual(stmt1.iter.value, 10.0)

        # Case 2: for behavior
        code2 = """
for ~~wait~~:
    pass
"""
        mod2 = self.parse(code2)
        stmt2 = mod2.body[0]
        assert isinstance(stmt2, ast.For)
        self.assertIsInstance(stmt2.iter, ast.BehaviorExpr)

        # Case 3: for i in list
        code3 = """
for i in items:
    pass
"""
        mod3 = self.parse(code3)
        stmt3 = mod3.body[0]
        assert isinstance(stmt3, ast.For)
        assert isinstance(stmt3.target, ast.Name)
        assert isinstance(stmt3.iter, ast.Name)
        self.assertEqual(stmt3.target.id, "i")
        self.assertEqual(stmt3.iter.id, "items")

    def test_math_precedence(self):
        """Test arithmetic operator precedence."""
        # 1 + 2 * 3 -> 1 + (2 * 3)
        expr = self.parse_expr("res = 1 + 2 * 3")
        assert isinstance(expr, ast.BinOp)
        self.assertEqual(expr.op, "+")
        assert isinstance(expr.right, ast.BinOp)
        self.assertEqual(expr.right.op, "*")

        # (1 + 2) * 3
        expr = self.parse_expr("res = (1 + 2) * 3")
        assert isinstance(expr, ast.BinOp)
        self.assertEqual(expr.op, "*")
        assert isinstance(expr.left, ast.BinOp)
        self.assertEqual(expr.left.op, "+")

    def test_compound_assignment(self):
        """Test +=, -=, etc."""
        cases = [("x += 1", "+"), ("x -= 1", "-"), ("x *= 1", "*"), ("x /= 1", "/")]
        for code, op in cases:
            stmt = self.parse(code).body[0]
            assert isinstance(stmt, ast.AugAssign)
            self.assertEqual(stmt.op, op)

if __name__ == '__main__':
    unittest.main()

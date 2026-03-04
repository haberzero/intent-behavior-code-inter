
import unittest
import textwrap
from core.types import parser_types as ast
from core.runtime.interpreter.interpreter import Interpreter
from core.support.diagnostics.issue_tracker import IssueTracker
from core.compiler.parser.parser import Parser
from core.compiler.lexer.lexer import Lexer
from core.types.exception_types import InterpreterError

class TestEvaluatorRefactor(unittest.TestCase):
    def setUp(self):
        self.issue_tracker = IssueTracker()
        self.interpreter = Interpreter(self.issue_tracker)

    def parse_code(self, code: str) -> ast.Module:
        code = textwrap.dedent(code).strip() + "\n"
        lexer = Lexer(code, self.issue_tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, self.issue_tracker)
        try:
            return parser.parse()
        except Exception:
            for diag in self.issue_tracker.diagnostics:
                print(f"Error: {diag.message} at line {diag.location.line if diag.location else '?'}")
            raise

    def run_code(self, code: str):
        module = self.parse_code(code)
        return self.interpreter.execute_module(module)

    def test_basic_eval(self):
        """Test basic expression evaluation (handled by Evaluator directly)"""
        code = "x = 1 + 2 * 3"
        self.run_code(code)
        x = self.interpreter.context.get_variable("x")
        self.assertEqual(x, 7)

    def test_call_delegation(self):
        """Test Evaluator delegation to Interpreter for Call nodes"""
        code = """
        func add(int a, int b):
            return a + b
            
        x = 10 + add(5, 5)
        """
        self.run_code(code)
        x = self.interpreter.context.get_variable("x")
        self.assertEqual(x, 20)

    def test_nested_call(self):
        """Test nested calls within expressions"""
        code = """
        func double(int n):
            return n * 2
            
        x = double(double(5)) + 1
        """
        self.run_code(code)
        x = self.interpreter.context.get_variable("x")
        self.assertEqual(x, 21)

    def test_unknown_node_error(self):
        """Test that unknown nodes raise InterpreterError"""
        # We can't easily parse an unknown node, so we mock one
        class UnknownNode(ast.ASTNode):
            pass
            
        unknown = UnknownNode()
        with self.assertRaises(InterpreterError) as cm:
            self.interpreter.evaluator.evaluate_expr(unknown, self.interpreter.context)
        
        self.assertIn("No evaluation logic implemented for UnknownNode", str(cm.exception))

if __name__ == "__main__":
    unittest.main()


import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic.types import INT_TYPE
from core.types.diagnostic_types import CompilerError
from core.engine import IBCIEngine

class TestBitwiseOps(unittest.TestCase):
    def setUp(self):
        self.analyzer = SemanticAnalyzer()
        self.engine = IBCIEngine()

    def analyze_code(self, code):
        dedented_code = textwrap.dedent(code).strip() + "\n"
        lexer = Lexer(dedented_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        module = parser.parse()
        # Ensure a fresh analyzer for each call to avoid error accumulation
        analyzer = SemanticAnalyzer()
        analyzer.analyze(module)
        return module

    def run_code(self, code):
        test_file = "tmp_bitwise_test.ibci"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
        
        try:
            success = self.engine.run(test_file)
            if not success:
                self.fail(f"Execution failed with errors: {[d.message for d in self.engine.scheduler.issue_tracker.diagnostics]}")
            return self.engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    # --- Semantic Tests ---

    def test_semantic_bitwise_valid(self):
        """Test that bitwise operators are valid for int."""
        code = """
        int a = 10
        int b = 3
        int r1 = a & b
        int r2 = a | b
        int r3 = a ^ b
        int r4 = a << 1
        int r5 = a >> 1
        int r6 = ~a
        """
        self.analyze_code(code)
        # Should pass

    def test_semantic_bitwise_invalid_float(self):
        """Test that bitwise operators are invalid for float."""
        operators = ['&', '|', '^', '<<', '>>']
        for op in operators:
            code = f"""
            float a = 10.5
            int b = 3
            int r = a {op} b
            """
            with self.subTest(op=op):
                with self.assertRaises(CompilerError) as cm:
                    self.analyze_code(code)
                self.assertIn(f"Binary operator '{op}' not supported for types 'float' and 'int'", cm.exception.diagnostics[0].message)

    def test_semantic_unary_bitwise_invalid_float(self):
        """Test that unary bitwise NOT is invalid for float."""
        code = """
        float a = 10.5
        int r = ~a
        """
        with self.assertRaises(CompilerError) as cm:
            self.analyze_code(code)
        self.assertIn("Unary operator '~' not supported for type 'float'", cm.exception.diagnostics[0].message)

    # --- Interpreter Tests ---

    def test_interpreter_bitwise_and(self):
        code = "int r = 10 & 3"
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r"), 2)

    def test_interpreter_bitwise_or(self):
        code = "int r = 10 | 3"
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r"), 11)

    def test_interpreter_bitwise_xor(self):
        code = "int r = 10 ^ 3"
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r"), 9)

    def test_interpreter_bitwise_lshift(self):
        code = "int r = 10 << 2"
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r"), 40)

    def test_interpreter_bitwise_rshift(self):
        code = "int r = 10 >> 1"
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r"), 5)

    def test_interpreter_bitwise_not(self):
        code = "int r = ~10"
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r"), -11)

    def test_interpreter_bitwise_complex(self):
        code = """
        int a = 10
        int b = 3
        int c = 5
        int r = (a & b) | (c ^ 1)
        """
        interp = self.run_code(code)
        # (10 & 3) = 2
        # (5 ^ 1) = 4
        # 2 | 4 = 6
        self.assertEqual(interp.context.get_variable("r"), 6)

if __name__ == '__main__':
    unittest.main()

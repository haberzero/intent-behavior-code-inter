import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic.types import PrimitiveType, AnyType, ListType
from core.types.diagnostic_types import CompilerError, Severity

class TestSemantic(unittest.TestCase):
    """
    Consolidated tests for Semantic Analyzer.
    Covers basic, complex, and error scenarios.
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

    def assertSemanticError(self, code, expected_msg):
        with self.assertRaises(CompilerError) as cm:
            self.analyze_code(code)
        
        found = any(expected_msg in d.message for d in cm.exception.diagnostics)
        if not found:
            msgs = [d.message for d in cm.exception.diagnostics]
            self.fail(f"Expected error '{expected_msg}' not found in diagnostics: {msgs}")

    # --- Basic Semantic Checks ---

    def test_valid_declarations(self):
        """Test that valid declarations are accepted and symbols registered."""
        code = """
        int x = 10
        str s = "hello"
        float f = 3.14
        var v = 100
        """
        self.analyze_code(code)
        sym_x = self.analyzer.scope_manager.resolve('x')
        self.assertIsNotNone(sym_x)
        self.assertEqual(sym_x.type_info.name, 'int')

    def test_type_mismatch(self):
        """Test type mismatch in assignment."""
        self.assertSemanticError("int x = \"hello\"", "Type mismatch")

    def test_undefined_variable(self):
        """Test usage of undefined variable."""
        self.assertSemanticError("x = 10", "Variable 'x' is not defined")

    def test_var_reassignment(self):
        """Test that 'var' uses type inference and disallows incompatible reassignment."""
        code = """
        var x = 10
        x = "string"
        """
        self.assertSemanticError(code, "Type mismatch")

    def test_binary_op_compatibility(self):
        """Test binary operator compatibility."""
        self.assertSemanticError("int x = 10 + \"string\"", "Binary operator '+' not supported")

    def test_function_scope(self):
        """Test that function parameters do not leak to global scope."""
        code = """
        func add(int a, int b) -> int:
            return a + b
        """
        self.analyze_code(code)
        self.assertIsNone(self.analyzer.scope_manager.resolve('a'))
        self.assertIsNotNone(self.analyzer.scope_manager.resolve('add'))

    def test_return_type_check(self):
        """Test return type validation."""
        code = """
        func foo() -> int:
            return "s"
        """
        self.assertSemanticError(code, "Invalid return type: expected 'int'")

    # --- Complex Scenarios ---

    def test_nested_function_scope(self):
        """Test nested function access to outer variables."""
        code = """
        func outer() -> int:
            int x = 10
            func inner() -> int:
                return x + 1
            return inner()
        """
        self.analyze_code(code)

    def test_list_inference(self):
        """Test list type inference and mixed lists."""
        code1 = "list[int] l = [1, 2]"
        self.analyze_code(code1)
        
        code2 = "var l = [1, \"two\"]"
        self.analyze_code(code2)
        sym = self.analyzer.scope_manager.resolve('l')
        self.assertIsInstance(sym.type_info.element_type, AnyType)

    def test_shadowing(self):
        """Test variable shadowing in nested scopes."""
        code = """
        int x = 10
        func foo() -> void:
            str x = "shadow"
            print(x)
        """
        self.analyze_code(code)

    # --- Error Scenarios ---

    def test_argument_mismatch(self):
        """Test function call argument count and type mismatch."""
        code1 = """
        func add(int a, int b) -> int:
            return a + b
        add(1)
        """
        self.assertSemanticError(code1, "Argument count mismatch")
        
        code2 = """
        func add(int a, int b) -> int:
            return a + b
        add("s", 2)
        """
        self.assertSemanticError(code2, "Argument 1 type mismatch")

    def test_behavior_expr_variable_check(self):
        """Test undefined variable in behavior expression and LLM prompt."""
        self.assertSemanticError("str res = @~analyze $x~", "Variable 'x' used in behavior expression is not defined")
        
        code = """
        llm analyze(str text):
        __user__
        analyze $__undefined__
        llmend
        """
        self.assertSemanticError(code, "Parameter 'undefined' used in LLM prompt is not defined")

    def test_prototype_limit_hint(self):
        """Test that nested generics trigger a prototype limit hint."""
        code = "list[list[int]] nested = [[1]]"
        self.analyze_code(code)
        has_hint = any(d.severity == Severity.HINT and d.code == "PROTO_LIMIT" 
                       for d in self.analyzer.issue_tracker.diagnostics)
        self.assertTrue(has_hint)

if __name__ == '__main__':
    unittest.main()

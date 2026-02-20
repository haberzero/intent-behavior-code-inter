
import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from utils.semantic.types import PrimitiveType, AnyType, ListType, DictType
from typedef.diagnostic_types import CompilerError

class TestSemanticComplex(unittest.TestCase):
    """
    Complex semantic analysis scenarios:
    - Nested scopes
    - Generic types with inference
    - LLM function interactions
    - 'var' type propagation
    - Control flow (if/while) interactions
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

    def test_nested_function_scope_visibility(self):
        """Test that inner functions can access outer variables with correct types."""
        code = """
        func outer() -> int:
            int x = 10
            func inner() -> int:
                return x + 1
            return inner()
        """
        self.analyze_code(code)
        # No errors means x was resolved correctly in inner scope

    def test_var_propagation_and_usage(self):
        """Test that 'var' type allows operations and passes through functions."""
        # Use 'int' for the function parameter as 'var' might not be allowed in signatures.
        code = """
        func process(int data) -> int:
            return data + 1

        var x = 10
        # 'var x' is Any, so passing it to 'int' parameter is allowed (optimistic).
        var y = process(x)
        # 'var y' means y is Any, even though process returns int.
        y = "now a string"
        """
        self.analyze_code(code)

    def test_list_of_lists_inference(self):
        """Test inference for nested lists."""
        code = """
        list[list[int]] matrix = [[1, 2], [3, 4]]
        """
        self.analyze_code(code)
        
        sym = self.analyzer.scope_manager.resolve('matrix')
        self.assertIsNotNone(sym)
        if sym is None: self.fail()
        # Expected: list[list[int]]
        self.assertTrue(str(sym.type_info).startswith("list[list[int]]"))

    def test_llm_function_call_types(self):
        """Test calling LLM functions and using their string return."""
        code = """
        llm translator(str text) -> str:
            __sys__
            Translate
            __user__
            $text
            llmend

        str result = translator("Hello")
        int len_res = len(result)
        """
        self.analyze_code(code)

    def test_mixed_list_inference(self):
        """Test that mixed lists degrade to list[Any]."""
        code = """
        var l = [1, "two", 3.0]
        """
        self.analyze_code(code)
        sym = self.analyzer.scope_manager.resolve('l')
        self.assertIsNotNone(sym)
        if sym is None: self.fail()
        # 'var' declaration sets type to AnyType.
        self.assertIsInstance(sym.type_info, AnyType)

    def test_shadowing_variables(self):
        """Test variable shadowing in nested scopes."""
        code = """
        int x = 10
        func foo() -> void:
            str x = "shadow"
            print(x) # Should resolve to str x
        """
        self.analyze_code(code)
        # If shadowing wasn't working, redefinition might error or type check might fail
        # (e.g. if it resolved to outer int x)

    def test_chained_function_calls(self):
        """Test type checking through a chain of calls."""
        code = """
        func a() -> int:
            return 1
        func b(int val) -> str:
            return "s"
        func c(str s) -> void:
            print(s)

        c(b(a()))
        """
        self.analyze_code(code)

    def test_complex_assignment_chain(self):
        """Test assigning result of complex expression."""
        code = """
        int x = 1
        int y = 2
        int z = (x + y) * 3
        """
        self.analyze_code(code)
        sym = self.analyzer.scope_manager.resolve('z')
        assert sym is not None
        if sym is None: self.fail()
        assert sym.type_info is not None
        self.assertEqual(sym.type_info.name, 'int')

if __name__ == '__main__':
    unittest.main()

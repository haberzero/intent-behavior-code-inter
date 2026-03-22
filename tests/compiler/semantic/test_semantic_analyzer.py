import unittest
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.kernel.factory import create_default_registry
from core.kernel import ast as ast

class TestSemanticAnalyzer(unittest.TestCase):

    def _analyze(self, source: str):
        tracker = IssueTracker()
        registry = create_default_registry()
        lexer = Lexer(source, tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, tracker)
        module = parser.parse()
        analyzer = SemanticAnalyzer(issue_tracker=tracker, registry=registry)
        result = analyzer.analyze(module, raise_on_error=False)
        return result.module_ast, tracker, analyzer, result

    def test_analyze_empty_module(self):
        result, tracker, analyzer, compilation = self._analyze("")
        self.assertIsInstance(result, ast.IbModule)
        self.assertEqual(len(result.body), 0)

    def test_analyze_simple_expression(self):
        result, tracker, analyzer, compilation = self._analyze("42")
        self.assertIsInstance(result, ast.IbModule)
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_variable_assignment(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42")
        self.assertEqual(len(result.body), 1)

    def test_analyze_function_no_params(self):
        result, tracker, analyzer, compilation = self._analyze("func test():\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_function_with_params(self):
        result, tracker, analyzer, compilation = self._analyze("func add(str a, int b):\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_function_with_return_type(self):
        result, tracker, analyzer, compilation = self._analyze("func get() -> int:\n    return 42\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_if_statement(self):
        result, tracker, analyzer, compilation = self._analyze("if True:\n    x = 1\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_while_statement(self):
        result, tracker, analyzer, compilation = self._analyze("while True:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_return_value(self):
        result, tracker, analyzer, compilation = self._analyze("func f():\n    return 42\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_class_definition(self):
        result, tracker, analyzer, compilation = self._analyze("class MyClass:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_class_with_init(self):
        result, tracker, analyzer, compilation = self._analyze("class User:\n    func __init__(str n, int a):\n        pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_list_literal(self):
        result, tracker, analyzer, compilation = self._analyze("[1, 2, 3]")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_dict_literal(self):
        result, tracker, analyzer, compilation = self._analyze('{"key": "value"}')
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_string_literal(self):
        result, tracker, analyzer, compilation = self._analyze('"hello"')
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_number_literal(self):
        result, tracker, analyzer, compilation = self._analyze("42")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_boolean_literals(self):
        result, tracker, analyzer, compilation = self._analyze("True")
        self.assertGreaterEqual(len(result.body), 1)

        result2, tracker2, analyzer2, compilation2 = self._analyze("False")
        self.assertGreaterEqual(len(result2.body), 1)

    def test_analyze_none_literal(self):
        result, tracker, analyzer, compilation = self._analyze("None")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_break_statement(self):
        result, tracker, analyzer, compilation = self._analyze("while True:\n    break\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_continue_statement(self):
        result, tracker, analyzer, compilation = self._analyze("while True:\n    continue\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_for_statement(self):
        result, tracker, analyzer, compilation = self._analyze("for x in items:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_multiple_statements(self):
        result, tracker, analyzer, compilation = self._analyze("x = 1\ny = 2\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_pass_statement(self):
        result, tracker, analyzer, compilation = self._analyze("pass")
        self.assertGreaterEqual(len(result.body), 1)

    def test_symbol_table_created(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42")
        self.assertIsNotNone(analyzer.symbol_table)

    def test_side_table_has_node_scenes(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42")
        self.assertIsNotNone(compilation.node_scenes)

    def test_side_table_has_node_types(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42")
        self.assertIsNotNone(compilation.node_to_type)

    def test_analyze_nested_functions(self):
        result, tracker, analyzer, compilation = self._analyze("func outer():\n    func inner():\n        pass\n    return inner\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_binary_operators(self):
        result, tracker, analyzer, compilation = self._analyze("1 + 2 - 3 * 4 / 5")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_comparison_operators(self):
        result, tracker, analyzer, compilation = self._analyze("x > y")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_logical_operators(self):
        result, tracker, analyzer, compilation = self._analyze("a and b or not c")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_unary_operators(self):
        result, tracker, analyzer, compilation = self._analyze("-x")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_var_ref(self):
        result, tracker, analyzer, compilation = self._analyze("$variable")
        self.assertGreaterEqual(len(result.body), 1)

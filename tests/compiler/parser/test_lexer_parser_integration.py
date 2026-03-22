import unittest
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.kernel import ast as ast

class TestLexerParserIntegration(unittest.TestCase):

    def _parse(self, source: str):
        tracker = IssueTracker()
        lexer = Lexer(source, tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, tracker)
        return parser.parse(), tracker

    def test_simple_expression(self):
        result, _ = self._parse("x + 1")
        self.assertIsInstance(result, ast.IbModule)
        self.assertGreaterEqual(len(result.body), 1)

    def test_variable_assignment(self):
        result, _ = self._parse("x = 42")
        self.assertEqual(len(result.body), 1)

    def test_function_call(self):
        result, _ = self._parse("foo()")
        self.assertGreaterEqual(len(result.body), 1)

    def test_function_definition_no_params(self):
        result, _ = self._parse("func test():\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_function_definition_with_params(self):
        result, _ = self._parse("func add(str a, int b):\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_function_with_return_type(self):
        result, _ = self._parse("func get() -> int:\n    return 42\n")
        self.assertEqual(len(result.body), 1)

    def test_if_statement(self):
        result, _ = self._parse("if True:\n    x = 1\n")
        self.assertEqual(len(result.body), 1)

    def test_while_statement(self):
        result, _ = self._parse("while True:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_return_statement(self):
        result, _ = self._parse("func f():\n    return 42\n")
        self.assertEqual(len(result.body), 1)

    def test_list_literal(self):
        result, _ = self._parse("[1, 2, 3]")
        self.assertGreaterEqual(len(result.body), 1)

    def test_dict_literal(self):
        result, _ = self._parse('{"key": "value"}')
        self.assertGreaterEqual(len(result.body), 1)

    def test_string_literal(self):
        result, _ = self._parse('"hello"')
        self.assertGreaterEqual(len(result.body), 1)

    def test_number_literal(self):
        result, _ = self._parse("42")
        self.assertGreaterEqual(len(result.body), 1)

    def test_boolean_true(self):
        result, _ = self._parse("True")
        self.assertGreaterEqual(len(result.body), 1)

    def test_boolean_false(self):
        result, _ = self._parse("False")
        self.assertGreaterEqual(len(result.body), 1)

    def test_none_literal(self):
        result, _ = self._parse("None")
        self.assertGreaterEqual(len(result.body), 1)

    def test_method_call(self):
        result, _ = self._parse("obj.method()")
        self.assertGreaterEqual(len(result.body), 1)

    def test_subscript_access(self):
        result, _ = self._parse("arr[0]")
        self.assertGreaterEqual(len(result.body), 1)

    def test_nested_expressions(self):
        result, _ = self._parse("((1 + 2) * 3)")
        self.assertGreaterEqual(len(result.body), 1)

    def test_binary_operators(self):
        result, _ = self._parse("1 + 2 - 3 * 4 / 5")
        self.assertGreaterEqual(len(result.body), 1)

    def test_comparison_operators(self):
        result, _ = self._parse("x > y")
        self.assertGreaterEqual(len(result.body), 1)

    def test_logical_operators(self):
        result, _ = self._parse("a and b or not c")
        self.assertGreaterEqual(len(result.body), 1)

    def test_unary_operators(self):
        result, _ = self._parse("-x")
        self.assertGreaterEqual(len(result.body), 1)

    def test_var_ref_in_expression(self):
        result, _ = self._parse("$variable")
        self.assertGreaterEqual(len(result.body), 1)

    def test_class_definition(self):
        result, _ = self._parse("class MyClass:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_class_with_init(self):
        result, _ = self._parse("class User:\n    func __init__(str n, int a):\n        pass\n")
        self.assertEqual(len(result.body), 1)

    def test_pass_statement(self):
        result, _ = self._parse("pass")
        self.assertGreaterEqual(len(result.body), 1)

    def test_break_statement(self):
        result, _ = self._parse("while True:\n    break\n")
        self.assertEqual(len(result.body), 1)

    def test_continue_statement(self):
        result, _ = self._parse("while True:\n    continue\n")
        self.assertEqual(len(result.body), 1)

    def test_for_statement(self):
        result, _ = self._parse("for x in items:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_multiple_statements(self):
        result, _ = self._parse("x = 1\ny = 2\n")
        self.assertEqual(len(result.body), 2)

    def test_import_statement(self):
        result, _ = self._parse("import foo")
        self.assertGreaterEqual(len(result.body), 1)

    def test_from_import_statement(self):
        result, _ = self._parse("from bar import baz")
        self.assertGreaterEqual(len(result.body), 1)

    def test_empty_module(self):
        result, _ = self._parse("")
        self.assertIsInstance(result, ast.IbModule)
        self.assertEqual(len(result.body), 0)

    def test_module_with_only_newlines(self):
        result, _ = self._parse("\n\n")
        self.assertIsInstance(result, ast.IbModule)

    def test_assignment_compound(self):
        result, _ = self._parse("x += 1")
        self.assertGreaterEqual(len(result.body), 1)

    def test_nested_functions(self):
        result, _ = self._parse("func outer():\n    func inner():\n        pass\n    return inner\n")
        self.assertEqual(len(result.body), 1)

    def test_error_collection(self):
        from core.kernel.issue import CompilerError
        tracker = IssueTracker()
        lexer = Lexer("x = ", tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, tracker)
        try:
            parser.parse()
        except CompilerError:
            pass
        self.assertGreater(len(tracker.diagnostics), 0)

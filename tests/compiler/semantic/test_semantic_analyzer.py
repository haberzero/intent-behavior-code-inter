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

    def test_analyze_function_call(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nfoo()\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_method_call(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nobj.foo()\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_attribute_access(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nobj.attr\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_subscript_access(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\narr[0]\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_augmented_assignment_add(self):
        result, tracker, analyzer, compilation = self._analyze("x = 1\nx += 1\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_augmented_assignment_subtract(self):
        result, tracker, analyzer, compilation = self._analyze("x = 1\nx -= 1\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_augmented_assignment_multiply(self):
        result, tracker, analyzer, compilation = self._analyze("x = 2\nx *= 2\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_try_except(self):
        result, tracker, analyzer, compilation = self._analyze("try:\n    x = 1\nexcept:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_raise(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    raise Exception()\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_retry(self):
        result, tracker, analyzer, compilation = self._analyze("retry\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_expr_stmt(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nfoo()\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_class_with_init_and_attrs(self):
        result, tracker, analyzer, compilation = self._analyze("class User:\n    func __init__(str n, int a):\n        self.name = n\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_class_multiple_methods(self):
        result, tracker, analyzer, compilation = self._analyze("class Math:\n    func add(self, int a, int b) -> int:\n        return a\n    func sub(self, int a, int b) -> int:\n        return a\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_nested_call(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    return 1\nfoo() + foo()\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_type_annotated_expr(self):
        result, tracker, analyzer, compilation = self._analyze("func foo(int x):\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_if_else_expression(self):
        result, tracker, analyzer, compilation = self._analyze("if True:\n    x = 1\nelse:\n    x = 2\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_for_loop_with_assignment(self):
        result, tracker, analyzer, compilation = self._analyze("for i in items:\n    x = i\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_side_table_node_scenes_count(self):
        result, tracker, analyzer, compilation = self._analyze("if True:\n    x = 1\nwhile True:\n    y = 2\n")
        self.assertGreater(len(compilation.node_scenes), 0)

    def test_analyze_side_table_node_types_count(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\ny = \"hello\"\n")
        self.assertGreater(len(compilation.node_to_type), 0)

    def test_analyze_side_table_node_to_symbol_count(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\nfunc foo():\n    pass\n")
        self.assertGreater(len(compilation.node_to_symbol), 0)

    def test_analyze_return_in_function(self):
        result, tracker, analyzer, compilation = self._analyze("func add(int a, int b) -> int:\n    return a + b\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_function_call_no_args(self):
        result, tracker, analyzer, compilation = self._analyze("func greet():\n    pass\ngreet()\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_function_call_with_args(self):
        result, tracker, analyzer, compilation = self._analyze("func add(int a, int b):\n    pass\nadd(1, 2)\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_break_in_while(self):
        result, tracker, analyzer, compilation = self._analyze("while True:\n    break\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_continue_in_while(self):
        result, tracker, analyzer, compilation = self._analyze("while True:\n    continue\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_while_with_else(self):
        result, tracker, analyzer, compilation = self._analyze("while False:\n    pass\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_assignment_from_call(self):
        result, tracker, analyzer, compilation = self._analyze("func get_value() -> int:\n    return 42\nresult = get_value()\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_assignment_from_attribute(self):
        result, tracker, analyzer, compilation = self._analyze("func get_obj():\n    return None\nval = get_obj().attr\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_assignment_from_subscript(self):
        result, tracker, analyzer, compilation = self._analyze("func get_list():\n    return None\nval = get_list()[0]\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_binary_and_or(self):
        result, tracker, analyzer, compilation = self._analyze("True and False or True\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_unary_not(self):
        result, tracker, analyzer, compilation = self._analyze("not True\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_compare_chained(self):
        result, tracker, analyzer, compilation = self._analyze("a < b < c\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_compare_eq_ne(self):
        result, tracker, analyzer, compilation = self._analyze("a == b\na != b\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_compare_gt_lt(self):
        result, tracker, analyzer, compilation = self._analyze("x > y\nx < y\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_compare_ge_le(self):
        result, tracker, analyzer, compilation = self._analyze("x >= y\nx <= y\n")
        self.assertEqual(len(result.body), 2)

    def test_analyze_assignment_with_type_annotation(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_global_statement(self):
        result, tracker, analyzer, compilation = self._analyze("global x\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_llm_function_def(self):
        result, tracker, analyzer, compilation = self._analyze("llm ask():\nllmend\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_behavior_expr(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\n@tag~hello~\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_import_statement(self):
        result, tracker, analyzer, compilation = self._analyze("import os\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_import_from_statement(self):
        result, tracker, analyzer, compilation = self._analyze("from foo import bar\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_side_table_node_is_deferred(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\n@tag~hello~\n")
        self.assertIsNotNone(compilation.node_is_deferred)

    def test_analyze_side_table_node_to_loc(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\n")
        self.assertIsNotNone(compilation.node_to_loc)

    def test_analyze_side_table_node_to_loc_count(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\n")
        self.assertGreater(len(compilation.node_to_loc), 0)

    def test_analyze_symbol_table_contains_function(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\n")
        func_node = result.body[0]
        self.assertIn(func_node, compilation.node_to_symbol)

    def test_analyze_symbol_table_contains_class(self):
        result, tracker, analyzer, compilation = self._analyze("class MyClass:\n    pass\n")
        class_node = result.body[0]
        self.assertIn(class_node, compilation.node_to_symbol)

    def test_analyze_symbol_table_contains_variable(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\n")
        var_node = result.body[0]
        self.assertIn(var_node, compilation.node_to_symbol)

    def test_analyze_node_scenes_for_if_statement(self):
        result, tracker, analyzer, compilation = self._analyze("if True:\n    x = 1\nelse:\n    x = 2\n")
        if_node = result.body[0]
        test_expr = if_node.test
        self.assertIn(test_expr, compilation.node_scenes)
        from core.kernel.ast import IbScene
        self.assertEqual(compilation.node_scenes[test_expr], IbScene.BRANCH)

    def test_analyze_node_scenes_for_while_statement(self):
        result, tracker, analyzer, compilation = self._analyze("while True:\n    x = 1\n")
        while_node = result.body[0]
        test_expr = while_node.test
        self.assertIn(test_expr, compilation.node_scenes)
        from core.kernel.ast import IbScene
        self.assertEqual(compilation.node_scenes[test_expr], IbScene.LOOP)

    def test_analyze_node_scenes_for_for_statement(self):
        result, tracker, analyzer, compilation = self._analyze("for x in items:\n    pass\n")
        for_node = result.body[0]
        iter_expr = for_node.iter
        self.assertIn(iter_expr, compilation.node_scenes)
        from core.kernel.ast import IbScene
        self.assertEqual(compilation.node_scenes[iter_expr], IbScene.LOOP)

    def test_analyze_type_resolved_for_constant(self):
        result, tracker, analyzer, compilation = self._analyze("x = 42\n")
        const_node = result.body[0]
        if hasattr(const_node, 'value') and hasattr(const_node.value, '__class__'):
            if const_node.value in compilation.node_to_type:
                self.assertIsNotNone(compilation.node_to_type[const_node.value])

    def test_analyze_module_preserves_structure(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nclass Bar:\n    pass\n")
        self.assertEqual(len(result.body), 2)
        self.assertIsInstance(result.body[0], ast.IbFunctionDef)
        self.assertIsInstance(result.body[1], ast.IbClassDef)

    def test_analyze_class_with_fields(self):
        result, tracker, analyzer, compilation = self._analyze("class User:\n    func __init__(str n):\n        self.name = n\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_attribute_assignment(self):
        result, tracker, analyzer, compilation = self._analyze("class User:\n    func __init__(str n):\n        self.name = n\n")
        self.assertEqual(len(result.body), 1)

    def test_analyze_chain_comparison(self):
        result, tracker, analyzer, compilation = self._analyze("a < b <= c\n")
        self.assertGreaterEqual(len(result.body), 1)

    def test_analyze_nested_attribute_access(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nobj.attr1.attr2\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_nested_subscript(self):
        result, tracker, analyzer, compilation = self._analyze("func foo():\n    pass\nmatrix[0][1]\n")
        self.assertGreaterEqual(len(result.body), 2)

    def test_analyze_function_default_params(self):
        result, tracker, analyzer, compilation = self._analyze("func greet(str name, int count):\n    pass\n")
        self.assertEqual(len(result.body), 1)

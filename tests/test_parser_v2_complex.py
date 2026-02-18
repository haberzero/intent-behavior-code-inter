import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer_v2 import LexerV2
from utils.parser.parser_v2 import ParserV2
from typedef import parser_types as ast
from typedef.lexer_types import TokenType

class TestParserV2Complex(unittest.TestCase):
    """
    Complex functionality tests for Parser V2.
    Covers:
    1. Advanced Features (Behavior, LLM, Intent Comments)
    2. Data Structures (List, Dict, Generics)
    3. Complex Expressions (Bitwise, Comparison Chains, Casts)
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = ParserV2(tokens)
        mod = parser.parse()
        if parser.errors:
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

    def test_list_dict_literals(self):
        """Test list and dict literal parsing."""
        mod = self.parse("l = [1, 2]")
        assign = mod.body[0]
        assert isinstance(assign, ast.Assign)
        self.assertIsInstance(assign.value, ast.ListExpr)
        
        mod = self.parse('d = {"a": 1, 2: "b"}')
        assign_d = mod.body[0]
        assert isinstance(assign_d, ast.Assign)
        d = assign_d.value
        assert isinstance(d, ast.Dict)
        self.assertEqual(len(d.keys), 2)

    def test_generics_parsing(self):
        """Test generic type annotations like List[int]."""
        code = """
func f(List[int] a, Dict[str, int] b) -> None:
    pass
"""
        mod = self.parse(code)
        func = mod.body[0]
        assert isinstance(func, ast.FunctionDef)
        
        # List[int]
        arg_a = func.args[0]
        assert isinstance(arg_a.annotation, ast.Subscript)
        assert isinstance(arg_a.annotation.value, ast.Name)
        self.assertEqual(arg_a.annotation.value.id, "List")
        assert isinstance(arg_a.annotation.slice, ast.Name)
        self.assertEqual(arg_a.annotation.slice.id, "int")
        
        # Dict[str, int]
        arg_b = func.args[1]
        assert isinstance(arg_b.annotation, ast.Subscript)
        assert isinstance(arg_b.annotation.value, ast.Name)
        self.assertEqual(arg_b.annotation.value.id, "Dict")
        # In V2, Dict[str, int] is parsed as Subscript(Dict, ListExpr([str, int]))
        # Note: The original test expected ListExpr.
        assert isinstance(arg_b.annotation.slice, ast.ListExpr)
        self.assertEqual(len(arg_b.annotation.slice.elts), 2)

    def test_behavior_expression(self):
        """Test behavior description expression."""
        source = "res = ~~process $data with prompt~~"
        mod = self.parse(source)
        assign = mod.body[0]
        assert isinstance(assign, ast.Assign)
        assert isinstance(assign.value, ast.BehaviorExpr)
        self.assertIn("$data", assign.value.variables)
        self.assertIn("process", assign.value.content)

    def test_behavior_logic(self):
        """Test logical operations with behavior descriptions."""
        code = """
if ~~ check user input ~~ and
   ~~ verify signature ~~:
    pass
"""
        mod = self.parse(code)
        if_stmt = mod.body[0]
        assert isinstance(if_stmt, ast.If)
        test_expr = if_stmt.test
        assert isinstance(test_expr, ast.BoolOp)
        self.assertEqual(test_expr.op, 'and')
        self.assertIsInstance(test_expr.values[0], ast.BehaviorExpr)
        self.assertIsInstance(test_expr.values[1], ast.BehaviorExpr)

    def test_llm_function(self):
        """Test LLM function definition."""
        source = """
llm chatbot(str user_input) -> str:
    __sys__
    You are a helpful assistant.
    __user__
    Answer this: $user_input
    llmend
"""
        mod = self.parse(source)
        llm_func = mod.body[0]
        assert isinstance(llm_func, ast.LLMFunctionDef)
        self.assertEqual(llm_func.name, "chatbot")

    def test_intent_comments(self):
        """Test runtime intent comments (@)."""
        # Case 1: Attached to LLM call
        code1 = """
@ optimize for speed
res = generate_text("prompt")
"""
        mod1 = self.parse(code1)
        stmt1 = mod1.body[0]
        assert isinstance(stmt1, ast.Assign)
        call = stmt1.value
        assert isinstance(call, ast.Call)
        assert call.intent is not None
        self.assertEqual(call.intent.strip(), "optimize for speed")

        # Case 2: Attached to Behavior
        code2 = """
@ analyze strictly
if ~~ user input is malicious ~~:
    pass
"""
        mod2 = self.parse(code2)
        stmt2 = mod2.body[0]
        assert isinstance(stmt2, ast.If)
        behavior = stmt2.test
        assert isinstance(behavior, ast.BehaviorExpr)
        assert behavior.intent is not None
        self.assertEqual(behavior.intent.strip(), "analyze strictly")

    def test_comparison_chains(self):
        """Test chained comparisons."""
        # x > 1 + 2
        expr = self.parse_expr("res = x > 1 + 2")
        assert isinstance(expr, ast.Compare)
        self.assertEqual(expr.ops[0], ">")
        self.assertIsInstance(expr.comparators[0], ast.BinOp)

        # a < b < c
        expr = self.parse_expr("res = 1 < 2 < 3")
        assert isinstance(expr, ast.Compare)
        self.assertEqual(expr.ops, ["<", "<"])
        self.assertEqual(len(expr.comparators), 2)

        # Mixed: a < b == c >= d
        expr = self.parse_expr("res = a < b == c >= d")
        assert isinstance(expr, ast.Compare)
        self.assertEqual(expr.ops, ["<", "==", ">="])

    def test_bitwise_operators(self):
        """Test bitwise operators and precedence."""
        cases = [
            ("a & b", "&"),
            ("a | b", "|"),
            ("a ^ b", "^"),
            ("a << b", "<<"),
            ("a >> b", ">>"),
            ("~a", "~") # Unary
        ]
        
        for code, op in cases:
            with self.subTest(code=code):
                mod = self.parse(f"x = {code}")
                assign = mod.body[0]
                assert isinstance(assign, ast.Assign)
                if op == "~":
                    assert isinstance(assign.value, ast.UnaryOp)
                    self.assertEqual(assign.value.op, "~")
                else:
                    assert isinstance(assign.value, ast.BinOp)
                    self.assertEqual(assign.value.op, op)

        # Precedence: & > |
        # a | b & c -> a | (b & c)
        expr = self.parse_expr("res = a | b & c")
        assert isinstance(expr, ast.BinOp)
        self.assertEqual(expr.op, "|")
        assert isinstance(expr.right, ast.BinOp)
        self.assertEqual(expr.right.op, "&")

    def test_cast_expression(self):
        """Test type casting (type) value."""
        cases = [("(int) x", "int"), ("(float) 1", "float"), ("(list) []", "list")]
        for code, type_name in cases:
            expr = self.parse_expr(f"res = {code}")
            assert isinstance(expr, ast.CastExpr)
            self.assertEqual(expr.type_name, type_name)
            
        # Precedence: (int) x + 1 -> ((int) x) + 1
        expr = self.parse_expr("res = (int) x + 1")
        assert isinstance(expr, ast.BinOp)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, ast.CastExpr)

        # Scenario 8.6: int(x)
        # In V2, this is now a valid Call expression (constructor call), not a syntax error.
        # This unifies the grammar and allows for standard constructor syntax.
        code_call = "res = int(x)"
        expr_call = self.parse_expr(code_call)
        self.assertIsInstance(expr_call, ast.Call)
        self.assertEqual(expr_call.func.id, "int")
        self.assertEqual(len(expr_call.args), 1)
        self.assertEqual(expr_call.args[0].id, "x")

    def test_behavior_precedence(self):
        """Test precedence of behavior expressions in logic."""
        code = """
if ~~A~~ or
   ~~B~~ and
   ~~C~~:
    pass
"""
        mod = self.parse(code)
        if_stmt = mod.body[0]
        assert isinstance(if_stmt, ast.If)
        test_expr = if_stmt.test
        assert isinstance(test_expr, ast.BoolOp)
        self.assertEqual(test_expr.op, 'or')
        self.assertIsInstance(test_expr.values[0], ast.BehaviorExpr)
        assert isinstance(test_expr.values[1], ast.BoolOp) # Inner AND
        self.assertEqual(test_expr.values[1].op, 'and')

    def test_behavior_as_argument_via_var(self):
        """Test using behavior expression passed to function via variable."""
        code = """
str temp = ~~user input~~
res = analyze(temp)
"""
        mod = self.parse(code)
        assign_temp = mod.body[0]
        assert isinstance(assign_temp, ast.Assign)
        self.assertIsInstance(assign_temp.value, ast.BehaviorExpr)
        call_stmt = mod.body[1]
        assert isinstance(call_stmt, ast.Assign)
        call = call_stmt.value
        assert isinstance(call, ast.Call)
        assert isinstance(call.args[0], ast.Name)
        self.assertEqual(call.args[0].id, "temp")

    def test_complex_generics(self):
        """Test deeply nested generic types."""
        code = """
func process(List[Dict[str, List[int]]] data) -> None:
    pass
"""
        mod = self.parse(code)
        func = mod.body[0]
        assert isinstance(func, ast.FunctionDef)
        arg = func.args[0]
        # List[...]
        assert isinstance(arg.annotation, ast.Subscript)
        assert isinstance(arg.annotation.value, ast.Name)
        self.assertEqual(arg.annotation.value.id, "List")
        # Dict[...]
        inner = arg.annotation.slice
        assert isinstance(inner, ast.Subscript)
        assert isinstance(inner.value, ast.Name)
        self.assertEqual(inner.value.id, "Dict")
        # [str, List[int]]
        dict_args_expr = inner.slice
        assert isinstance(dict_args_expr, ast.ListExpr)
        dict_args = dict_args_expr.elts
        
        first_arg = dict_args[0]
        assert isinstance(first_arg, ast.Name)
        self.assertEqual(first_arg.id, "str")
        # List[int]
        list_int = dict_args[1]
        assert isinstance(list_int, ast.Subscript)
        assert isinstance(list_int.value, ast.Name)
        self.assertEqual(list_int.value.id, "List")
        assert isinstance(list_int.slice, ast.Name)
        self.assertEqual(list_int.slice.id, "int")

    def test_comparison_chain_complex(self):
        """Test complex comparison chains."""
        # a < b > c <= d == e
        expr = self.parse_expr("res = a < b > c <= d == e")
        assert isinstance(expr, ast.Compare)
        self.assertEqual(expr.ops, ["<", ">", "<=", "=="])
        self.assertEqual(len(expr.comparators), 4)

    def test_bitwise_precedence_complex(self):
        """Test bitwise operator precedence mixed."""
        expr = self.parse_expr("res = a | b & c ^ d")
        assert isinstance(expr, ast.BinOp)
        self.assertEqual(expr.op, "|")
        assert isinstance(expr.right, ast.BinOp)
        self.assertEqual(expr.right.op, "^")
        assert isinstance(expr.right.left, ast.BinOp)
        self.assertEqual(expr.right.left.op, "&")

    def test_llm_function_empty_sections(self):
        """Test LLM function with empty sections."""
        code = """
llm empty(str s) -> str:
    __sys__
    __user__
    $s
    llmend
"""
        mod = self.parse(code)
        llm = mod.body[0]
        assert isinstance(llm, ast.LLMFunctionDef)
        assert llm.sys_prompt is not None
        self.assertEqual(llm.sys_prompt.value, "")
        assert llm.user_prompt is not None
        self.assertIn("$s", llm.user_prompt.value)

    def test_unicode_identifiers(self):
        """Test unicode identifiers (e.g. Chinese)."""
        code = """
str 名字 = "张三"
int 年龄 = 18
if 年龄 >= 18:
    print(名字)
"""
        mod = self.parse(code)
        assign1 = mod.body[0]
        assert isinstance(assign1, ast.Assign)
        assert isinstance(assign1.targets[0], ast.Name)
        self.assertEqual(assign1.targets[0].id, "名字")
        assign2 = mod.body[1]
        assert isinstance(assign2, ast.Assign)
        assert isinstance(assign2.targets[0], ast.Name)
        self.assertEqual(assign2.targets[0].id, "年龄")

    def test_intent_scope_nested_calls(self):
        """
        Test that intent on the outer statement is NOT attached to inner calls.
        """
        code = """
@ outer intent
x = outer(inner())
"""
        mod = self.parse(code)
        assign = mod.body[0]
        assert isinstance(assign, ast.Assign)
        outer_call = assign.value
        assert isinstance(outer_call, ast.Call)
        
        # Outer call should have intent
        if outer_call.intent is not None:
            self.assertEqual(outer_call.intent.strip(), "outer intent")
        else:
            self.fail("Outer call should have intent")
        
        # Inner call (argument) should NOT have intent
        inner_call = outer_call.args[0]
        assert isinstance(inner_call, ast.Call)
        self.assertIsNone(inner_call.intent)

    def test_behavior_escapes_complex(self):
        """Test escape sequences in behavior description (\\~\\~, \\$, \\~)."""
        code = r"str cmd = ~~查找包含 \$100 和 \~~波浪号\~~ 的文本~~"
        mod = self.parse(code)
        assign = mod.body[0]
        assert isinstance(assign, ast.Assign)
        behavior = assign.value
        
        expected_content = "查找包含 $100 和 ~~波浪号~~ 的文本"
        assert isinstance(behavior, ast.BehaviorExpr)
        self.assertEqual(behavior.content, expected_content)
        self.assertEqual(behavior.variables, [])

    def test_llm_block_tokens_no_indent(self):
        """
        Ensure NO INDENT tokens are generated inside LLM block even if indented.
        """
        code = """
llm ask():
    __sys__
    Content
    llmend
"""
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        
        # Filter out EOF
        tokens = [t for t in tokens if t.type != TokenType.EOF]
        
        colon_idx = next(i for i, t in enumerate(tokens) if t.type == TokenType.COLON)
        block_tokens = tokens[colon_idx+1:]
        token_types = [t.type for t in block_tokens]
        
        self.assertNotIn(TokenType.INDENT, token_types, "LLM Block should not contain INDENT tokens")
        
        raw_text_token = next(t for t in block_tokens if t.type == TokenType.RAW_TEXT)
        self.assertEqual(raw_text_token.value, "    Content")

    def test_intent_scope_multiple_statements(self):
        """
        Test that intent is consumed by the immediate next statement and does not bleed.
        """
        code = """
@ intent 1
x = call1()
y = call2()
"""
        mod = self.parse(code)
        
        # Statement 1
        assign1 = mod.body[0]
        assert isinstance(assign1, ast.Assign)
        call1 = assign1.value
        assert isinstance(call1, ast.Call)
        assert call1.intent is not None
        self.assertEqual(call1.intent.strip(), "intent 1")
        
        # Statement 2 (should have NO intent)
        assign2 = mod.body[1]
        assert isinstance(assign2, ast.Assign)
        call2 = assign2.value
        assert isinstance(call2, ast.Call)
        self.assertIsNone(call2.intent)

    def test_intent_does_not_attach_to_assignment_target(self):
        """
        Test that intent attaches to the CALL/Expr, not the variable name being assigned to.
        """
        code = """
@ intent
int x = my_func()
"""
        mod = self.parse(code)
        assign = mod.body[0]
        assert isinstance(assign, ast.Assign)
        # Intent is on the value (Call), not the target (Name)
        assert isinstance(assign.targets[0], ast.Name)
        assert isinstance(assign.value, ast.Call)
        assert assign.value.intent is not None
        self.assertEqual(assign.value.intent.strip(), "intent")

    def test_intent_in_return_statement(self):
        """Test intent attached to a function call inside a return statement."""
        code = """
@ intent for return
return my_func()
"""
        mod = self.parse(code)
        ret = mod.body[0]
        assert isinstance(ret, ast.Return)
        assert isinstance(ret.value, ast.Call)
        
        intent = ret.value.intent
        assert intent is not None
        self.assertEqual(intent.strip(), "intent for return")

if __name__ == '__main__':
    unittest.main()

import unittest
from core.compiler.lexer.lexer import Lexer
from core.compiler.common.tokens import TokenType
from core.compiler.diagnostics.issue_tracker import IssueTracker

class TestLexer(unittest.TestCase):

    def _tokenize(self, source: str):
        tracker = IssueTracker()
        lexer = Lexer(source, tracker)
        return lexer.tokenize(), tracker

    def test_simple_identifier(self):
        tokens, _ = self._tokenize("x")
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "x")

    def test_keyword_func(self):
        tokens, _ = self._tokenize("func")
        self.assertEqual(tokens[0].type, TokenType.FUNC)

    def test_assignment(self):
        tokens, _ = self._tokenize("x = 42")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER])

    def test_function_def(self):
        source = "func foo():\n    pass\n"
        tokens, _ = self._tokenize(source)
        types = [t.type for t in tokens]
        self.assertIn(TokenType.FUNC, types)
        self.assertIn(TokenType.INDENT, types)
        self.assertIn(TokenType.DEDENT, types)

    def test_indentation(self):
        source = "if True:\n    x = 1\n    y = 2\n"
        tokens, _ = self._tokenize(source)
        types = [t.type for t in tokens]
        self.assertEqual(types.count(TokenType.INDENT), 1)
        self.assertEqual(types.count(TokenType.DEDENT), 1)

    def test_string_literal(self):
        tokens, _ = self._tokenize('"hello"')
        self.assertEqual(tokens[0].type, TokenType.STRING)

    def test_multiline_string(self):
        source = '"line1\\nline2"'
        tokens, _ = self._tokenize(source)
        self.assertEqual(tokens[0].type, TokenType.STRING)

    def test_import_statement(self):
        tokens, _ = self._tokenize("import foo")
        self.assertEqual(tokens[0].type, TokenType.IMPORT)
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)

    def test_from_import(self):
        tokens, _ = self._tokenize("from bar import baz")
        types = [t.type for t in tokens]
        self.assertIn(TokenType.FROM, types)
        self.assertIn(TokenType.IMPORT, types)
        self.assertIn(TokenType.IDENTIFIER, types)

    def test_expression_operators(self):
        tokens, _ = self._tokenize("a + b * c")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.IDENTIFIER, TokenType.PLUS, TokenType.IDENTIFIER, TokenType.STAR, TokenType.IDENTIFIER])

    def test_comparison(self):
        tokens, _ = self._tokenize("x > y")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.IDENTIFIER, TokenType.GT, TokenType.IDENTIFIER])

    def test_logical_operators(self):
        tokens, _ = self._tokenize("a and b or not c")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.IDENTIFIER, TokenType.AND, TokenType.IDENTIFIER, TokenType.OR, TokenType.NOT, TokenType.IDENTIFIER])

    def test_parentheses_grouping(self):
        tokens, _ = self._tokenize("(a + b)")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.LPAREN, TokenType.IDENTIFIER, TokenType.PLUS, TokenType.IDENTIFIER, TokenType.RPAREN])

    def test_list_literal(self):
        tokens, _ = self._tokenize("[1, 2, 3]")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.LBRACKET, TokenType.NUMBER, TokenType.COMMA, TokenType.NUMBER, TokenType.COMMA, TokenType.NUMBER, TokenType.RBRACKET])

    def test_dict_literal(self):
        tokens, _ = self._tokenize('{"key": "value"}')
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.LBRACE, TokenType.STRING, TokenType.COLON, TokenType.STRING, TokenType.RBRACE])

    def test_behavior_block(self):
        tokens, _ = self._tokenize("@tag~hello~")
        types = [t.type for t in tokens]
        self.assertIn(TokenType.BEHAVIOR_MARKER, types)
        self.assertIn(TokenType.RAW_TEXT, types)

    def test_var_ref_in_behavior(self):
        tokens, _ = self._tokenize("@~$name~")
        types = [t.type for t in tokens]
        self.assertIn(TokenType.BEHAVIOR_MARKER, types)
        self.assertIn(TokenType.VAR_REF, types)

    def test_var_ref_standalone(self):
        tokens, _ = self._tokenize("$variable")
        self.assertEqual(tokens[0].type, TokenType.VAR_REF)

    def test_control_flow_keywords(self):
        tokens, _ = self._tokenize("if else elif for while break continue return")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertIn(TokenType.IF, types)
        self.assertIn(TokenType.ELSE, types)
        self.assertIn(TokenType.ELIF, types)
        self.assertIn(TokenType.FOR, types)
        self.assertIn(TokenType.WHILE, types)
        self.assertIn(TokenType.BREAK, types)
        self.assertIn(TokenType.CONTINUE, types)
        self.assertIn(TokenType.RETURN, types)

    def test_class_definition(self):
        tokens, _ = self._tokenize("class MyClass:\n    pass\n")
        self.assertEqual(tokens[0].type, TokenType.CLASS)

    def test_self_keyword(self):
        tokens, _ = self._tokenize("self")
        self.assertEqual(tokens[0].type, TokenType.SELF)

    def test_none_literal(self):
        tokens, _ = self._tokenize("None")
        self.assertEqual(tokens[0].type, TokenType.NONE)

    def test_boolean_literals(self):
        tokens, _ = self._tokenize("True False")
        self.assertEqual(tokens[0].type, TokenType.TRUE)
        self.assertEqual(tokens[1].type, TokenType.FALSE)

    def test_comment_ignored(self):
        tokens, _ = self._tokenize("x # this is a comment")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].type, TokenType.EOF)

    def test_empty_source(self):
        tokens, _ = self._tokenize("")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.EOF)

    def test_eof_token_at_end(self):
        tokens, _ = self._tokenize("x")
        self.assertEqual(tokens[-1].type, TokenType.EOF)

    def test_arrows_and_assignment(self):
        tokens, _ = self._tokenize("() -> int")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.LPAREN, TokenType.RPAREN, TokenType.ARROW, TokenType.IDENTIFIER])

    def test_subscript_access(self):
        tokens, _ = self._tokenize("arr[0]")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.IDENTIFIER, TokenType.LBRACKET, TokenType.NUMBER, TokenType.RBRACKET])

    def test_method_chain(self):
        tokens, _ = self._tokenize("obj.method()")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertIn(TokenType.DOT, types)

    def test_complex_expression(self):
        tokens, _ = self._tokenize("x = (a + b) * c - d / e")
        types = [t.type for t in tokens if t.type != TokenType.EOF and t.type != TokenType.NEWLINE]
        self.assertEqual(types, [TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.LPAREN, TokenType.IDENTIFIER, TokenType.PLUS, TokenType.IDENTIFIER, TokenType.RPAREN, TokenType.STAR, TokenType.IDENTIFIER, TokenType.MINUS, TokenType.IDENTIFIER, TokenType.SLASH, TokenType.IDENTIFIER])

    def test_token_positions(self):
        tokens, _ = self._tokenize("abc")
        token = tokens[0]
        self.assertEqual(token.line, 1)
        self.assertEqual(token.column, 1)
        self.assertEqual(token.end_column, 4)

    def test_multiline_positions(self):
        tokens, _ = self._tokenize("a\nb")
        self.assertEqual(tokens[0].line, 1)
        for t in tokens:
            if t.type == TokenType.IDENTIFIER and t.value == "b":
                self.assertEqual(t.line, 2)

import unittest
from core.compiler.lexer.core_scanner import CoreTokenScanner
from core.compiler.lexer.str_stream import StrStream
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.common.tokens import TokenType, SubState

class TestCoreTokenScanner(unittest.TestCase):

    def _make_scanner(self, source: str) -> tuple:
        stream = StrStream(source)
        tracker = IssueTracker()
        return CoreTokenScanner(stream, tracker), stream, tracker

    def test_keywords(self):
        scanner, _, _ = self._make_scanner("func var if else return")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.FUNC, TokenType.VAR, TokenType.IF, TokenType.ELSE, TokenType.RETURN])

    def test_identifier(self):
        scanner, _, _ = self._make_scanner("myVar")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[0].value, "myVar")

    def test_number_integer(self):
        scanner, _, _ = self._make_scanner("42")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.NUMBER)
        self.assertEqual(tokens[0].value, "42")

    def test_number_float(self):
        scanner, _, _ = self._make_scanner("3.14")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.NUMBER)
        self.assertEqual(tokens[0].value, "3.14")

    def test_number_hex(self):
        scanner, _, _ = self._make_scanner("0x1F")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.NUMBER)
        self.assertEqual(tokens[0].value, "0x1F")

    def test_number_binary(self):
        scanner, _, _ = self._make_scanner("0b101")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.NUMBER)
        self.assertEqual(tokens[0].value, "0b101")

    def test_string_literal(self):
        scanner, _, _ = self._make_scanner('"hello"')
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "hello")

    def test_raw_string(self):
        scanner, _, _ = self._make_scanner('r"hello\\n"')
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.STRING)

    def test_operators(self):
        scanner, _, _ = self._make_scanner("+ - * / %")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH, TokenType.PERCENT])

    def test_comparison_operators(self):
        scanner, _, _ = self._make_scanner("== != >= <=")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.EQ, TokenType.NE, TokenType.GE, TokenType.LE])

    def test_assignment_equals(self):
        scanner, _, _ = self._make_scanner("=")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.ASSIGN)

    def test_assignment_colon(self):
        scanner, _, _ = self._make_scanner(":")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.COLON)

    def test_arrow(self):
        scanner, _, _ = self._make_scanner("->")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.ARROW)

    def test_delimiters(self):
        scanner, _, _ = self._make_scanner("( ) [ ] { } , .")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.LPAREN, TokenType.RPAREN, TokenType.LBRACKET, TokenType.RBRACKET, TokenType.LBRACE, TokenType.RBRACE, TokenType.COMMA, TokenType.DOT])

    def test_paren_level(self):
        scanner, _, _ = self._make_scanner("(()")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(scanner.paren_level, 1)

    def test_newline_token(self):
        scanner, _, _ = self._make_scanner("x\n")
        tokens, is_newline, _ = scanner.scan_line()
        self.assertTrue(is_newline)
        self.assertTrue(any(t.type == TokenType.NEWLINE for t in tokens))

    def test_sub_state_normal(self):
        scanner, _, _ = self._make_scanner("")
        self.assertEqual(scanner.sub_state, SubState.NORMAL)

    def test_push_pop_state(self):
        scanner, _, _ = self._make_scanner("")
        scanner.push_state(SubState.IN_STRING)
        self.assertEqual(scanner.sub_state, SubState.IN_STRING)
        scanner.pop_state()
        self.assertEqual(scanner.sub_state, SubState.NORMAL)

    def test_var_ref(self):
        scanner, _, _ = self._make_scanner("$x")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.VAR_REF)
        self.assertEqual(tokens[0].value, "$x")

    def test_behavior_marker(self):
        scanner, _, _ = self._make_scanner("@tag~hello~")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[1].type, TokenType.RAW_TEXT)
        self.assertEqual(tokens[2].type, TokenType.BEHAVIOR_MARKER)

    def test_intent_marker(self):
        scanner, _, _ = self._make_scanner("@+message")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.INTENT)

    def test_llm_keywords(self):
        scanner, _, _ = self._make_scanner("llm llmend llmexcept retry")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.LLM_DEF, TokenType.LLM_END, TokenType.LLM_EXCEPT, TokenType.RETRY])

    def test_boolean_literals(self):
        scanner, _, _ = self._make_scanner("True False")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.TRUE)
        self.assertEqual(tokens[1].type, TokenType.FALSE)

    def test_none_literal(self):
        scanner, _, _ = self._make_scanner("None")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].type, TokenType.NONE)

    def test_comment_skip(self):
        scanner, _, _ = self._make_scanner("x # comment")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].value, "x")

    def test_whitespace_skip(self):
        scanner, _, _ = self._make_scanner("   x")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(len(tokens), 1)

    def test_scientific_notation(self):
        scanner, _, _ = self._make_scanner("1e10 2.5e-3")
        tokens, _, _ = scanner.scan_line()
        self.assertEqual(tokens[0].value, "1e10")
        self.assertEqual(tokens[1].value, "2.5e-3")

    def test_bitwise_operators(self):
        scanner, _, _ = self._make_scanner("& | ^ ~ << >>")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.BIT_AND, TokenType.BIT_OR, TokenType.BIT_XOR, TokenType.BIT_NOT, TokenType.LSHIFT, TokenType.RSHIFT])

    def test_compound_assignment(self):
        scanner, _, _ = self._make_scanner("+= -= *= /=")
        tokens, _, _ = scanner.scan_line()
        types = [t.type for t in tokens]
        self.assertEqual(types, [TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN])

    def test_snapshot_restore(self):
        scanner, _, _ = self._make_scanner("abc")
        tokens = []
        snapshot = scanner.get_snapshot()
        scanner.scan_line()
        scanner.restore_snapshot(snapshot, tokens, 0)
        self.assertEqual(scanner.scanner.pos, 0)

    def test_try_scan_success(self):
        scanner, _, _ = self._make_scanner("$var")
        tokens = []
        result = scanner.try_scan(tokens, scanner._scan_var_ref)
        self.assertTrue(result)

    def test_try_scan_failure(self):
        scanner, _, _ = self._make_scanner("")
        tokens = []
        result = scanner.try_scan(tokens, lambda t: False)
        self.assertFalse(result)

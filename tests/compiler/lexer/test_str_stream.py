import unittest
from core.compiler.lexer.str_stream import StrStream

class TestStrStream(unittest.TestCase):

    def test_initial_state(self):
        stream = StrStream("hello")
        self.assertEqual(stream.source, "hello")
        self.assertEqual(stream.length, 5)
        self.assertEqual(stream.pos, 0)
        self.assertEqual(stream.line, 1)
        self.assertEqual(stream.col, 1)

    def test_peek(self):
        stream = StrStream("abc")
        self.assertEqual(stream.peek(), 'a')
        self.assertEqual(stream.peek(1), 'b')
        self.assertEqual(stream.peek(2), 'c')
        self.assertEqual(stream.peek(3), '\0')

    def test_advance(self):
        stream = StrStream("abc")
        self.assertEqual(stream.advance(), 'a')
        self.assertEqual(stream.pos, 1)
        self.assertEqual(stream.col, 2)

    def test_advance_newline(self):
        stream = StrStream("a\nb")
        stream.advance()
        self.assertEqual(stream.peek(), '\n')
        stream.advance()
        self.assertEqual(stream.line, 2)
        self.assertEqual(stream.col, 1)
        self.assertEqual(stream.peek(), 'b')

    def test_is_at_end(self):
        stream = StrStream("a")
        self.assertFalse(stream.is_at_end())
        stream.advance()
        self.assertTrue(stream.is_at_end())

    def test_match_success(self):
        stream = StrStream("abc")
        result = stream.match('a')
        self.assertTrue(result)
        self.assertEqual(stream.pos, 1)

    def test_match_failure(self):
        stream = StrStream("abc")
        result = stream.match('b')
        self.assertFalse(result)
        self.assertEqual(stream.pos, 0)

    def test_match_at_end(self):
        stream = StrStream("")
        result = stream.match('a')
        self.assertFalse(result)

    def test_snapshot_restore(self):
        stream = StrStream("abc")
        stream.advance()
        snap = stream.get_snapshot()
        stream.advance()
        stream.restore_snapshot(snap)
        self.assertEqual(stream.pos, 1)
        self.assertEqual(stream.line, 1)

    def test_start_token(self):
        stream = StrStream("abc")
        stream.advance()
        stream.start_token()
        self.assertEqual(stream.current_token_start_pos, 1)

    def test_create_token(self):
        from core.compiler.common.tokens import TokenType
        stream = StrStream("abc")
        stream.advance()
        stream.advance()
        token = stream.create_token(TokenType.IDENTIFIER, "ab")
        self.assertEqual(token.type, TokenType.IDENTIFIER)
        self.assertEqual(token.value, "ab")
        self.assertEqual(token.line, 1)
        self.assertEqual(token.column, 1)

    def test_create_token_with_value(self):
        from core.compiler.common.tokens import TokenType
        stream = StrStream("abc")
        token = stream.create_token(TokenType.NUMBER, "42")
        self.assertEqual(token.value, "42")

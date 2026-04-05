import unittest
from core.compiler.parser.core.token_stream import TokenStream, ParseControlFlowError
from core.compiler.common.tokens import Token, TokenType
from core.compiler.diagnostics.issue_tracker import IssueTracker

class TestTokenStream(unittest.TestCase):

    def _make_stream(self, tokens):
        return TokenStream(tokens, IssueTracker())

    def _token(self, type, value="", line=1, col=1):
        return Token(type, value, line, col)

    def test_peek(self):
        stream = self._make_stream([self._token(TokenType.IDENTIFIER, "x")])
        self.assertEqual(stream.peek().value, "x")

    def test_peek_offset(self):
        tokens = [self._token(TokenType.IDENTIFIER, "a"),
                  self._token(TokenType.NUMBER, "1"),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        self.assertEqual(stream.peek(1).value, "1")

    def test_previous(self):
        tokens = [self._token(TokenType.IDENTIFIER, "x"),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        stream.advance()
        self.assertEqual(stream.previous().value, "x")

    def test_is_at_end(self):
        tokens = [self._token(TokenType.IDENTIFIER, "x"),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        self.assertFalse(stream.is_at_end())
        stream.advance()
        self.assertTrue(stream.is_at_end())

    def test_check(self):
        tokens = [self._token(TokenType.FUNC),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        self.assertTrue(stream.check(TokenType.FUNC))
        self.assertFalse(stream.check(TokenType.AUTO))

    def test_advance(self):
        tokens = [self._token(TokenType.IDENTIFIER),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        tok = stream.advance()
        self.assertEqual(stream.current, 1)
        self.assertEqual(tok.type, TokenType.IDENTIFIER)

    def test_match_success(self):
        tokens = [self._token(TokenType.FUNC),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        result = stream.match(TokenType.FUNC, TokenType.AUTO)
        self.assertTrue(result)
        self.assertEqual(stream.current, 1)

    def test_match_failure(self):
        tokens = [self._token(TokenType.IDENTIFIER),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        result = stream.match(TokenType.FUNC)
        self.assertFalse(result)
        self.assertEqual(stream.current, 0)

    def test_consume_success(self):
        tokens = [self._token(TokenType.IMPORT),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        tok = stream.consume(TokenType.IMPORT, "Expected IMPORT")
        self.assertEqual(tok.type, TokenType.IMPORT)

    def test_consume_failure(self):
        tokens = [self._token(TokenType.IDENTIFIER),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        with self.assertRaises(ParseControlFlowError):
            stream.consume(TokenType.FUNC, "Expected FUNC")

    def test_consume_end_of_statement_newline(self):
        tokens = [self._token(TokenType.NEWLINE),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        stream.consume_end_of_statement("Expected newline")
        self.assertEqual(stream.current, 1)

    def test_consume_end_of_statement_eof(self):
        tokens = [self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        stream.consume_end_of_statement("Expected EOF")
        self.assertEqual(stream.current, 0)

    def test_get_checkpoint(self):
        tokens = [self._token(TokenType.IDENTIFIER),
                  self._token(TokenType.NUMBER),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        cp = stream.get_checkpoint()
        stream.advance()
        stream.advance()
        self.assertEqual(cp, 0)

    def test_restore_checkpoint(self):
        tokens = [self._token(TokenType.IDENTIFIER),
                  self._token(TokenType.NUMBER),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        stream.advance()
        stream.advance()
        stream.restore_checkpoint(1)
        self.assertEqual(stream.current, 1)

    def test_speculate_success(self):
        tokens = [self._token(TokenType.FUNC),
                  self._token(TokenType.IDENTIFIER, "foo"),
                  self._token(TokenType.EOF)]
        stream = self._make_stream(tokens)
        with stream.speculate() as temp:
            stream.match(TokenType.FUNC)
            stream.match(TokenType.IDENTIFIER)
        self.assertEqual(stream.current, 2)

    def test_error_records_diagnostic(self):
        tokens = [self._token(TokenType.IDENTIFIER)]
        stream = self._make_stream(tokens)
        stream.error(tokens[0], "Test error", code="TEST")
        self.assertGreater(len(stream.issue_tracker.diagnostics), 0)

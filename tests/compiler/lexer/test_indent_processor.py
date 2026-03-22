import unittest
from core.compiler.lexer.indent_processor import IndentProcessor
from core.compiler.lexer.str_stream import StrStream
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.common.tokens import TokenType

class TestIndentProcessor(unittest.TestCase):

    def _make_processor(self, source: str) -> IndentProcessor:
        return IndentProcessor(StrStream(source), IssueTracker())

    def test_indent_basic(self):
        proc = self._make_processor("    x")
        level, tokens = proc.process()
        self.assertEqual(level, 4)
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.INDENT)

    def test_no_indent(self):
        proc = self._make_processor("x")
        level, tokens = proc.process()
        self.assertEqual(level, 0)
        self.assertEqual(len(tokens), 0)

    def test_empty_line_returns_none(self):
        proc = self._make_processor("\n")
        level, tokens = proc.process()
        self.assertIsNone(level)
        self.assertEqual(len(tokens), 0)

    def test_comment_line_returns_none(self):
        proc = self._make_processor("    # comment\n")
        level, tokens = proc.process()
        self.assertIsNone(level)
        self.assertEqual(len(tokens), 0)

    def test_dedent_single_level(self):
        proc = IndentProcessor(StrStream(""), IssueTracker())
        proc.indent_stack = [0, 4]
        tokens = proc.handle_eof()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.DEDENT)
        self.assertEqual(proc.indent_stack, [0])

    def test_multiple_dedent(self):
        proc = IndentProcessor(StrStream(""), IssueTracker())
        proc.indent_stack = [8, 4, 0]
        tokens = proc.handle_eof()
        self.assertEqual(len(tokens), 2)
        for t in tokens:
            self.assertEqual(t.type, TokenType.DEDENT)

    def test_handle_eof_single_dedent(self):
        proc = IndentProcessor(StrStream(""), IssueTracker())
        proc.indent_stack = [4, 0]
        tokens = proc.handle_eof()
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.DEDENT)

    def test_tab_indent(self):
        proc = self._make_processor("\tx")
        level, tokens = proc.process()
        self.assertEqual(level, 1)

    def test_indent_stack_grows(self):
        proc = self._make_processor("        x")
        proc.process()
        self.assertEqual(proc.indent_stack, [0, 8])

    def test_indent_stack_maintained(self):
        proc = self._make_processor("")
        proc.indent_stack = [4, 4]
        level, tokens = proc.process()
        self.assertEqual(proc.indent_stack[-1], 4)

import unittest
import sys
import os
import io
from contextlib import redirect_stdout

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from typedef.exception_types import LexerError
from utils.parser.parser import Parser
from typedef.exception_types import ParserError

class TestParserErrors(unittest.TestCase):
    """
    Error handling and resilience tests for Parser.
    Covers:
    1. Syntax Errors (Malformed imports, Missing newlines)
    2. Deep Recursion Resilience
    3. Unexpected EOF
    4. Warnings (Unused intent comments)
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        mod = parser.parse()
        return mod, parser.errors

    def test_deep_recursion(self):
        """Test parser resilience against deep recursion."""
        depth = 200
        # Nested parens
        source = "(" * depth + "1" + ")" * depth
        try:
            self.parse(source)
        except RecursionError:
            # Expected behavior for recursive descent parser
            pass

        # Nested types
        source = "x: " + "List[" * depth + "int" + "]" * depth + " = []"
        try:
            mod, errors = self.parse(source)
            # This specific deep nesting might be parsed as syntactically incorrect 
            # (e.g. if it looks like a slice but isn't quite valid type syntax in parser)
            # but we just want to ensure it doesn't crash unexpectedly if not RecursionError.
        except RecursionError:
            pass

    def test_unexpected_eof(self):
        """Test EOF handling in various contexts."""
        # EOF in func
        mod, errors = self.parse("func my_func(")
        self.assertTrue(len(errors) > 0)
        # Expect type name first
        self.assertIn("Expect type name", str(errors[0]))

    def test_malformed_import(self):
        """Test malformed import."""
        mod, errors = self.parse("import")
        self.assertTrue(len(errors) > 0)

    def test_behavior_errors(self):
        """Test errors related to behavior syntax (Lexer errors caught during parse)."""
        # Note: Previous Lexer errors for comments are now allowed or handled by Parser.
        
        # Invalid continuation (e.g. extra tokens on line)
        # Lexer now tokenizes successfully, so Parser should catch the extra tokens.
        # We use '123' after behavior because 'and' is a valid operator that would extend the expression.
        mod, errors = self.parse("x = ~~ behavior ~~ 123")
        self.assertTrue(len(errors) > 0)
        self.assertIn("Expect newline", str(errors[0]))

    def test_intent_comment_warning(self):
        """Test warning when intent comment is unused."""
        code = """
@ unused intent
x = 1
"""
        f = io.StringIO()
        with redirect_stdout(f):
            self.parse(code)
        output = f.getvalue()
        self.assertIn("Warning: Intent comment", output)

    def test_missing_newline_before_block(self):
        """Test missing newline before block (e.g. for 10: pass on one line)."""
        # Note: In IBC, blocks must start on new line with indentation.
        code = "for 10: pass"
        mod, errors = self.parse(code)
        self.assertTrue(len(errors) > 0)
        self.assertIn("Expect newline", str(errors[0]))

    def test_consecutive_intent_errors(self):
        """Test consecutive intent comments error."""
        code = """
@ intent 1
@ intent 2
x = 1
"""
        mod, errors = self.parse(code)
        self.assertTrue(len(errors) > 0)
        self.assertIn("Multiple intent comments", str(errors[0]))

if __name__ == '__main__':
    unittest.main()

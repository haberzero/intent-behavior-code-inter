import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer_v2 import LexerV2
from utils.parser.parser_v2 import ParserV2

class TestParserV2Errors(unittest.TestCase):
    """
    Error handling and resilience tests for Parser V2.
    Covers:
    1. Syntax Errors (Malformed imports, Missing newlines)
    2. Deep Recursion Resilience
    3. Unexpected EOF
    4. Warnings (Unused intent comments)
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = ParserV2(tokens)
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
        source = "List[" * depth + "int" + "]" * depth + " x = []"
        try:
            mod, errors = self.parse(source)
            # This specific deep nesting might be parsed as syntactically incorrect 
            # but we just want to ensure it doesn't crash unexpectedly if not RecursionError.
        except RecursionError:
            pass

    def test_unexpected_eof(self):
        """Test EOF handling in various contexts."""
        # EOF in func
        mod, errors = self.parse("func my_func(")
        self.assertTrue(len(errors) > 0)
        # Expect type name first (for parameter) or just "Expect type name"
        self.assertTrue("Expect type name" in str(errors[0]) or "Expect parameter name" in str(errors[0]))

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
        warnings = []
        def warn_cb(msg):
            warnings.append(msg)
            
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = ParserV2(tokens, warning_callback=warn_cb)
        parser.parse()
        
        self.assertTrue(len(warnings) > 0)
        self.assertIn("Intent comment", warnings[0])

    def test_missing_newline_before_block(self):
        """Test missing newline before block (e.g. for 10: pass on one line)."""
        # Note: In IBC, blocks must start on new line with indentation.
        code = "for 10: pass"
        mod, errors = self.parse(code)
        self.assertTrue(len(errors) > 0)
        # V2 Parser synchronization might produce different errors, but should complain about block
        # Actually "Expect newline before block" or "Expect indent"
        self.assertTrue(any("Expect newline" in str(e) or "Expect indent" in str(e) for e in errors))

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

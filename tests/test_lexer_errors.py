import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from typedef.diagnostic_types import CompilerError, Severity
from utils.diagnostics.codes import *

class TestLexerErrors(unittest.TestCase):
    """
    Error handling tests for Lexer (Using Diagnostic System).
    Covers:
    1. EOF errors (strings, behaviors)
    2. Invalid escape sequences
    3. Invalid tokens
    """

    def check_error(self, code: str, expected_code: str = None, expected_msg: str = None):
        lexer = Lexer(code)
        with self.assertRaises(CompilerError) as cm:
            lexer.tokenize()
        
        # Verify diagnostics
        diags = cm.exception.diagnostics
        self.assertTrue(len(diags) > 0, "No diagnostics reported")
        
        # Check if any error matches
        found = False
        for d in diags:
            if d.severity.value >= Severity.ERROR.value:
                if expected_code and d.code != expected_code:
                    continue
                if expected_msg and expected_msg not in d.message:
                    continue
                found = True
                break
        
        if not found:
            self.fail(f"Expected error {expected_code} / '{expected_msg}' not found in diagnostics: {diags}")

    def test_eof_in_string(self):
        """Test EOF while scanning string literal."""
        code = 'str s = "hello world' # Missing closing quote
        self.check_error(code, LEX_UNTERMINATED_STRING, "Unexpected EOF while scanning string literal")

    def test_eof_in_raw_string(self):
        """Test EOF while scanning raw string literal."""
        code = 'str s = r"hello world' # Missing closing quote
        self.check_error(code, LEX_UNTERMINATED_STRING, "Unexpected EOF while scanning string literal")

    def test_eof_in_behavior(self):
        """Test EOF while scanning behavior description."""
        code = 'str res = ~~analyze this' # Missing closing ~~
        self.check_error(code, LEX_UNTERMINATED_BEHAVIOR, "Unexpected EOF while scanning behavior description")

    def test_invalid_escape_in_code(self):
        """Test invalid escape sequence in code."""
        code = r'int x = \a' # Invalid escape
        self.check_error(code, LEX_INVALID_ESCAPE, "Unexpected character '\\' or invalid escape sequence")

    def test_valid_continuation_eof(self):
        """Test backslash at EOF (should fail if not followed by newline)."""
        code = 'x = 1 + \\' 
        self.check_error(code, LEX_INVALID_ESCAPE, "Unexpected character '\\' or invalid escape sequence")

    def test_inline_examples_errors(self):
        """Test various inline code examples known to be invalid."""
        invalid_examples = {
            "invalid_behavior_multiline_unclosed": ("""
str x = ~~行为描述
    没有结束标记
""", LEX_UNTERMINATED_BEHAVIOR),
            
            "invalid_indent": ("""
func bad_indent():
    int x = 1
   int y = 2
""", PAR_INDENTATION_ERROR),
            
            "invalid_string_unclosed": ("""
str s = "hello world
print(s)
""", LEX_UNTERMINATED_STRING)
        }

        for name, (code, error_code) in invalid_examples.items():
            with self.subTest(example=name):
                self.check_error(code.strip(), error_code)

if __name__ == '__main__':
    unittest.main()

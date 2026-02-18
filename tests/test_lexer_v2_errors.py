import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer_v2 import LexerV2
from typedef.exception_types import LexerError

class TestLexerV2Errors(unittest.TestCase):
    """
    Error handling tests for Lexer V2.
    Covers:
    1. EOF errors (strings, behaviors)
    2. Invalid escape sequences
    3. Invalid tokens
    """

    def test_eof_in_string(self):
        """Test EOF while scanning string literal."""
        code = 'str s = "hello world' # Missing closing quote
        lexer = LexerV2(code)
        with self.assertRaisesRegex(LexerError, "Unexpected EOF while scanning string literal"):
            lexer.tokenize()

    def test_eof_in_raw_string(self):
        """Test EOF while scanning raw string literal."""
        code = 'str s = r"hello world' # Missing closing quote
        lexer = LexerV2(code)
        with self.assertRaisesRegex(LexerError, "Unexpected EOF while scanning string literal"):
            lexer.tokenize()

    def test_eof_in_behavior(self):
        """Test EOF while scanning behavior description."""
        code = 'str res = ~~analyze this' # Missing closing ~~
        lexer = LexerV2(code)
        with self.assertRaisesRegex(LexerError, "Unexpected EOF while scanning behavior description"):
            lexer.tokenize()

    def test_invalid_escape_in_code(self):
        """Test invalid escape sequence in code."""
        code = r'int x = \a' # Invalid escape
        lexer = LexerV2(code)
        with self.assertRaisesRegex(LexerError, "Unexpected character '\\\\' or invalid escape sequence"):
            lexer.tokenize()

    def test_valid_continuation_eof(self):
        """Test backslash at EOF (should fail if not followed by newline)."""
        code = 'x = 1 + \\' 
        lexer = LexerV2(code)
        with self.assertRaisesRegex(LexerError, "Unexpected character '\\\\' or invalid escape sequence"):
            lexer.tokenize()

    def test_inline_examples_errors(self):
        """Test various inline code examples known to be invalid."""
        invalid_examples = {
            "invalid_behavior_multiline_unclosed": ("""
str x = ~~行为描述
    没有结束标记
""", "Unexpected EOF while scanning behavior description"),
            
            "invalid_indent": ("""
func bad_indent():
    int x = 1
   int y = 2
""", "Unindent does not match"),
            
            "invalid_string_unclosed": ("""
str s = "hello world
print(s)
""", "EOL while scanning string literal")
        }

        for name, (code, error_msg) in invalid_examples.items():
            with self.subTest(example=name):
                lexer = LexerV2(code.strip())
                try:
                    lexer.tokenize()
                    self.fail(f"Should have raised LexerError for {name}")
                except LexerError as e:
                    self.assertIn(error_msg, str(e))
                except Exception as e:
                    self.fail(f"Caught unexpected Exception in {name}: {type(e).__name__}: {str(e)}")

if __name__ == '__main__':
    unittest.main()

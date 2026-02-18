import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer_v2 import LexerV2
from typedef.lexer_types import TokenType

class TestLexerV2Basic(unittest.TestCase):
    """
    Basic functionality tests for LexerV2.
    """

    def test_basic_structure(self):
        """Test basic code structure: function definition, variables, loops."""
        code = """
func 计算(int a) -> int:
    int x = 10
    for i in a:
        x = x + i
    return x
"""
        lexer = LexerV2(code.strip())
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.FUNC, TokenType.IDENTIFIER, TokenType.LPAREN, TokenType.TYPE_NAME, TokenType.IDENTIFIER, TokenType.RPAREN, TokenType.ARROW, TokenType.TYPE_NAME, TokenType.COLON, TokenType.NEWLINE,
            TokenType.INDENT,
            TokenType.TYPE_NAME, TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER, TokenType.NEWLINE,
            TokenType.FOR, TokenType.IDENTIFIER, TokenType.IN, TokenType.IDENTIFIER, TokenType.COLON, TokenType.NEWLINE,
            TokenType.INDENT,
            TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.IDENTIFIER, TokenType.PLUS, TokenType.IDENTIFIER, TokenType.NEWLINE,
            TokenType.DEDENT,
            TokenType.RETURN, TokenType.IDENTIFIER,
            TokenType.DEDENT,
            TokenType.EOF
        ]
        
        self.assertEqual([t.type for t in tokens], expected_types)

    def test_continuation_line(self):
        """Test explicit line continuation with backslash."""
        code = """
x = 1 + \\
2
"""
        lexer = LexerV2(code.strip())
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER, TokenType.PLUS, 
            TokenType.NUMBER, TokenType.EOF
        ]
        self.assertEqual([t.type for t in tokens], expected_types)

    def test_implicit_continuation(self):
        """Test implicit line continuation within parentheses."""
        code = """
x = (
    1 + 
    2
)
"""
        lexer = LexerV2(code.strip())
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.LPAREN,
            TokenType.NUMBER, TokenType.PLUS, TokenType.NUMBER,
            TokenType.RPAREN, TokenType.EOF
        ]
        self.assertEqual([t.type for t in tokens], expected_types)

    def test_container_types_as_identifiers(self):
        """Test that list and dict are now IDENTIFIERs, not TYPE_NAMEs (V2 specific)."""
        code = "list l = []"
        lexer = LexerV2(code)
        tokens = lexer.tokenize()
        
        # list -> IDENTIFIER
        # l -> IDENTIFIER
        # = -> ASSIGN
        # [ -> LBRACKET
        # ] -> RBRACKET
        expected_types = [
            TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.LBRACKET, TokenType.RBRACKET, TokenType.EOF
        ]
        self.assertEqual([t.type for t in tokens], expected_types)
        self.assertEqual(tokens[0].value, "list")

if __name__ == '__main__':
    unittest.main()

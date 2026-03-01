import unittest
import sys
import os
from typing import Optional

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compiler.lexer.lexer import Lexer
from core.types.lexer_types import TokenType
from core.types.diagnostic_types import CompilerError, Severity
from core.support.diagnostics.codes import *

class TestLexer(unittest.TestCase):
    """
    Consolidated tests for Lexer.
    Covers basic, complex, and error scenarios.
    """

    # --- Basic Functionality ---

    def test_basic_structure(self):
        """Test basic code structure: function definition, variables, loops."""
        code = """
func 计算(int a) -> int:
    int x = 10
    for i in a:
        x = x + i
    return x
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.FUNC, TokenType.IDENTIFIER, TokenType.LPAREN, TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.RPAREN, TokenType.ARROW, TokenType.IDENTIFIER, TokenType.COLON, TokenType.NEWLINE,
            TokenType.INDENT,
            TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER, TokenType.NEWLINE,
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
        lexer = Lexer(code.strip())
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
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.LPAREN,
            TokenType.NUMBER, TokenType.PLUS, TokenType.NUMBER,
            TokenType.RPAREN, TokenType.EOF
        ]
        self.assertEqual([t.type for t in tokens], expected_types)

    def test_container_types_as_identifiers(self):
        """Test that list and dict are now IDENTIFIERs."""
        code = "list l = []"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.LBRACKET, TokenType.RBRACKET, TokenType.EOF
        ]
        self.assertEqual([t.type for t in tokens], expected_types)
        self.assertEqual(tokens[0].value, "list")

    # --- Complex Scenarios ---

    def test_mixed_indentation_and_continuation(self):
        """Test mixed indentation and explicit line continuation."""
        code = """
func test():
    int x = 1 + \\
        2 + \\
        3
    
    list y = [
        "a",
        "b"
    ]
    
    if x > 0:
        return y
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        nums = [t for t in tokens if t.type == TokenType.NUMBER]
        self.assertEqual(len(nums), 4) 
        
        lbracket_idx = next(i for i, t in enumerate(tokens) if t.type == TokenType.LBRACKET)
        self.assertEqual(tokens[lbracket_idx+1].type, TokenType.STRING)

    def test_behavior_description(self):
        """Test behavior description scanning (@~...~)."""
        code = """
str res = @~分析 $content~
if @~判断 $val~:
    pass
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        # Verify first line: str res = @~分析 $content~
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[2].type, TokenType.ASSIGN)
        self.assertEqual(tokens[3].type, TokenType.BEHAVIOR_MARKER) # @~
        self.assertEqual(tokens[3].value, "@~")
        self.assertEqual(tokens[4].type, TokenType.RAW_TEXT) # 分析 
        self.assertEqual(tokens[5].type, TokenType.VAR_REF)  # $content
        self.assertEqual(tokens[6].type, TokenType.BEHAVIOR_MARKER) # ~
        self.assertEqual(tokens[6].value, "~")
        self.assertEqual(tokens[7].type, TokenType.NEWLINE)
        
        # Verify second line: if @~判断 $val~:
        self.assertEqual(tokens[8].type, TokenType.IF)
        self.assertEqual(tokens[9].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[9].value, "@~")
        self.assertEqual(tokens[10].type, TokenType.RAW_TEXT)
        self.assertEqual(tokens[11].type, TokenType.VAR_REF)
        self.assertEqual(tokens[12].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[12].value, "~")
        self.assertEqual(tokens[13].type, TokenType.COLON)

    def test_behavior_with_tag(self):
        """Test behavior description with tag (@tag~...~)."""
        code = "res = @python~ print('hello') ~"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        self.assertEqual(tokens[2].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[2].value, "@python~")
        self.assertEqual(tokens[3].type, TokenType.RAW_TEXT)
        self.assertEqual(tokens[3].value, " print('hello') ")
        self.assertEqual(tokens[4].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[4].value, "~")

    def test_llm_block(self):
        """Test LLM function definition and block scanning."""
        code = """
llm 生成(str msg):
    __sys__
    系统提示
    __user__
    用户内容 $__msg__
    llmend
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        # Verify LLM definition
        self.assertEqual(tokens[0].type, TokenType.LLM_DEF)
        colon_index = next(i for i, t in enumerate(tokens) if t.type == TokenType.COLON)
        
        # Verify LLM block internals
        sys_index = colon_index + 2 
        self.assertEqual(tokens[sys_index].type, TokenType.LLM_SYS)
        
        # System prompt content
        self.assertEqual(tokens[sys_index+1].type, TokenType.RAW_TEXT)
        self.assertEqual(tokens[sys_index+1].value.strip(), "系统提示")
        
        # __user__ section
        user_token = next(t for t in tokens if t.type == TokenType.LLM_USER)
        self.assertIsNotNone(user_token)
        
        # User content and placeholders
        param_token = next(t for t in tokens if t.type == TokenType.PARAM_PLACEHOLDER)
        self.assertEqual(param_token.value, "$__msg__")
        
        # llmend
        end_token = next(t for t in tokens if t.type == TokenType.LLM_END)
        self.assertIsNotNone(end_token)

    def test_raw_strings(self):
        """Test raw string literals (r"..." and r'...')."""
        cases = [
            (r'r"C:\Windows\System32"', r"C:\Windows\System32"),
            (r"r'raw\ntext'", r"raw\ntext"),
            (r'r"quote \" inside"', r'quote \" inside'), 
            (r'r"backslashes \\\\"', r'backslashes \\\\')
        ]
        
        for source, expected in cases:
            with self.subTest(source=source):
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                self.assertEqual(tokens[0].type, TokenType.STRING)
                self.assertEqual(tokens[0].value, expected)

    def test_number_literals(self):
        """Test enhanced number literals (hex, binary, scientific)."""
        cases = [
            ("0xFF", "0xFF"),
            ("0X1a", "0X1a"),
            ("0b101", "0b101"),
            ("0B0", "0B0"),
            ("1.23", "1.23"),
            ("1e10", "1e10"),
            ("1.5E-2", "1.5E-2"),
            ("1e+5", "1e+5")
        ]
        
        for source, expected in cases:
            with self.subTest(source=source):
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                self.assertEqual(tokens[0].type, TokenType.NUMBER)
                self.assertEqual(tokens[0].value, expected)

    def test_exception_keywords(self):
        """测试异常处理关键字"""
        code = "try except finally raise as"
        lexer = Lexer(code)
        tokens = [t.type for t in lexer.tokenize() if t.type != TokenType.EOF]
        self.assertEqual(tokens, [
            TokenType.TRY, TokenType.EXCEPT, TokenType.FINALLY, 
            TokenType.RAISE, TokenType.AS
        ])

    # --- Error Handling ---

    def check_error(self, code: str, expected_code: Optional[str] = None, expected_msg: Optional[str] = None):
        lexer = Lexer(code)
        with self.assertRaises(CompilerError) as cm:
            lexer.tokenize()
        
        diags = cm.exception.diagnostics
        self.assertTrue(len(diags) > 0, "No diagnostics reported")
        
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
        code = 'str s = "hello world' 
        self.check_error(code, LEX_UNTERMINATED_STRING, "Unexpected EOF while scanning string literal")

    def test_eof_in_behavior(self):
        """Test EOF while scanning behavior description."""
        code = 'str res = @~analyze this' 
        self.check_error(code, LEX_UNTERMINATED_BEHAVIOR, "Unexpected EOF while scanning behavior description")

    def test_invalid_escape_in_code(self):
        """Test invalid escape sequence in code."""
        code = r'int x = \a' 
        self.check_error(code, LEX_INVALID_ESCAPE, "Unexpected character '\\' or invalid escape sequence")

    def test_invalid_indent(self):
        """Test invalid indentation."""
        code = """
func bad_indent():
    int x = 1
   int y = 2
"""
        self.check_error(code.strip(), PAR_INDENTATION_ERROR)

if __name__ == '__main__':
    unittest.main()

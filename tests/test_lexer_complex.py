import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compiler.lexer.lexer import Lexer
from core.types.lexer_types import TokenType

class TestLexerComplex(unittest.TestCase):
    """
    Complex functionality tests for Lexer.
    Covers:
    1. Behavior Descriptions (~~...~~)
    2. LLM Blocks (llm, __sys__, __user__)
    3. Complex Real-world Scenarios
    4. Mixed indentation and continuations
    """

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
        """Test behavior description scanning (~~...~~)."""
        code = """
str res = ~~分析 $content~~
if ~~判断 $val~~:
    pass
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        # Verify first line: str res = ~~分析 $content~~
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[1].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[2].type, TokenType.ASSIGN)
        self.assertEqual(tokens[3].type, TokenType.BEHAVIOR_MARKER) # ~~
        self.assertEqual(tokens[4].type, TokenType.RAW_TEXT) # 分析 
        self.assertEqual(tokens[5].type, TokenType.VAR_REF)  # $content
        self.assertEqual(tokens[6].type, TokenType.BEHAVIOR_MARKER) # ~~
        self.assertEqual(tokens[7].type, TokenType.NEWLINE)
        
        # Verify second line: if ~~判断 $val~~:
        self.assertEqual(tokens[8].type, TokenType.IF)
        self.assertEqual(tokens[9].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[10].type, TokenType.RAW_TEXT)
        self.assertEqual(tokens[11].type, TokenType.VAR_REF)
        self.assertEqual(tokens[12].type, TokenType.BEHAVIOR_MARKER)
        self.assertEqual(tokens[13].type, TokenType.COLON)

    def test_behavior_no_escape(self):
        """Test that behavior descriptions treat backslashes and tildes as raw text."""
        code = """
str cmd = ~~分析 ~ 符号~~
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.IDENTIFIER, TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.BEHAVIOR_MARKER,
            TokenType.RAW_TEXT, 
            TokenType.BEHAVIOR_MARKER, TokenType.EOF
        ]
        
        self.assertEqual([t.type for t in tokens], expected_types)
        
        content_tokens = [t.value for t in tokens if t.type == TokenType.RAW_TEXT]
        content = "".join(content_tokens)
        self.assertIn("分析", content)
        self.assertIn("~", content)

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

    def test_complex_real_world_code(self):
        """Test a complex real-world code scenario mixing multiple features."""
        # Note: 'list' and 'dict' are parsed as IDENTIFIERs, not TYPE_NAMEs.
        # This test focuses on LLM and strings, so this distinction is not critical here.
        code = r"""
import utils
from models import User

llm generate_report(User user, str context):
    __sys__
    You are a data analyst.
    Current Date: $__date__
    __user__
    Please analyze user $__user_name__ with context:
    $__context__
    llmend

func process_user_data(list users) -> dict:
    dict results = {}
    
    for user in users:
        if ~~check if user $user.name is active~~:
            # Nested behavior description and complex strings
            str status = "Active: \"Yes\""
            
            # Multiline behavior description (no escapes needed)
            str analysis = ~~analyze user behavior
                with deep learning model
                using context $user.context~~
                
            # Call LLM
            str report = generate_report(user, analysis)
            
            # Complex calculation and list operations
            results[user.id] = {
                "status": status,
                "score": (int) 100 * 0.95,
                "tags": ["vip", "high-value"]
            }
        else:
            results[user.id] = None
            
    return results
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        llm_def = next(t for t in tokens if t.type == TokenType.LLM_DEF)
        self.assertEqual(llm_def.value, "llm")
        
        str_tokens = [t for t in tokens if t.type == TokenType.STRING]
        target_str = next((t for t in str_tokens if "Active" in t.value), None)
        assert target_str is not None
        self.assertEqual(target_str.value, 'Active: "Yes"') 
        
        behavior_texts = [t.value for t in tokens if t.type == TokenType.RAW_TEXT]
        combined_behavior = "".join(behavior_texts)
        self.assertIn("analyze user behavior", combined_behavior)
        self.assertIn("with deep learning model", combined_behavior)

    def test_behavior_escapes(self):
        r"""Test escape sequences in behavior description (\~\~, \$, \~)."""
        # Use space to separate \~ from ~~ to avoid ambiguity in test string parsing vs lexer logic
        code = r"str x = ~~text with \~\~ and \$ and \~ ~~"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        # Structure: TYPE IDENT ASSIGN ~~ RAW(text with ) RAW(~~) RAW( and ) RAW($) RAW( and ) RAW(~) RAW( ) ~~ EOF
        behavior_tokens = [t.value for t in tokens if t.type == TokenType.RAW_TEXT]
        combined = "".join(behavior_tokens)
        
        self.assertIn("~~", combined)
        self.assertIn("$", combined)
        self.assertIn("~", combined)
        # Expect "text with ~~ and $ and ~ "
        self.assertEqual(combined, "text with ~~ and $ and ~ ")

    def test_raw_strings(self):
        """Test raw string literals (r"..." and r'...')."""
        cases = [
            (r'r"C:\Windows\System32"', r"C:\Windows\System32"),
            (r"r'raw\ntext'", r"raw\ntext"),
            (r'r"quote \" inside"', r'quote \" inside'), # Quote is escaped but backslash remains
            (r'r"backslashes \\\\"', r'backslashes \\\\')
        ]
        
        for source, expected in cases:
            with self.subTest(source=source):
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                self.assertEqual(tokens[0].type, TokenType.STRING)
                self.assertEqual(tokens[0].value, expected)

    def test_var_ref_with_dots(self):
        """Test variable references with dot notation ($user.name.first) are now atomic tokens."""
        code = "str x = ~~hello $user.name.first world~~"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        # Expected sequence: ... RAW_TEXT("hello ") VAR_REF("$user") DOT(".") IDENTIFIER("name") DOT(".") IDENTIFIER("first") RAW_TEXT(" world") ...
        # Structure: 
        # 0: IDENTIFIER(str)
        # 1: IDENTIFIER(x)
        # 2: ASSIGN(=)
        # 3: BEHAVIOR_MARKER(~~)
        # 4: RAW_TEXT(hello )
        # 5: VAR_REF($user)
        # 6: DOT(.)
        # 7: IDENTIFIER(name)
        # 8: DOT(.)
        # 9: IDENTIFIER(first)
        # 10: RAW_TEXT( world)
        # 11: BEHAVIOR_MARKER(~~)
        # 12: NEWLINE(\n)
        # 13: EOF()

        self.assertEqual(tokens[5].type, TokenType.VAR_REF)
        self.assertEqual(tokens[5].value, "$user")
        self.assertEqual(tokens[6].type, TokenType.DOT)
        self.assertEqual(tokens[7].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[7].value, "name")
        self.assertEqual(tokens[8].type, TokenType.DOT)
        self.assertEqual(tokens[9].type, TokenType.IDENTIFIER)
        self.assertEqual(tokens[9].value, "first")
        
        # Ensure surrounding text is correct
        raw_texts = [t.value for t in tokens if t.type == TokenType.RAW_TEXT]
        self.assertEqual(raw_texts[0], "hello ")
        self.assertEqual(raw_texts[1], " world")

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
                # Should be NUMBER token
                self.assertEqual(tokens[0].type, TokenType.NUMBER)
                self.assertEqual(tokens[0].value, expected)

    def test_behavior_escape_at_end(self):
        """Test behavior description ending with escaped tilde."""
        # ~~ ... \~~ ~~
        code = r"x = ~~ content \~~ ~~"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        # Expect: IDENT, ASSIGN, BEHAVIOR_MARKER, RAW_TEXT(" content "), RAW_TEXT("~~"), RAW_TEXT(" "), BEHAVIOR_MARKER
        raw_texts = [t.value for t in tokens if t.type == TokenType.RAW_TEXT]
        combined = "".join(raw_texts)
        self.assertEqual(combined, " content ~~ ")

    def test_llm_block_inline_content(self):
        """Test LLM block with inline content after keywords."""
        code = """
llm inline_test(int a):
    __sys__ System prompt
    __user__ User prompt $__a__
    llmend
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        # Find LLM_SYS and check if "System prompt" follows immediately
        sys_idx = next(i for i, t in enumerate(tokens) if t.type == TokenType.LLM_SYS)
        self.assertEqual(tokens[sys_idx+1].type, TokenType.RAW_TEXT)
        self.assertEqual(tokens[sys_idx+1].value.strip(), "System prompt")
        
        # Find LLM_USER and check if "User prompt $__a__" follows
        user_idx = next(i for i, t in enumerate(tokens) if t.type == TokenType.LLM_USER)
        # The content might be split into multiple tokens (RAW_TEXT, PARAM, etc.).
        # Verify that the first token is RAW_TEXT starting with "User prompt".
        self.assertEqual(tokens[user_idx+1].type, TokenType.RAW_TEXT)
        self.assertIn("User prompt", tokens[user_idx+1].value)


    def test_exception_keywords(self):
        """测试新增的异常处理关键字"""
        code = "try except finally raise as"
        lexer = Lexer(code)
        tokens = [t.type for t in lexer.tokenize() if t.type != TokenType.EOF]
        self.assertEqual(tokens, [
            TokenType.TRY, TokenType.EXCEPT, TokenType.FINALLY, 
            TokenType.RAISE, TokenType.AS
        ])

if __name__ == '__main__':
    unittest.main()

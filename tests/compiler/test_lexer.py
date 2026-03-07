import unittest
from tests.compiler.base import BaseCompilerTest
from core.compiler.lexer.lexer import Lexer
from core.types.lexer_types import TokenType

class TestLexer(BaseCompilerTest):
    """
    词法分析测试：基于标准 Fixture 验证 Token 流。
    """
    def test_basics_tokens(self):
        code = self.get_fixture_content("standard/basics.ibci")
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        types = [t.type for t in tokens]
        self.assertIn(TokenType.FUNC, types)
        self.assertIn(TokenType.IDENTIFIER, types) # int, str are identifiers
        self.assertIn(TokenType.NUMBER, types) # 10, 3.14
        self.assertIn(TokenType.STRING, types) # "hello"
        
    def test_oop_tokens(self):
        code = self.get_fixture_content("standard/oop.ibci")
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        types = [t.type for t in tokens]
        self.assertIn(TokenType.CLASS, types)
        self.assertIn(TokenType.FUNC, types)
        
    def test_control_flow_tokens(self):
        code = self.get_fixture_content("standard/control_flow.ibci")
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        types = [t.type for t in tokens]
        self.assertIn(TokenType.IF, types)
        self.assertIn(TokenType.FOR, types)
        self.assertIn(TokenType.TRY, types)
        self.assertIn(TokenType.EXCEPT, types)

    def test_advanced_feature_tokens(self):
        code = self.get_fixture_content("standard/advanced_features.ibci")
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        types = [t.type for t in tokens]
        self.assertIn(TokenType.LLM_DEF, types)
        self.assertIn(TokenType.LLM_SYS, types)
        self.assertIn(TokenType.LLM_USER, types)
        self.assertIn(TokenType.LLM_END, types)
        self.assertIn(TokenType.INTENT, types)
        self.assertIn(TokenType.BEHAVIOR_MARKER, types)
        self.assertIn(TokenType.PARAM_PLACEHOLDER, types)

if __name__ == "__main__":
    unittest.main()

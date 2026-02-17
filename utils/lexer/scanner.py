from typing import List, Optional
from typedef.lexer_types import TokenType, Token

class Scanner:
    """提供字符流操作，包括位置维护、前瞻和匹配。"""
    def __init__(self, source_code: str):
        self.source = source_code
        self.length = len(source_code)
        self.pos = 0
        self.line = 1
        self.col = 1
        self.current_token_start_pos = 0
        self.current_token_start_line = 1
        self.current_token_start_col = 1
    
    def peek(self, offset: int = 0) -> str:
        """返回当前位置+偏移量的字符。"""
        if self.pos + offset >= self.length:
            return '\0'
        return self.source[self.pos + offset]

    def advance(self) -> str:
        """移动指针并返回字符，更新行列号。"""
        if self.is_at_end():
            return '\0'
            
        char = self.source[self.pos]
        self.pos += 1
        
        if char == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
            
        return char

    def match(self, expected: str) -> bool:
        """消耗并匹配预期字符。"""
        if self.is_at_end():
            return False
        if self.source[self.pos] != expected:
            return False
            
        self.advance()
        return True

    def is_at_end(self) -> bool:
        return self.pos >= self.length

    def start_token(self):
        """记录 Token 起始位置。"""
        self.current_token_start_pos = self.pos
        self.current_token_start_line = self.line
        self.current_token_start_col = self.col

    def create_token(
            self, 
            type: TokenType, 
            value: Optional[str] = None, 
            at_line_start: bool = False
        ) -> Token:
        """创建 Token 实例。"""
        if value is None:
            value = self.source[self.current_token_start_pos : self.pos]
            
        return Token(
            type=type,
            value=value,
            line=self.current_token_start_line,
            column=self.current_token_start_col,
            end_line=self.line,
            end_column=self.col,
            is_at_line_start=at_line_start
        )

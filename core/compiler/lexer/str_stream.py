from typing import List, Optional
from core.compiler.common.tokens import TokenType, Token

class StrStream:
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
        # 当前最内层未闭合构造起点 (line, col)（CoreScanner 经括号栈维护）；
        # None = 无未闭合构造。create_token 对跨行 token 附 continuation_start
        # 标记，供解析错误位置归位（卡住点跨行时归位到构造起点）。
        self.continuation_start: Optional[tuple] = None
    
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

    def get_snapshot(self) -> tuple:
        """获取当前流状态的快照。"""
        return (self.pos, self.line, self.col)

    def restore_snapshot(self, snapshot: tuple):
        """从快照恢复流状态。"""
        self.pos, self.line, self.col = snapshot

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
            
        token = Token(
            type=type,
            value=value,
            line=self.current_token_start_line,
            column=self.current_token_start_col,
            end_line=self.line,
            end_column=self.col,
            is_at_line_start=at_line_start
        )
        # 跨行续行标记：token 起点与未闭合构造起点不同行时附构造起点
        # （同行 token 不标记——错误卡住点同行时列号精确，维持现状）。
        if (
            self.continuation_start is not None
            and self.current_token_start_line > self.continuation_start[0]
        ):
            token.continuation_start = self.continuation_start
        return token

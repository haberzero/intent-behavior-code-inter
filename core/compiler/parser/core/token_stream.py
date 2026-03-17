from typing import List, Optional
from contextlib import contextmanager
from core.compiler.lexer.tokens import Token, TokenType
from core.domain import ast as ast
from core.compiler.support.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker

class ParseControlFlowError(Exception):
    """Internal exception for parser synchronization control flow."""
    pass

class TokenStream:
    """
    Manages the stream of tokens for parsing.
    Provides primitives for peeking, consuming, and matching tokens.
    """
    def __init__(self, tokens: List[Token], issue_tracker: Optional[DiagnosticReporter] = None):
        self.tokens = tokens
        self.current = 0
        self.issue_tracker = issue_tracker or IssueTracker()

    def peek(self, offset: int = 0) -> Token:
        if self.current + offset >= len(self.tokens):
            return self.tokens[-1] # EOF
        return self.tokens[self.current + offset]

    def previous(self) -> Token:
        if self.current == 0:
            return self.tokens[0]
        return self.tokens[self.current - 1]

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def check(self, type: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == type

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def consume(self, type: TokenType, message: str, code: str = "PAR_001") -> Token:
        if self.check(type):
            return self.advance()
        raise self.error(self.peek(), message, code=code)

    def consume_end_of_statement(self, message: str, code: str = "PAR_001"):
        if self.check(TokenType.NEWLINE):
            self.advance()
        elif self.is_at_end():
            return
        else:
            raise self.error(self.peek(), message, code=code)

    def match(self, *types: TokenType) -> bool:
        for type in types:
            if self.check(type):
                self.advance()
                return True
        return False

    def get_checkpoint(self) -> int:
        """[IES 2.1] 获取当前流的检查点，用于推测性解析的回滚"""
        return self.current

    def restore_checkpoint(self, checkpoint: int):
        """[IES 2.1] 回滚到指定的检查点"""
        self.current = checkpoint

    @contextmanager
    def speculate(self):
        """
        [IES 2.1] 开启推测性解析上下文。
        在此期间产生的所有错误都会被收集到一个临时的 IssueTracker 中。
        如果解析成功（未抛出 ParseControlFlowError），则合并诊断信息。
        如果解析失败，则静默丢弃，防止误报。
        """
        old_tracker = self.issue_tracker
        # 使用一个新的 IssueTracker 进行隔离
        temp_tracker = IssueTracker(file_path=old_tracker.file_path)
        self.issue_tracker = temp_tracker
        success = False
        try:
            yield temp_tracker
            success = True
        finally:
            self.issue_tracker = old_tracker
            # 仅在推测成功时合并诊断信息（包括潜在的警告）
            if success:
                old_tracker.merge(temp_tracker)

    def error(self, token: Token, message: str, code: str = "PAR_001") -> Exception:
        self.issue_tracker.error(message, token, code=code)
        return ParseControlFlowError()

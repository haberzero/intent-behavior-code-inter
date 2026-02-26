from typing import List, Optional
from core.types.lexer_types import Token, TokenType
from core.types import parser_types as ast
from core.support.diagnostics.issue_tracker import IssueTracker
from core.support.diagnostics.codes import PAR_EXPECTED_TOKEN
from core.types.diagnostic_types import Severity

class ParseControlFlowError(Exception):
    """Internal exception for parser synchronization control flow."""
    pass

class TokenStream:
    """
    Manages the stream of tokens for parsing.
    Provides primitives for peeking, consuming, and matching tokens.
    """
    def __init__(self, tokens: List[Token], issue_tracker: Optional[IssueTracker] = None):
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

    def consume(self, type: TokenType, message: str) -> Token:
        if self.check(type):
            return self.advance()
        raise self.error(self.peek(), message)

    def consume_end_of_statement(self, message: str):
        if self.check(TokenType.NEWLINE):
            self.advance()
        elif self.is_at_end():
            return
        else:
            raise self.error(self.peek(), message)

    def match(self, *types: TokenType) -> bool:
        for type in types:
            if self.check(type):
                self.advance()
                return True
        return False

    def error(self, token: Token, message: str) -> Exception:
        self.issue_tracker.report(Severity.ERROR, PAR_EXPECTED_TOKEN, message, token)
        return ParseControlFlowError()

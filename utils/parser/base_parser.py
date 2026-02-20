from typing import List, Optional
from typedef.lexer_types import Token, TokenType
from typedef import parser_types as ast
from utils.diagnostics.issue_tracker import IssueTracker
from utils.diagnostics.codes import PAR_EXPECTED_TOKEN
from typedef.diagnostic_types import Severity

class ParseControlFlowError(Exception):
    """Internal exception for parser synchronization control flow."""
    pass

class BaseParser:
    """
    Base class for Parsers and Scanners.
    Provides token consumption primitives and shared syntax parsing (e.g. imports).
    """
    def __init__(self, tokens: List[Token], issue_tracker: Optional[IssueTracker] = None):
        self.tokens = tokens
        self.current = 0
        self.issue_tracker = issue_tracker or IssueTracker()

    # --- Token Helpers ---

    def peek(self, offset: int = 0) -> Token:
        if self.current + offset >= len(self.tokens):
            return self.tokens[-1] # EOF
        return self.tokens[self.current + offset]

    def previous(self) -> Token:
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
        
    def _loc(self, node: ast.ASTNode, token: Token) -> ast.ASTNode:
        """Inject location information."""
        node.lineno = token.line
        node.col_offset = token.column
        node.end_lineno = token.end_line
        node.end_col_offset = token.end_column
        return node

    # --- Shared Parsing Logic ---

    def parse_import(self) -> ast.Import:
        """Parses 'import a.b, c as d'."""
        start_token = self.previous() # 'import' already consumed by caller usually, but let's assume caller calls this
        # Actually, if I call this, I expect 'import' to be current or previous?
        # Standard pattern: `if match(IMPORT): parse_import()`
        # So previous token is IMPORT.
        
        names = self.parse_aliases()
        self.consume_end_of_statement("Expect newline after import.")
        return self._loc(ast.Import(names=names), start_token)

    def parse_from_import(self) -> ast.ImportFrom:
        """Parses 'from .a import b'."""
        start_token = self.previous() # 'from' already consumed
        
        # Handle relative imports: from . import x, from ..foo import x
        level = 0
        while self.match(TokenType.DOT):
            level += 1
            
        module_name = None
        if self.check(TokenType.IDENTIFIER):
            module_name = self.parse_dotted_name()
            
        self.consume(TokenType.IMPORT, "Expect 'import'.")
        names = self.parse_aliases()
        
        self.consume_end_of_statement("Expect newline after import.")
        return self._loc(ast.ImportFrom(module=module_name, names=names, level=level), start_token)

    def parse_aliases(self) -> List[ast.alias]:
        aliases = []
        while True:
            start = self.peek()
            
            if self.match(TokenType.STAR):
                aliases.append(self._loc(ast.alias(name='*', asname=None), start))
            else:
                name = self.parse_dotted_name()
                asname = None
                
                # Check for 'as' keyword
                if self.match(TokenType.AS):
                    asname = self.consume(TokenType.IDENTIFIER, "Expect alias name.").value
                
                aliases.append(self._loc(ast.alias(name=name, asname=asname), start))
            
            if not self.match(TokenType.COMMA):
                break
        return aliases

    def parse_dotted_name(self) -> str:
        name = self.consume(TokenType.IDENTIFIER, "Expect identifier.").value
        while self.match(TokenType.DOT):
            name += "." + self.consume(TokenType.IDENTIFIER, "Expect identifier after '.'.").value
        return name

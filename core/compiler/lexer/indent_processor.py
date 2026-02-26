from typing import List, Optional, Tuple
from core.types.lexer_types import Token, TokenType
from core.compiler.lexer.str_stream import StrStream
from core.support.diagnostics.issue_tracker import IssueTracker
from core.support.diagnostics.codes import PAR_INDENTATION_ERROR
from core.types.diagnostic_types import Severity

class IndentProcessor:
    """
    Handles indentation processing for IBC-Inter Lexer.
    Maintains the indentation stack and generates INDENT/DEDENT tokens.
    """
    def __init__(self, scanner: StrStream, issue_tracker: IssueTracker):
        self.scanner = scanner
        self.issue_tracker = issue_tracker
        self.indent_stack: List[int] = [0]

    def process(self) -> Tuple[Optional[int], List[Token]]:
        """
        Calculate and generate INDENT/DEDENT tokens for the current line.
        
        Returns:
            Tuple[Optional[int], List[Token]]:
            - The current indentation level (None if empty/comment line).
            - A list of generated tokens (INDENT/DEDENT).
        """
        start_col = self.scanner.col
        spaces = 0
        tokens: List[Token] = []
        
        # Count spaces
        while self.scanner.peek() in ' \t':
            self.scanner.advance()
            spaces += 1
            
        # Check for empty lines or comments
        if self.scanner.peek() == '\n':
            self.scanner.advance()
            return None, tokens
        if self.scanner.peek() == '#':
            self._skip_comment()
            if self.scanner.peek() == '\n':
                self.scanner.advance()
            return None, tokens
        if self.scanner.is_at_end():
            return None, tokens

        current_indent = spaces
        last_indent = self.indent_stack[-1]
        
        if current_indent > last_indent:
            self.indent_stack.append(current_indent)
            tokens.append(Token(TokenType.INDENT, "", self.scanner.line, start_col))
        elif current_indent < last_indent:
            while current_indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, "", self.scanner.line, start_col))
            
            if current_indent != self.indent_stack[-1]:
                self.issue_tracker.report(
                    Severity.ERROR, 
                    PAR_INDENTATION_ERROR, 
                    "Unindent does not match any outer indentation level",
                    self.scanner
                )
        
        return current_indent, tokens

    def handle_eof(self) -> List[Token]:
        """Generate remaining DEDENT tokens at EOF."""
        tokens: List[Token] = []
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            tokens.append(Token(TokenType.DEDENT, "", self.scanner.line, 0))
        return tokens

    def _skip_comment(self):
        """Skip comments until end of line (do not consume newline)."""
        while self.scanner.peek() != '\n' and not self.scanner.is_at_end():
            self.scanner.advance()

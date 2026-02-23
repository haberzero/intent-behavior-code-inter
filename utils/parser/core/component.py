from typing import TypeVar, Optional
from typedef import parser_types as ast
from typedef.lexer_types import Token
from utils.parser.core.context import ParserContext

T = TypeVar("T", bound=ast.ASTNode)

class BaseComponent:
    """
    Base class for parser components.
    Provides access to the parser context and shared utilities.
    """
    def __init__(self, context: ParserContext):
        self.context = context

    @property
    def stream(self):
        return self.context.stream

    @property
    def issue_tracker(self):
        return self.context.issue_tracker

    @property
    def scope_manager(self):
        return self.context.scope_manager

    def _loc(self, node: T, token: Token) -> T:
        """Inject location information."""
        node.lineno = token.line
        node.col_offset = token.column
        node.end_lineno = token.end_line
        node.end_col_offset = token.end_column
        return node

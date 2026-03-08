from typing import Any, Optional, TypeVar
from core.domain import ast as ast
from core.domain.tokens import Token
from core.compiler.parser.core.context import ParserContext

T = TypeVar("T", bound=ast.IbASTNode)

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

    def _loc(self, node: T, start_obj: Any) -> T:
        """Helper to attach location info to a node from a token or other object with lineno/col_offset."""
        if hasattr(start_obj, 'line'):
            node.lineno = start_obj.line
            node.col_offset = start_obj.column
        else:
            node.lineno = getattr(start_obj, 'lineno', 0)
            node.col_offset = getattr(start_obj, 'col_offset', 0)
        return node

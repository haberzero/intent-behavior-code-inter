from typing import Any, Optional, TypeVar
from core.kernel import ast as ast
from core.compiler.common.tokens import Token
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

    def _loc(self, node: T, start_obj: Any, end_obj: Optional[Any] = None) -> T:
        """Helper to attach location info to a node from a token or other object with line/column.

        输入统一为 Token 或 IbASTNode——两者都经 ``.line``/``.column``/``.end_line``/
        ``.end_column`` 属性暴露位置（IbASTNode 已提供同名属性转发），无需双形状探测。
        """
        node.lineno = start_obj.line
        node.col_offset = start_obj.column
        if hasattr(start_obj, 'end_line'):
            node.end_lineno = start_obj.end_line
            node.end_col_offset = start_obj.end_column

        if end_obj:
            node.end_lineno = end_obj.end_line
            node.end_col_offset = end_obj.end_column
        
        return node

    def _extend_loc(self, node: T, end_obj: Any) -> T:
        """Extends the end location of a node using another object's end position."""
        if hasattr(end_obj, 'end_line'):
            node.end_lineno = end_obj.end_line
            node.end_col_offset = end_obj.end_column
        elif hasattr(end_obj, 'end_lineno'):
            node.end_lineno = end_obj.end_lineno
            node.end_col_offset = end_obj.end_col_offset
        return node

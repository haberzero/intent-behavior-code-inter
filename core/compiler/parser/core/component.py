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
        """Helper to attach location info to a node from a token or other object with line/column."""
        if hasattr(start_obj, 'line'):
            node.lineno = start_obj.line
            node.col_offset = start_obj.column
            if hasattr(start_obj, 'end_line'):
                node.end_lineno = start_obj.end_line
                node.end_col_offset = start_obj.end_column
        elif hasattr(start_obj, 'lineno'):
            node.lineno = start_obj.lineno
            node.col_offset = start_obj.col_offset
            node.end_lineno = getattr(start_obj, 'end_lineno', None)
            node.end_col_offset = getattr(start_obj, 'end_col_offset', None)

        if end_obj:
            if hasattr(end_obj, 'end_line'):
                node.end_lineno = end_obj.end_line
                node.end_col_offset = end_obj.end_column
            elif hasattr(end_obj, 'end_lineno'):
                node.end_lineno = end_obj.end_lineno
                node.end_col_offset = end_obj.end_col_offset
        
        # [Intent Smearing] 暂存 Parser 发现的意图
        # [Fix] 仅将意图附加到语句或特定的表达式（如 BehaviorExpr）上，防止 sub-nodes (如 IbName) 过早夺取意图
        if isinstance(node, (ast.IbStmt, ast.IbBehaviorExpr, ast.IbTypeAnnotatedExpr)):
            intents = self.context.consume_intents()
            if intents:
                # 如果节点已经有了意图（可能来自多重标注），则追加
                existing = getattr(node, "_pending_intents", [])
                setattr(node, "_pending_intents", existing + intents)
            
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

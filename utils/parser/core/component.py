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

    def _set_scene_recursive(self, node: ast.ASTNode, scene: ast.Scene):
        """Recursively set the scene tag for behavior expressions and operations."""
        if isinstance(node, ast.Expr):
            node.scene_tag = scene
            
        # Specific handling for common expression containers
        if isinstance(node, ast.BoolOp):
            for val in node.values:
                self._set_scene_recursive(val, scene)
        elif isinstance(node, ast.UnaryOp):
            self._set_scene_recursive(node.operand, scene)
        elif isinstance(node, ast.BinOp):
            self._set_scene_recursive(node.left, scene)
            self._set_scene_recursive(node.right, scene)
        elif isinstance(node, ast.Compare):
            self._set_scene_recursive(node.left, scene)
            for comparator in node.comparators:
                self._set_scene_recursive(comparator, scene)
        elif isinstance(node, ast.Call):
            for arg in node.args:
                self._set_scene_recursive(arg, scene)
        # Add more if needed, but these cover most logic in if/while conditions

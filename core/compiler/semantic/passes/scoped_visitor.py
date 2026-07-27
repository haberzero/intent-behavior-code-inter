"""
ScopedVisitor — Unified base class for AST visitors with scope management.

Provides:
- scope_stack with push/pop
- current_scope property
- enter_scope() context manager for safe scope lifecycle
- visit() dispatch with generic_visit fallback
- error/warning diagnostic helpers

Eliminates ~200 lines of duplicated scope management across
SymbolResolver, TypeCheckingVisitor, and LambdaCaptureAnalyzer.
"""

from contextlib import contextmanager
from typing import Optional, List, Any

from core.base.diagnostics.codes import SEM_UNCATEGORIZED
from core.kernel import ast
from core.kernel.symbols import SymbolTable

from ..result import Diagnostic, DiagnosticLevel
from ..context import SemanticContext


class ScopedVisitor:
    """Base class for AST visitors that manage a scope stack.

    Subclasses get:
    - self.context, self.symbol_table, self.registry
    - self.scope_stack, self.current_scope, push_scope/pop_scope
    - enter_scope() context manager (preferred over raw push/pop)
    - self.diagnostics list with error()/warning() helpers
    - visit() dispatch → visit_ClassName methods
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []

        # Scope stack: root scope is always present
        self.scope_stack: List[SymbolTable] = [self.symbol_table]

    @property
    def current_scope(self) -> SymbolTable:
        """Current active scope."""
        return self.scope_stack[-1]

    def push_scope(self, scope: SymbolTable):
        """Enter a new scope."""
        self.scope_stack.append(scope)

    def pop_scope(self):
        """Exit the current scope (never pops root)."""
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()

    @contextmanager
    def enter_scope(self, scope: SymbolTable):
        """Context manager for safe scope lifecycle.

        Usage:
            with self.enter_scope(func_scope):
                # ... visit body within func_scope
            # scope automatically restored
        """
        self.push_scope(scope)
        try:
            yield scope
        finally:
            self.pop_scope()

    # ---- Visit dispatch ----

    def visit(self, node: ast.IbASTNode) -> Any:
        """Dispatch to visit_ClassName method. Returns None for unknown nodes."""
        if node is None:
            return None
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode) -> Any:
        """Default: recursively visit all child AST nodes."""
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.visit(item)
            elif isinstance(child, ast.IbASTNode):
                self.visit(child)
        return None

    # ---- Diagnostic helpers ----

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
        """Record an error diagnostic."""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def warning(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
        """Record a warning diagnostic."""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.WARNING,
            message=message,
            code=code,
            node_uid=node_uid
        ))

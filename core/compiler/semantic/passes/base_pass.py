"""
Base Pass Abstract Class

Defines the interface for all semantic analysis passes.

Design principle: Each pass is independent and composable.
"""

from abc import ABC, abstractmethod
from typing import Optional
from ..context import SemanticContext
from ..result import PassResult, Diagnostic


class BasePass(ABC):
    """
    Abstract base class for semantic analysis passes.

    Contract:
    - Takes a SemanticContext as input
    - Returns a PassResult with (possibly updated) context and diagnostics
    - Should not throw exceptions (use PassResult.fail instead)
    - Should be stateless (all state in context)

    Comparison with V1:
    - V1: All passes mixed into one class
    - V2: Each pass is independent, testable unit
    """

    def __init__(self, pass_name: str):
        self.pass_name = pass_name

    @abstractmethod
    def run(self, context: SemanticContext) -> PassResult:
        """
        Run this pass on the given context.

        Args:
            context: Current semantic analysis context

        Returns:
            PassResult with updated context and diagnostics

        Design note: This method should never throw exceptions.
        All errors should be captured in the PassResult.
        """
        pass

    def safe_run(self, context: SemanticContext) -> PassResult:
        """
        Run the pass with exception handling.

        Wraps run() to catch any unexpected exceptions.
        """
        try:
            return self.run(context)
        except Exception as e:
            diagnostic = Diagnostic.from_exception(e)
            return PassResult.fail(context, diagnostic, pass_name=self.pass_name)

    def should_skip(self, context: SemanticContext) -> bool:
        """
        Check if this pass should be skipped.

        Override to implement conditional pass execution.
        """
        return False

    def get_dependencies(self) -> list[str]:
        """
        Get list of pass names that must run before this pass.

        Override to declare dependencies.
        """
        return []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.pass_name}>"

    @staticmethod
    def iter_child_nodes(node):
        """
        Safely iterate over child AST nodes.

        Yields (attr_name, child_node) pairs for all AST node children.
        Handles None values and non-dict objects gracefully.
        """
        if node is None or not hasattr(node, '__dict__'):
            return

        for attr_name, value in vars(node).items():
            if attr_name.startswith('_'):
                continue

            # Import here to avoid circular dependency
            from core.kernel import ast

            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.IbASTNode):
                        yield (attr_name, item)
            elif isinstance(value, ast.IbASTNode):
                yield (attr_name, value)

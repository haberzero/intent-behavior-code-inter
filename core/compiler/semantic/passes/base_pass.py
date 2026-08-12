"""
Base Pass Abstract Class

Defines the interface for all semantic analysis passes.

Design principle: Each pass is independent and composable.
"""

from abc import ABC, abstractmethod
from typing import Optional
import traceback
from ..context import SemanticContext
from ..result import PassResult


class BasePass(ABC):
    """
    Abstract base class for semantic analysis passes.

    Contract:
    - Takes a SemanticContext as input
    - Returns a PassResult with (possibly updated) context and diagnostics
    - Should not throw exceptions (use PassResult.fail instead)
    - Should be stateless (all state in context)
    - Each pass is independent and testable
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

        Wraps run() to catch unexpected exceptions. ``run()`` 报告语义错误
        走 ``self.error()``（进 PassResult 不抛）；此处捕获的均为 pass 自身的
        编程错误（pass bug），必须 fail-fast 崩溃暴露——伪装成编译错误诊断
        会掩盖 pass 内部缺陷，且无 traceback 无从定位。
        """
        try:
            return self.run(context)
        except Exception as e:
            traceback.print_exc()
            raise

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

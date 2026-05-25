"""
Phase 1: Symbol Phase (formerly Pass 1 + Pass 2)

职责：符号收集 + 符号解析，共享 scope stack，一次 Phase 完成
输入：AST
输出：Context with populated symbol_table and resolved symbol bindings

设计原则：
- 两个子步骤在同一 Phase 内顺序执行，共享上下文
- 符号收集（sub-step 1）→ 符号解析（sub-step 2）
- 消除 pipeline 层面的额外 context 传递开销
"""

from ..result import PassResult
from ..context import SemanticContext
from .base_pass import BasePass
from .symbol_collection_pass import SymbolCollectionPass
from .symbol_resolution_pass import SymbolResolutionPass


class SymbolPhase(BasePass):
    """符号阶段（Phase 1）

    合并原 Pass 1（SymbolCollectionPass）和 Pass 2（SymbolResolutionPass）。
    两步共享同一 SemanticContext 实例，顺序执行：
    1. 收集所有符号定义（类、函数、全局变量）
    2. 解析所有符号引用，绑定到 metadata
    """

    def __init__(self):
        super().__init__("SymbolPhase")
        self._collection_pass = SymbolCollectionPass()
        self._resolution_pass = SymbolResolutionPass()

    def run(self, context: SemanticContext) -> PassResult:
        """运行符号阶段：收集 → 解析"""
        # Sub-step 1: Symbol Collection
        result = self._collection_pass.run(context)
        all_diagnostics = list(result.diagnostics)

        # Sub-step 2: Symbol Resolution (uses updated context from step 1)
        result2 = self._resolution_pass.run(result.context)
        all_diagnostics.extend(result2.diagnostics)

        success = result.success and result2.success

        return PassResult(
            context=result2.context,
            metadata={},
            diagnostics=all_diagnostics,
            success=success,
        )

"""
Phase 1: Symbol Phase

职责：符号收集 + 符号解析 + TypeRef 解析收口
输入：AST + empty symbol_table
输出：PassOutput with symbol_bindings; Context with populated symbol_table
"""

from ..result import PassResult, PassOutput
from ..context import SemanticContext
from .base_pass import BasePass
from .symbol_collection_pass import SymbolCollectionPass
from .symbol_resolution_pass import SymbolResolutionPass
from .typeref_resolution_pass import TypeRefResolutionPass


class SymbolPhase(BasePass):
    """符号阶段（Phase 1）

    1. 收集所有符号定义（类、函数、全局变量）
    2. 解析所有符号引用，绑定到 PassOutput
    3. 将残留 TypeRef spec 解析为具体 IbSpec
    """

    def __init__(self):
        super().__init__("SymbolPhase")
        self._collection_pass = SymbolCollectionPass()
        self._resolution_pass = SymbolResolutionPass()
        self._typeref_pass = TypeRefResolutionPass()

    def run(self, context: SemanticContext) -> PassResult:
        # Sub-step 1: Symbol Collection (populates symbol_table)
        result1 = self._collection_pass.run(context)

        # Sub-step 2: Symbol Resolution (produces symbol_bindings)
        result2 = self._resolution_pass.run(result1.context)

        # Sub-step 3: TypeRef Resolution (resolves residual TypeRef specs)
        result3 = self._typeref_pass.run(result2.context)

        # Merge diagnostics; symbol_bindings come from resolution pass
        all_diags = (list(result1.output.diagnostics)
                     + list(result2.output.diagnostics)
                     + list(result3.output.diagnostics))
        merged_output = PassOutput(
            symbol_bindings=result2.output.symbol_bindings,
            diagnostics=all_diags,
            success=result1.success and result2.success and result3.success,
        )

        return PassResult.ok(result3.context, output=merged_output)

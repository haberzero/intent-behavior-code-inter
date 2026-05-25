"""
Phase 3: Binding Phase

职责：绑定分析 + 行为依赖分析
输入：Context with type_bindings
输出：PassOutput with cell_captured_symbols; AST dependency annotations
"""

from ..result import PassResult, PassOutput
from ..context import SemanticContext
from .base_pass import BasePass
from .binding_analysis_pass import BindingAnalysisPass
from .behavior_dependency_pass import BehaviorDependencyPass


class BindingPhase(BasePass):
    """绑定阶段（Phase 3）

    1. 绑定分析（llmexcept body 重写、intent 验证、lambda 捕获）
    2. 行为依赖分析（LLM 依赖图、dispatch_eligible 标注）
    """

    def __init__(self):
        super().__init__("BindingPhase")
        self._binding_pass = BindingAnalysisPass()
        self._dependency_pass = BehaviorDependencyPass()

    def run(self, context: SemanticContext) -> PassResult:
        # Sub-step 1: Binding Analysis
        result1 = self._binding_pass.run(context)

        # Sub-step 2: Behavior Dependency
        result2 = self._dependency_pass.run(result1.context)

        # Merge outputs
        all_diags = list(result1.output.diagnostics) + list(result2.output.diagnostics)
        merged_output = PassOutput(
            cell_captured_symbols=result1.output.cell_captured_symbols,
            diagnostics=all_diags,
            success=result1.success and result2.success,
        )

        return PassResult.ok(result2.context, output=merged_output)

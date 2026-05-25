"""
Phase 3: Binding Phase (formerly Pass 4 + Pass 5)

职责：绑定分析 + 行为依赖分析，一次 AST 遍历完成结构变换+依赖标注
输入：Context with type_bindings
输出：Context with binding metadata and AST dependency annotations

设计原则：
- BindingAnalysisPass 做 llmexcept/intent/lambda 绑定
- BehaviorDependencyPass 做 LLM 依赖图分析
- 两步合并为一个 Phase，减少 pipeline 调度
"""

from ..result import PassResult
from ..context import SemanticContext
from .base_pass import BasePass
from .binding_analysis_pass import BindingAnalysisPass
from .behavior_dependency_pass import BehaviorDependencyPass


class BindingPhase(BasePass):
    """绑定阶段（Phase 3）

    合并原 Pass 4（BindingAnalysisPass）和 Pass 5（BehaviorDependencyPass）。
    两步共享同一 SemanticContext 实例，顺序执行：
    1. 绑定分析（llmexcept body 重写、intent 验证、lambda 捕获）
    2. 行为依赖分析（LLM 依赖图、dispatch_eligible 标注）
    """

    def __init__(self):
        super().__init__("BindingPhase")
        self._binding_pass = BindingAnalysisPass()
        self._dependency_pass = BehaviorDependencyPass()

    def run(self, context: SemanticContext) -> PassResult:
        """运行绑定阶段：绑定 → 依赖"""
        # Sub-step 1: Binding Analysis
        result = self._binding_pass.run(context)
        all_diagnostics = list(result.diagnostics)

        # Sub-step 2: Behavior Dependency (uses context after llmexcept body rewrite)
        result2 = self._dependency_pass.run(result.context)
        all_diagnostics.extend(result2.diagnostics)

        success = result.success and result2.success

        return PassResult(
            context=result2.context,
            metadata={},
            diagnostics=all_diagnostics,
            success=success,
        )

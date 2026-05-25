"""
Phase 2: Type Phase (formerly Pass 2.5 + Pass 3)

职责：类型标注解析 + 类型检查/推断
输入：Context with resolved symbols
输出：Context with type_bindings

设计原则：
- TypeResolutionPass 将类型名称字符串转为 IbSpec
- TypeCheckingPass 在已解析类型的基础上做类型检查和推断
- 两步合并消除独立 Pass 间的重复类型解析逻辑
"""

from ..result import PassResult
from ..context import SemanticContext
from .base_pass import BasePass
from .type_resolution_pass import TypeResolutionPass
from .type_checking_pass import TypeCheckingPass


class TypePhase(BasePass):
    """类型阶段（Phase 2）

    合并原 Pass 2.5（TypeResolutionPass）和 Pass 3（TypeCheckingPass）。
    两步共享同一 SemanticContext 实例，顺序执行：
    1. 解析类型标注（名称 → IbSpec）
    2. 类型检查和推断
    """

    def __init__(self):
        super().__init__("TypePhase")
        self._resolution_pass = TypeResolutionPass()
        self._checking_pass = TypeCheckingPass()

    def run(self, context: SemanticContext) -> PassResult:
        """运行类型阶段：解析 → 检查"""
        # Sub-step 1: Type Resolution
        result = self._resolution_pass.run(context)
        all_diagnostics = list(result.diagnostics)

        # Sub-step 2: Type Checking (uses context with resolved type annotations)
        result2 = self._checking_pass.run(result.context)
        all_diagnostics.extend(result2.diagnostics)

        success = result.success and result2.success

        return PassResult(
            context=result2.context,
            metadata={},
            diagnostics=all_diagnostics,
            success=success,
        )

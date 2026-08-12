"""
Phase 2: Type Phase

职责：类型标注解析 + 类型检查/推断
输入：Context with resolved symbols
输出：PassOutput with type_bindings
"""

from ..result import PassResult, PassOutput
from ..context import SemanticContext
from .base_pass import BasePass
from .type_resolution_pass import TypeResolutionPass
from .type_checking_pass import TypeCheckingPass


class TypePhase(BasePass):
    """类型阶段（Phase 2）

    1. 解析类型标注（名称 → IbSpec）
    2. 类型检查和推断
    """

    def __init__(self):
        super().__init__("TypePhase")
        self._resolution_pass = TypeResolutionPass()
        self._checking_pass = TypeCheckingPass()

    def run(self, context: SemanticContext) -> PassResult:
        # Sub-step 1: Type Resolution
        result1 = self._resolution_pass.run(context)

        # Sub-step 2: Type Checking
        result2 = self._checking_pass.run(result1.context)

        # Merge type_bindings from both sub-steps
        merged_types = {**result1.output.type_bindings, **result2.output.type_bindings}
        all_diags = list(result1.output.diagnostics) + list(result2.output.diagnostics)
        merged_output = PassOutput(
            type_bindings=merged_types,
            diagnostics=all_diags,
            success=result1.success and result2.success,
        )

        return PassResult.ok(result2.context, output=merged_output)

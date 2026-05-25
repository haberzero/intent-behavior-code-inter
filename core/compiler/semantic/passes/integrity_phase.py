"""
Phase 4: Integrity Phase

职责：完整性检查 + 位置绑定
输入：Context with all phases completed
输出：PassOutput with location_bindings + final diagnostics
"""

from ..result import PassResult, PassOutput
from ..context import SemanticContext
from .base_pass import BasePass
from .integrity_check_pass import IntegrityCheckPass


class IntegrityPhase(BasePass):
    """完整性阶段（Phase 4）

    纯验证 + 位置绑定：检查所有引用节点都有符号绑定，所有表达式都有类型绑定。
    """

    def __init__(self):
        super().__init__("IntegrityPhase")
        self._check_pass = IntegrityCheckPass()

    def run(self, context: SemanticContext) -> PassResult:
        return self._check_pass.run(context)

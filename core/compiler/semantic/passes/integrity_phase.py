"""
Phase 4: Integrity Phase (formerly Pass 6)

职责：完整性检查，验证所有节点都有必要的绑定
输入：Context with all phases completed
输出：Final diagnostics

设计原则：
- 纯验证阶段，不做 AST 变换
- 独立于前三个 Phase，作为最终守门人
- 薄包装层：委托给 IntegrityCheckPass 实现
"""

from ..result import PassResult
from ..context import SemanticContext
from .base_pass import BasePass
from .integrity_check_pass import IntegrityCheckPass


class IntegrityPhase(BasePass):
    """完整性阶段（Phase 4）

    包装原 IntegrityCheckPass，保持独立。
    纯验证：检查所有引用节点都有符号绑定，所有表达式都有类型绑定。
    """

    def __init__(self):
        super().__init__("IntegrityPhase")
        self._check_pass = IntegrityCheckPass()

    def run(self, context: SemanticContext) -> PassResult:
        """运行完整性阶段"""
        return self._check_pass.run(context)

"""
Integrity Check Pass (IntegrityPhase)

职责：为所有 AST 节点绑定位置信息 + 符号表一致性验证
输入：Context with all phases completed
输出：PassOutput with location_bindings
"""

from typing import List, Dict, Any

from core.kernel import ast

from ..result import PassResult, PassOutput, Diagnostic
from ..context import SemanticContext
from .base_pass import BasePass


class LocationBinder:
    """Traverse all AST nodes and bind location info to metadata."""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.bindings: Dict[Any, Dict[str, Any]] = {}
        self._file_path = getattr(context, 'module_name', '<unknown>')

    def bind_all(self, node: ast.IbASTNode):
        """Recursively bind location for all nodes."""
        if node is None:
            return
        self._bind_node(node)
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.bind_all(item)
            elif isinstance(child, ast.IbASTNode):
                self.bind_all(child)

    def _bind_node(self, node: ast.IbASTNode):
        """Bind location info for a single node."""
        lineno = getattr(node, 'lineno', 0)
        col_offset = getattr(node, 'col_offset', 0)
        self.bindings[node] = {
            "file_path": self._file_path,
            "line": lineno,
            "column": col_offset,
        }


class IntegrityCheckPass(BasePass):
    """完整性检查 Pass（IntegrityPhase）

    - 绑定位置信息到所有 AST 节点
    - 验证符号表一致性
    """

    def __init__(self):
        super().__init__("IntegrityCheckPass")

    def run(self, context: SemanticContext) -> PassResult:

        # Populate location bindings for all AST nodes
        loc_binder = LocationBinder(context)
        loc_binder.bind_all(context.ast)

        # Run symbol table consistency check
        checker = IntegrityChecker(context)
        checker.check()

        output = PassOutput(
            location_bindings=loc_binder.bindings,
            diagnostics=checker.diagnostics,
            success=True,
        )
        return PassResult.ok(context, output=output)


class IntegrityChecker:
    """符号表一致性检查器"""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []

    def check(self):
        """验证符号表中所有符号的一致性。"""
        for symbol_name, symbol in self.context.symbol_table.current.symbols.items():
            if hasattr(symbol, 'node_uid') and symbol.node_uid:
                pass  # 未来可扩展：验证符号定义节点存在性

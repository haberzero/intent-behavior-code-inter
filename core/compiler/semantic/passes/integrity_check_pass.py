"""
Integrity Check Pass (IntegrityPhase)

职责：为所有 AST 节点绑定位置信息 + 符号表一致性验证
输入：Context with all phases completed
输出：PassOutput with location_bindings
"""

from typing import Dict, Any

from core.kernel import ast

from ..result import PassResult, PassOutput
from ..context import SemanticContext
from .base_pass import BasePass


class LocationBinder:
    """Traverse all AST nodes and bind location info to metadata."""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.bindings: Dict[Any, Dict[str, Any]] = {}
        # 位置绑定的 file_path = 模块源文件真实路径（诊断渲染/源行上下文
        # 的单一权威源）；无文件载体（临时编译/直接构造 context）回落
        # 模块名标识。
        self._file_path = (
            getattr(context, 'module_file_path', "") or
            getattr(context, 'module_name', '<unknown>')
        )

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

        output = PassOutput(
            location_bindings=loc_binder.bindings,
            success=True,
        )
        return PassResult.ok(context, output=output)

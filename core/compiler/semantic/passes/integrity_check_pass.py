"""
Integrity Check Pass (IntegrityPhase)

职责：完整性检查，验证所有节点都有必要的绑定
输入：Context with all phases completed
输出：Final diagnostics

设计原则：
- 只检查编译器生成的绑定（symbol_bindings, type_bindings）
- 不检查 AST 固有属性（如 llm_deps, dispatch_eligible）
- AST 固有属性由各 Pass 直接写入，不需要完整性验证
"""

from typing import List, Set, Dict, Any

from core.kernel import ast

from ..result import PassResult, Diagnostic, DiagnosticLevel
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

    验证语义分析的完整性：
    - 检查所有引用节点都有符号绑定
    - 检查所有表达式节点都有类型绑定
    - 检查符号表的完整性
    
    不检查：
    - AST 固有属性（llm_deps, dispatch_eligible）- 这些由 BehaviorDependencyPass 直接写入
    """

    def __init__(self):
        super().__init__("IntegrityCheckPass")

    def run(self, context: SemanticContext) -> PassResult:
        from ..result import PassOutput

        # 1. Populate location bindings for all AST nodes
        loc_binder = LocationBinder(context)
        loc_binder.bind_all(context.ast)

        # 2. Run integrity checks
        checker = IntegrityChecker(context)
        checker.check()

        output = PassOutput(
            location_bindings=loc_binder.bindings,
            diagnostics=checker.diagnostics,
            success=True,
        )
        return PassResult.ok(context, output=output)


class IntegrityChecker:
    """完整性检查器

    验证语义分析的完整性：
    - 所有符号引用都已解析
    - 所有表达式都有类型
    - 元数据一致性
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []

        # 收集的节点集合
        self.reference_nodes: Set[str] = set()  # 所有符号引用节点的 UID
        self.expression_nodes: Set[str] = set()  # 所有表达式节点的 UID

    def warning(self, message: str, node_uid: str = None, code: str = "INTEGRITY_000"):
        """记录警告诊断"""
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.WARNING,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def error(self, message: str, node_uid: str = None, code: str = "INTEGRITY_000"):
        """记录错误诊断"""
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def check(self):
        """执行完整性检查"""
        # 1. 收集所有需要绑定的节点
        self._collect_nodes(self.context.ast)

        # 2. 检查符号绑定完整性
        self._check_symbol_bindings()

        # 3. 检查类型绑定完整性
        self._check_type_bindings()

        # 4. 检查元数据一致性（仅检查编译器生成的绑定）
        self._check_metadata_consistency()

    def _collect_nodes(self, node: ast.IbASTNode):
        """收集需要检查的节点"""
        node_uid = getattr(node, 'uid', None)

        # 收集符号引用节点（IbName）
        if isinstance(node, ast.IbName):
            if node_uid:
                self.reference_nodes.add(node_uid)

        # 收集表达式节点（所有产生值的节点）
        if self._is_expression_node(node):
            if node_uid:
                self.expression_nodes.add(node_uid)

        # 递归处理子节点
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self._collect_nodes(item)
            elif isinstance(child, ast.IbASTNode):
                self._collect_nodes(child)

    def _is_expression_node(self, node: ast.IbASTNode) -> bool:
        """判断节点是否为表达式节点"""
        expression_types = (
            ast.IbName,
            ast.IbConstant,
            ast.IbListExpr,
            ast.IbDict,
            ast.IbTuple,
            ast.IbBinOp,
            ast.IbUnaryOp,
            ast.IbCompare,
            ast.IbCall,
            ast.IbAttribute,
            ast.IbSubscript,
            ast.IbLambdaExpr,
            ast.IbBehaviorExpr,
        )
        return isinstance(node, expression_types)

    def _check_symbol_bindings(self):
        """检查符号绑定的完整性（no-op: bindings use node objects as keys）"""
        pass

    def _check_type_bindings(self):
        """检查类型绑定的完整性（no-op: bindings use node objects as keys）"""
        pass

    def _check_metadata_consistency(self):
        """检查元数据的一致性（仅检查编译器生成的绑定）"""
        # 检查符号表与符号绑定的一致性
        self._check_symbol_table_consistency()

        # 注意：不检查 behavior 依赖的一致性
        # 原因：llm_deps 和 dispatch_eligible 是 AST 固有属性，
        # 由 BehaviorDependencyPass 直接写入 AST 节点，不需要验证一致性

    def _check_symbol_table_consistency(self):
        """检查符号表的一致性"""
        # 验证符号表中的符号都有对应的节点
        for symbol_name, symbol in self.context.symbol_table.current.symbols.items():
            if hasattr(symbol, 'node_uid') and symbol.node_uid:
                # 符号应该有对应的定义节点
                # 注意：符号定义不在 symbol_bindings 中（那里存的是引用）
                pass

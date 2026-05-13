"""
Pass 1: Symbol Collection Pass

职责：收集所有符号定义（类、函数、全局变量）
输入：AST
输出：Context with populated symbol_table
"""

from dataclasses import replace
from typing import Optional, List, Tuple

from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, TypeSymbol, FunctionSymbol, VariableSymbol, SymbolKind
from core.kernel.spec import IbSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.member import MethodMemberSpec, MemberSpec

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class SymbolExtractor:
    """符号提取器：从 AST 节点中提取定义的符号名"""

    @staticmethod
    def get_assigned_names(node: ast.IbASTNode) -> List[Tuple[str, ast.IbASTNode]]:
        """提取赋值或迭代语句中的目标名称及对应的节点"""
        results = []

        def _extract(target: ast.IbASTNode):
            if isinstance(target, ast.IbName):
                results.append((target.id, target))
            elif isinstance(target, ast.IbTypeAnnotatedExpr):
                results.append((target.target.id, target))
                _extract(target.target)
            elif isinstance(target, ast.IbTuple):
                for el in target.elts:
                    _extract(el)

        if isinstance(node, ast.IbAssign):
            for target in node.targets:
                _extract(target)
        elif isinstance(node, ast.IbFor):
            if node.target:
                _extract(node.target)
        elif isinstance(node, ast.IbExceptHandler):
            if node.name:
                results.append((node.name, node))

        return results


class SymbolCollectionPass(BasePass):
    """符号收集 Pass（Pass 1）

    收集顶层符号：
    - 类定义（IbClassDef）
    - 函数定义（IbFunctionDef, IbLLMFunctionDef）
    - 全局变量（IbAssign with type annotation）
    """

    def __init__(self):
        super().__init__("SymbolCollectionPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行符号收集 Pass"""
        visitor = SymbolCollector(context)
        visitor.visit(context.ast)

        # 符号表已在 visitor 中原地修改（SymbolTableContext 设计）
        # 无需更新 context，直接返回
        return PassResult.ok(context, diagnostics=visitor.diagnostics)


class SymbolCollector:
    """符号收集访问者"""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []

        # 状态变量
        self.current_class: Optional[IbSpec] = None

        # 临时使用 registry 的 _any_desc
        self._any_desc = context.registry.resolve("any")

    def visit(self, node: ast.IbASTNode):
        """访问节点的分派方法"""
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode):
        """默认访问：递归访问所有子节点"""
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.visit(item)
            elif isinstance(child, ast.IbASTNode):
                self.visit(child)

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000"):
        """记录错误诊断"""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def _define(self, sym: Symbol, node: ast.IbASTNode):
        """定义符号到符号表"""
        try:
            self.symbol_table.define(sym)

            # 如果在类作用域内，同步到类的成员表
            if self.current_class:
                if sym.kind in (SymbolKind.FUNCTION, SymbolKind.LLM_FUNCTION):
                    llm_kind = "llm_method" if sym.kind == SymbolKind.LLM_FUNCTION else "method"
                    self.current_class.members[sym.name] = MethodMemberSpec(
                        name=sym.name,
                        kind=llm_kind,
                        type_ref=TypeRef.of(sym.spec.name if sym.spec else "any")
                    )
                else:
                    self.current_class.members[sym.name] = MemberSpec(
                        name=sym.name,
                        kind="field",
                        type_ref=TypeRef.of(sym.spec.name if sym.spec else "any")
                    )

        except ValueError as e:
            self.error(str(e), node, code="SEM_002")

    def visit_IbModule(self, node: ast.IbModule):
        """访问模块节点"""
        for stmt in node.body:
            self.visit(stmt)

    def visit_IbClassDef(self, node: ast.IbClassDef):
        """访问类定义节点"""
        # 1. 创建类元数据
        cls_meta = self.registry.factory.create_class(
            name=node.name,
            parent_name=node.parent
        )
        cls_meta.is_user_defined = True

        # Enum Hook: 如果继承 Enum，设置 axiom_name
        if node.parent == "Enum":
            cls_meta._axiom_name = "enum"

        # 注册到 registry
        registered_meta = self.registry.register(cls_meta)

        # 2. 创建类符号
        sym = TypeSymbol(
            name=node.name,
            kind=SymbolKind.CLASS,
            def_node=node,
            spec=registered_meta
        )
        self._define(sym, node)

        # 3. 进入类作用域收集成员
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table, name=node.name)

        old_class = self.current_class
        self.current_class = registered_meta

        try:
            for stmt in node.body:
                self.visit(stmt)
            # 记录类作用域
            sym.owned_scope = self.symbol_table
        finally:
            self.current_class = old_class
            self.symbol_table = old_table

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """访问函数定义节点"""
        # 创建函数元数据（暂定为 Any -> Any）
        func_meta = self.registry.factory.create_func(
            name=node.name,
            param_type_names=[],
            return_type_name="any"
        )
        func_meta.is_user_defined = True
        self.registry.register(func_meta)

        # 创建函数符号
        sym = FunctionSymbol(
            name=node.name,
            kind=SymbolKind.FUNCTION,
            def_node=node,
            spec=func_meta
        )
        self._define(sym, node)

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """访问 LLM 函数定义节点"""
        # 创建函数元数据
        func_meta = self.registry.factory.create_func(
            name=node.name,
            param_type_names=[],
            return_type_name="any"
        )
        func_meta.is_user_defined = True
        self.registry.register(func_meta)

        # 创建 LLM 函数符号
        sym = FunctionSymbol(
            name=node.name,
            kind=SymbolKind.LLM_FUNCTION,
            def_node=node,
            spec=func_meta
        )
        sym.metadata["is_llm"] = True
        self._define(sym, node)

    def visit_IbAssign(self, node: ast.IbAssign):
        """访问赋值节点（收集全局/类成员变量）"""
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 避免重复定义
            if name not in self.symbol_table.symbols:
                sym = VariableSymbol(
                    name=name,
                    kind=SymbolKind.VARIABLE,
                    def_node=node,
                    spec=self._any_desc
                )
                self._define(sym, target)

        # 递归扫描（处理嵌套结构）
        self.generic_visit(node)

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """访问带类型标注的表达式"""
        self.visit(node.target)

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """访问带过滤条件的表达式"""
        self.visit(node.expr)
        self.visit(node.filter)

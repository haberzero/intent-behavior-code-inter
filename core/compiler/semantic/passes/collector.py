from typing import Optional, Any, List, Tuple, TYPE_CHECKING
from core.compiler.support.diagnostics import DiagnosticReporter
from core.domain import ast as ast
from core.domain.symbols import Symbol, SymbolTable, TypeSymbol, FunctionSymbol, VariableSymbol, SymbolKind, STATIC_ANY

if TYPE_CHECKING:
    from .semantic_analyzer import SemanticAnalyzer

class SymbolExtractor:
    """
    符号提取器：统一从 AST 节点中提取定义的符号名。
    实现逻辑归一化，确保 Pass 2.5 与 Pass 3 行为一致。
    """
    @staticmethod
    def get_assigned_names(node: ast.IbASTNode) -> List[Tuple[str, ast.IbASTNode]]:
        """提取赋值语句中的目标名称及对应的节点"""
        results = []
        if isinstance(node, ast.IbAssign):
            for target in node.targets:
                if isinstance(target, ast.IbName):
                    results.append((target.id, target))
                elif isinstance(target, ast.IbTypeAnnotatedExpr) and isinstance(target.target, ast.IbName):
                    results.append((target.target.id, target.target))
        elif isinstance(node, ast.IbFor):
            if isinstance(node.target, ast.IbName):
                results.append((node.target.id, node.target))
        elif isinstance(node, ast.IbExceptHandler):
            if node.name:
                results.append((node.name, node))
        return results

class SymbolCollector:
    """
    第一阶段：符号收集 (Pass 1)
    仅收集顶层符号（类、函数、LLM 函数），不进行类型解析。
    """
    def __init__(self, symbol_table: SymbolTable, analyzer: Optional['SemanticAnalyzer'] = None, issue_tracker: Optional[DiagnosticReporter] = None):
        self.symbol_table = symbol_table
        self.analyzer = analyzer
        self.issue_tracker = issue_tracker

    def collect(self, node: ast.IbASTNode):
        self.visit(node)

    def visit(self, node: ast.IbASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode):
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.visit(item)
            elif isinstance(child, ast.IbASTNode):
                self.visit(child)

    def visit_IbModule(self, node: ast.IbModule):
        for stmt in node.body:
            self.visit(stmt)

    def _define(self, sym: Symbol, node: ast.IbASTNode):
        try:
            self.symbol_table.define(sym)
            # [NEW Phase 5] 记录侧表映射
            if self.analyzer and hasattr(self.analyzer, "node_to_symbol"):
                self.analyzer.node_to_symbol[node] = sym
        except ValueError as e:
            if self.issue_tracker:
                self.issue_tracker.error(str(e), node)
            elif hasattr(self, "analyzer") and self.analyzer:
                self.analyzer.error(str(e), node)
            else:
                # 在 Pass 1 阶段没有 analyzer 或 reporter 时，直接抛出
                raise

    def visit_IbClassDef(self, node: ast.IbClassDef):
        # 1. 注册类符号
        sym = TypeSymbol(name=node.name, kind=SymbolKind.CLASS, def_node=node)
        self._define(sym, node)
        
        # 2. 进入类作用域收集成员
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        try:
            for stmt in node.body:
                self.visit(stmt)
            # 记录类作用域
            sym.owned_scope = self.symbol_table
        finally:
            self.symbol_table = old_table

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.FUNCTION, def_node=node)
        self._define(sym, node)
        
        # 函数内部参数和局部变量暂时不作为全局符号收集，留给分析阶段
        pass

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.LLM_FUNCTION, is_llm=True, def_node=node)
        self._define(sym, node)

    def visit_IbAssign(self, node: ast.IbAssign):
        """
        收集赋值语句产生的符号（类成员变量或全局变量）。
        """
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 避免在 Pass 1 重复定义
            if name not in self.symbol_table.symbols:
                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, def_node=node)
                self._define(sym, target) # 绑定 target 节点

    def visit_IbAnnotatedStmt(self, node: ast.IbAnnotatedStmt):
        """递归收集包装语句内的符号"""
        self.visit(node.stmt)

    def visit_IbAnnotatedExpr(self, node: ast.IbAnnotatedExpr):
        """递归收集包装表达式内的符号"""
        self.visit(node.expr)

    def visit_IbAnnotatedStmt(self, node: ast.IbAnnotatedStmt):
        """预扫描包装语句内的符号"""
        self.visit(node.stmt)

    def visit_IbAnnotatedExpr(self, node: ast.IbAnnotatedExpr):
        """预扫描包装表达式内的符号"""
        self.visit(node.expr)

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """预扫描带类型标注的表达式"""
        self.visit(node.target)

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """预扫描带过滤条件的表达式"""
        self.visit(node.expr)
        self.visit(node.filter)

    def visit_IbLLMExceptionalStmt(self, node: ast.IbLLMExceptionalStmt):
        """递归收集包装节点内的符号"""
        self.visit(node.primary)
        for stmt in node.fallback:
            self.visit(stmt)

class LocalSymbolCollector:
    """
    第二点五阶段：局部符号收集 (Pass 2.5)
    在进入具体作用域分析前，预先扫描该作用域及其嵌套块中的显式定义和全局引用。
    """
    def __init__(self, symbol_table: SymbolTable, analyzer: 'SemanticAnalyzer'):
        self.symbol_table = symbol_table
        self.analyzer = analyzer # 期望是 SemanticAnalyzer 实例

    def collect(self, body: list):
        for stmt in body:
            self.visit(stmt)

    def visit(self, node: ast.IbASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode):
        # [AUDIT] 作用域隔离：基于节点自声明属性进行过滤，不再硬编码黑名单
        if node.creates_scope and not isinstance(node, ast.IbModule):
            return

        # 递归遍历所有可能包含代码块的属性
        for attr in ("body", "orelse", "finalbody"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.visit(item)

    def _define(self, sym: VariableSymbol, node: ast.IbASTNode):
        try:
            # [LIFECYCLE] 符号生命周期管理
            existing = self.symbol_table.symbols.get(sym.name)
            allow_overwrite = False
            if existing and existing.type_info.name in ("Any", "var"):
                allow_overwrite = True
            
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            # [NEW Phase 5] 记录侧表映射
            if hasattr(self.analyzer, "node_to_symbol"):
                self.analyzer.node_to_symbol[node] = sym
        except ValueError as e:
            self.analyzer.error(str(e), node)

    def visit_IbGlobalStmt(self, node: ast.IbGlobalStmt):
        # 处理 global 声明
        self.analyzer.visit_IbGlobalStmt(node)

    def visit_IbLLMExceptionalStmt(self, node: ast.IbLLMExceptionalStmt):
        """预扫描包装节点内的符号"""
        self.visit(node.primary)
        for stmt in node.fallback:
            self.visit(stmt)

    def visit_IbAssign(self, node: ast.IbAssign):
        # 仅收集带有类型标注的显式定义
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 检查该 target 是否被 TypeAnnotatedExpr 包装
            is_explicit = False
            declared_type = STATIC_ANY
            
            for t in node.targets:
                if isinstance(t, ast.IbTypeAnnotatedExpr) and isinstance(t.target, ast.IbName) and t.target.id == name:
                    is_explicit = True
                    declared_type = self.analyzer._resolve_type(t.annotation, safe=True)
                    break
            
            if is_explicit:
                # [LIFECYCLE] 符号生命周期：如果该符号已在 Pass 2 中决议为具体类型，则跳过
                existing = self.symbol_table.symbols.get(name)
                if existing and existing.type_info.name not in ("Any", "var"):
                    continue

                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=declared_type, def_node=node)
                self._define(sym, target) # 绑定 target 节点

    def visit_IbFor(self, node: ast.IbFor):
        # 预扫描 For 循环的迭代变量
        for name, target in SymbolExtractor.get_assigned_names(node):
            sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=STATIC_ANY, def_node=node)
            self._define(sym, target) # 绑定 target 节点
        self.generic_visit(node)

    def visit_IbTry(self, node: ast.IbTry):
        # 预扫描异常处理器中的变量
        for handler in node.handlers:
            for name, target in SymbolExtractor.get_assigned_names(handler):
                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=STATIC_ANY, def_node=handler)
                self._define(sym, target) # 绑定 target 节点
            self.visit(handler)
        self.generic_visit(node)

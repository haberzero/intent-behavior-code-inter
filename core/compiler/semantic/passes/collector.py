from typing import Optional, Any, List, Tuple
from core.compiler.support.diagnostics import DiagnosticReporter
from core.domain import ast as ast
from core.domain.symbols import Symbol, SymbolTable, TypeSymbol, FunctionSymbol, VariableSymbol, SymbolKind, STATIC_ANY

class SymbolExtractor:
    """
    符号提取器：统一从 AST 节点中提取定义的符号名。
    实现逻辑归一化，确保 Pass 2.5 与 Pass 3 行为一致。
    """
    @staticmethod
    def get_assigned_names(node: ast.ASTNode) -> List[Tuple[str, ast.ASTNode]]:
        """提取赋值语句中的目标名称及对应的节点"""
        results = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    results.append((target.id, target))
                elif isinstance(target, ast.TypeAnnotatedExpr) and isinstance(target.target, ast.Name):
                    results.append((target.target.id, target.target))
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                results.append((node.target.id, node.target))
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                results.append((node.name, node))
        return results

class SymbolCollector:
    """
    第一阶段：符号收集 (Pass 1)
    仅收集顶层符号（类、函数、LLM 函数），不进行类型解析。
    """
    def __init__(self, symbol_table: SymbolTable, analyzer: Any = None, issue_tracker: Optional[DiagnosticReporter] = None):
        self.symbol_table = symbol_table
        self.analyzer = analyzer
        self.issue_tracker = issue_tracker

    def collect(self, node: ast.ASTNode):
        self.visit(node)

    def visit(self, node: ast.ASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.ASTNode):
                        self.visit(item)
            elif isinstance(child, ast.ASTNode):
                self.visit(child)

    def visit_Module(self, node: ast.Module):
        for stmt in node.body:
            self.visit(stmt)

    def _define(self, sym: Symbol, node: ast.ASTNode):
        try:
            self.symbol_table.define(sym)
            # [NEW Phase 5] 记录侧表映射
            if self.analyzer and hasattr(self.analyzer, "node_to_symbol"):
                self.analyzer.node_to_symbol[node.uid] = sym.uid
        except ValueError as e:
            if self.issue_tracker:
                self.issue_tracker.error(str(e), node)
            elif hasattr(self, "analyzer") and self.analyzer:
                self.analyzer.error(str(e), node)
            else:
                # 在 Pass 1 阶段没有 analyzer 或 reporter 时，直接抛出
                raise

    def visit_ClassDef(self, node: ast.ClassDef):
        # 1. 注册类符号
        sym = TypeSymbol(name=node.name, kind=SymbolKind.CLASS, node_uid=node.uid)
        self._define(sym, node)
        
        # 2. 进入类作用域收集成员
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        import uuid
        self.symbol_table.uid = f"scope_{uuid.uuid4().hex[:8]}"
        try:
            for stmt in node.body:
                self.visit(stmt)
            # 记录类作用域
            sym.owned_scope = self.symbol_table
        finally:
            self.symbol_table = old_table

    def visit_FunctionDef(self, node: ast.FunctionDef):
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.FUNCTION, node_uid=node.uid)
        self._define(sym, node)
        
        # 函数内部参数和局部变量暂时不作为全局符号收集，留给分析阶段
        pass

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.LLM_FUNCTION, is_llm=True, node_uid=node.uid)
        self._define(sym, node)

    def visit_Assign(self, node: ast.Assign):
        """
        收集赋值语句产生的符号（类成员变量或全局变量）。
        """
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 避免在 Pass 1 重复定义
            if name not in self.symbol_table.symbols:
                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, node_uid=node.uid)
                self._define(sym, target) # 绑定 target 节点

    def visit_AnnotatedStmt(self, node: ast.AnnotatedStmt):
        """递归收集包装语句内的符号"""
        self.visit(node.stmt)

    def visit_AnnotatedExpr(self, node: ast.AnnotatedExpr):
        """递归收集包装表达式内的符号"""
        self.visit(node.expr)

    def visit_AnnotatedStmt(self, node: ast.AnnotatedStmt):
        """预扫描包装语句内的符号"""
        self.visit(node.stmt)

    def visit_AnnotatedExpr(self, node: ast.AnnotatedExpr):
        """预扫描包装表达式内的符号"""
        self.visit(node.expr)

    def visit_TypeAnnotatedExpr(self, node: ast.TypeAnnotatedExpr):
        """预扫描带类型标注的表达式"""
        self.visit(node.target)

    def visit_FilteredExpr(self, node: ast.FilteredExpr):
        """预扫描带过滤条件的表达式"""
        self.visit(node.expr)
        self.visit(node.filter)

    def visit_LLMExceptionalStmt(self, node: ast.LLMExceptionalStmt):
        """递归收集包装节点内的符号"""
        self.visit(node.primary)
        for stmt in node.fallback:
            self.visit(stmt)

class LocalSymbolCollector:
    """
    第二点五阶段：局部符号收集 (Pass 2.5)
    在进入具体作用域分析前，预先扫描该作用域及其嵌套块中的显式定义和全局引用。
    """
    def __init__(self, symbol_table: SymbolTable, analyzer: Any):
        self.symbol_table = symbol_table
        self.analyzer = analyzer # 期望是 SemanticAnalyzer 实例

    def collect(self, body: list):
        for stmt in body:
            self.visit(stmt)

    def visit(self, node: ast.ASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        # [AUDIT] 作用域隔离：基于节点自声明属性进行过滤，不再硬编码黑名单
        if node.creates_scope and not isinstance(node, ast.Module):
            return

        # 递归遍历所有可能包含代码块的属性
        for attr in ("body", "orelse", "finalbody"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.ASTNode):
                        self.visit(item)

    def _define(self, sym: VariableSymbol, node: ast.ASTNode):
        try:
            # [LIFECYCLE] 符号生命周期管理
            existing = self.symbol_table.symbols.get(sym.name)
            allow_overwrite = False
            if existing and existing.type_info.name in ("Any", "var"):
                allow_overwrite = True
            
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            # [NEW Phase 5] 记录侧表映射
            if hasattr(self.analyzer, "node_to_symbol"):
                self.analyzer.node_to_symbol[node.uid] = sym.uid
        except ValueError as e:
            self.analyzer.error(str(e), node)

    def visit_GlobalStmt(self, node: ast.GlobalStmt):
        # 处理 global 声明
        self.analyzer.visit_GlobalStmt(node)

    def visit_LLMExceptionalStmt(self, node: ast.LLMExceptionalStmt):
        """预扫描包装节点内的符号"""
        self.visit(node.primary)
        for stmt in node.fallback:
            self.visit(stmt)

    def visit_Assign(self, node: ast.Assign):
        # 仅收集带有类型标注的显式定义
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 检查该 target 是否被 TypeAnnotatedExpr 包装
            is_explicit = False
            declared_type = STATIC_ANY
            
            for t in node.targets:
                if isinstance(t, ast.TypeAnnotatedExpr) and isinstance(t.target, ast.Name) and t.target.id == name:
                    is_explicit = True
                    declared_type = self.analyzer._resolve_type(t.annotation, safe=True)
                    break
            
            if is_explicit:
                # [LIFECYCLE] 符号生命周期：如果该符号已在 Pass 2 中决议为具体类型，则跳过
                existing = self.symbol_table.symbols.get(name)
                if existing and existing.type_info.name not in ("Any", "var"):
                    continue

                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=declared_type, node_uid=node.uid)
                self._define(sym, target) # 绑定 target 节点

    def visit_For(self, node: ast.For):
        # 预扫描 For 循环的迭代变量
        for name, target in SymbolExtractor.get_assigned_names(node):
            sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=STATIC_ANY, node_uid=node.uid)
            self._define(sym, target) # 绑定 target 节点
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        # 预扫描异常处理器中的变量
        for handler in node.handlers:
            for name, target in SymbolExtractor.get_assigned_names(handler):
                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=STATIC_ANY, node_uid=handler.uid)
                self._define(sym, target) # 绑定 target 节点
            self.visit(handler)
        self.generic_visit(node)

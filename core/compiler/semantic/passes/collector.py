from typing import Optional, Any, List, Tuple, TYPE_CHECKING
from core.compiler.common.diagnostics import DiagnosticReporter
from core.kernel import ast as ast
from core.kernel.symbols import Symbol, SymbolTable, TypeSymbol, FunctionSymbol, VariableSymbol, SymbolKind
from core.kernel.spec import IbSpec, ClassSpec

if TYPE_CHECKING:
    from .semantic_analyzer import SemanticAnalyzer

class SymbolExtractor:
    """
    符号提取器：统一从 AST 节点中提取定义的符号名。
    实现逻辑归一化，确保 Pass 2.5 与 Pass 3 行为一致。
    """
    @staticmethod
    def get_assigned_names(node: ast.IbASTNode) -> List[Tuple[str, ast.IbASTNode]]:
        """提取赋值或迭代语句中的目标名称及对应的节点"""
        results = []
        
        def _extract(target: ast.IbASTNode):
            if isinstance(target, ast.IbName):
                results.append((target.id, target))
            elif isinstance(target, ast.IbTypeAnnotatedExpr):
                # 如果是带类型的表达式，我们同时记录外部节点和内部节点
                # 外部节点用于语义分析器获取 annotation
                # 内部节点用于解析器/解释器识别标识符
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
            # 记录侧表映射
            if self.analyzer and hasattr(self.analyzer, "node_to_symbol"):
                self.analyzer.node_to_symbol[node] = sym
            
            # [Axiom Hook] 同步到描述符的成员表中 (保持物理隔离下的元数据完备性)
            # 如果当前在类作用域内，且定义的不是类本身
            if self.analyzer and self.analyzer.current_class:
                if sym.kind in (SymbolKind.FUNCTION, SymbolKind.LLM_FUNCTION):
                    from core.kernel.spec.member import MethodMemberSpec
                    llm_kind = "llm_method" if sym.kind == SymbolKind.LLM_FUNCTION else "method"
                    self.analyzer.current_class.members[sym.name] = MethodMemberSpec(
                        name=sym.name,
                        kind=llm_kind,
                        type_name=sym.spec.name if sym.spec else "any",
                    )
                else:
                    from core.kernel.spec.member import MemberSpec
                    self.analyzer.current_class.members[sym.name] = MemberSpec(
                        name=sym.name,
                        kind="field",
                        type_name=sym.spec.name if sym.spec else "any",
                    )
                
        except ValueError as e:
            if self.issue_tracker:
                self.issue_tracker.error(str(e), node, code="SEM_002")
            elif hasattr(self, "analyzer") and self.analyzer:
                self.analyzer.error(str(e), node, code="SEM_002")
            else:
                # 在 Pass 1 阶段没有 analyzer 或 reporter 时，直接抛出
                raise

    def visit_IbClassDef(self, node: ast.IbClassDef):
        # 1. 创建类元数据并注册
        cls_meta = self.analyzer.registry.factory.create_class(name=node.name, parent_name=node.parent)
        cls_meta.is_user_defined = True
        
        # [Enum Hook] 如果类继承 Enum，则将 axiom_name 设置为 "enum"
        # 这样 hydrator 会注入 EnumAxiom，实现动态 __prompt__ 协议
        if node.parent == "Enum":
            cls_meta._axiom_name = "enum"
        
        # register() 返回的是注册表中实际存储的 spec（可能是 clone），
        # 后续所有操作必须使用 registered_meta 而非原始 cls_meta，
        # 否则成员注册会写入原始对象，导致注册表中的 clone 缺少成员信息，
        # 从而破坏继承链中父类成员的查找（resolve_member）。
        registered_meta = self.analyzer.registry.register(cls_meta)
        
        # 2. 注册类符号（使用注册表中的 spec）
        sym = TypeSymbol(name=node.name, kind=SymbolKind.CLASS, def_node=node, spec=registered_meta)
        self._define(sym, node)
        
        # 3. 进入类作用域收集成员
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table, name=node.name)
        
        old_class = self.analyzer.current_class
        self.analyzer.current_class = registered_meta
        
        try:
            for stmt in node.body:
                self.visit(stmt)
            # 记录类作用域
            sym.owned_scope = self.symbol_table
        finally:
            self.analyzer.current_class = old_class
            self.symbol_table = old_table

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        # 1. 创建函数元数据 (暂定为 Any -> Any)
        func_meta = self.analyzer.registry.factory.create_func(name=node.name, param_type_names=[], return_type_name="any")
        func_meta.is_user_defined = True
        self.analyzer.registry.register(func_meta)
        
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.FUNCTION, def_node=node, spec=func_meta)
        self._define(sym, node)
        # 局部作用域由 SemanticAnalyzer.visit_IbFunctionDef 处理

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        # 1. 创建函数元数据
        func_meta = self.analyzer.registry.factory.create_func(name=node.name, param_type_names=[], return_type_name="any")
        func_meta.is_user_defined = True
        self.analyzer.registry.register(func_meta)
        
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.LLM_FUNCTION, def_node=node, spec=func_meta)
        sym.metadata["is_llm"] = True
        self._define(sym, node)

    def visit_IbAssign(self, node: ast.IbAssign):
        """
        收集赋值语句产生的符号（类成员变量或全局变量）。
        """
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 避免在 Pass 1 重复定义
            if name not in self.symbol_table.symbols:
                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, def_node=node, spec=self.analyzer._any_desc if self.analyzer else None)
                self._define(sym, target) # 绑定 target 节点
        
        # 递归扫描回退块中的符号 (虽然赋值回退块通常不含类/函数定义)
        self.generic_visit(node)

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """预扫描带类型标注的表达式"""
        self.visit(node.target)

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """预扫描带过滤条件的表达式"""
        self.visit(node.expr)
        self.visit(node.filter)

class LocalSymbolCollector:
    """
    第二点五阶段：局部符号收集 (Pass 2.5)
    在进入具体作用域分析前，预先扫描该作用域及其嵌套块中的显式定义和全局引用。
    """
    def __init__(self, symbol_table: SymbolTable, analyzer: 'SemanticAnalyzer'):
        self.symbol_table = symbol_table
        self.analyzer = analyzer # 期望是 SemanticAnalyzer 实例

    def collect(self, body: list):
        # Pre-pass: 预先注册所有 global 声明，确保 global_refs 在处理赋值时已填充。
        # 这使得 'global x' 的效果对整个函数体有效，无论声明位置在赋值之前还是之后。
        self._prescan_globals(body)
        # Main pass
        for stmt in body:
            self.visit(stmt)

    def _prescan_globals(self, body: list):
        """递归预扫描 global 声明（不跨越作用域边界）。"""
        for stmt in body:
            if isinstance(stmt, ast.IbGlobalStmt):
                self.visit_IbGlobalStmt(stmt)
            elif not (stmt.creates_scope and not isinstance(stmt, ast.IbModule)):
                for attr in ("body", "orelse", "finalbody"):
                    child = getattr(stmt, attr, None)
                    if isinstance(child, list):
                        self._prescan_globals(child)

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
            # 如果现有符号是 any/auto 占位符，允许覆盖，消除名称硬编码
            if existing and (not existing.spec or self.analyzer.registry.is_dynamic(existing.spec)):
                allow_overwrite = True
            
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            # 记录侧表映射
            if hasattr(self.analyzer, "node_to_symbol"):
                self.analyzer.node_to_symbol[node] = sym
        except ValueError as e:
            self.analyzer.error(str(e), node, code="SEM_002")

    def visit_IbGlobalStmt(self, node: ast.IbGlobalStmt):
        # 处理 global 声明（幂等：pre-scan 和 main pass 均可调用）
        self.analyzer.visit_IbGlobalStmt(node)

    def visit_IbAssign(self, node: ast.IbAssign):
        # 仅收集带有类型标注的显式定义
        for name, target in SymbolExtractor.get_assigned_names(node):
            # global 声明：该名称已声明为全局变量，不在本地作用域中创建符号。
            # 将赋值目标节点绑定到全局符号，以确保运行时通过 UID 写入全局作用域。
            if name in self.symbol_table.global_refs:
                global_scope = self.symbol_table.get_global_scope()
                global_sym = global_scope.symbols.get(name)
                if global_sym and hasattr(self.analyzer, "node_to_symbol"):
                    self.analyzer.node_to_symbol[target] = global_sym
                continue

            # 检查该 target 是否被 TypeAnnotatedExpr 包装
            is_explicit = False
            declared_type = self.analyzer._any_desc
            
            for t in node.targets:
                if isinstance(t, ast.IbTypeAnnotatedExpr) and isinstance(t.target, ast.IbName) and t.target.id == name:
                    is_explicit = True
                    # analyzer._resolve_type now returns TypeDescriptor
                    declared_type = self.analyzer._resolve_type(t.annotation, safe=True)
                    break
            
            if is_explicit:
                # [LIFECYCLE] 符号生命周期：如果该符号已在 Pass 2 中决议为具体类型，则跳过
                existing = self.symbol_table.symbols.get(name)
                # 使用 is_dynamic 判定，消除硬编码
                if existing and existing.spec and not self.analyzer.registry.is_dynamic(existing.spec):
                    continue

                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=declared_type, def_node=node)
                self._define(sym, target) # 绑定 target 节点
        
        # 递归扫描回退块中的局部定义 (Pass 2.5)
        self.generic_visit(node)

    def visit_IbFor(self, node: ast.IbFor):
        # 预扫描 For 循环的迭代变量
        for name, target in SymbolExtractor.get_assigned_names(node):
            sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=self.analyzer._any_desc, def_node=node)
            self._define(sym, target) # 绑定 target 节点
        self.generic_visit(node)

    def visit_IbTry(self, node: ast.IbTry):
        # 预扫描异常处理器中的变量
        for handler in node.handlers:
            for name, target in SymbolExtractor.get_assigned_names(handler):
                sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=self.analyzer._any_desc, def_node=handler)
                self._define(sym, target) # 绑定 target 节点
            self.visit(handler)
        self.generic_visit(node)

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """Known Limit 2 修复：预扫描嵌套函数定义，使其在外围作用域中可见。
        
        只在当前作用域中该名称未被定义时注册（避免与 Pass 1 中已注册的顶层函数冲突）。
        """
        # 如果已在当前作用域（或父作用域）中定义，则跳过（由 Pass 1 SymbolCollector 负责）
        existing = self.symbol_table.symbols.get(node.name)
        if existing:
            return
        
        # 创建函数元数据并注册到 SpecRegistry
        func_meta = self.analyzer.registry.factory.create_func(
            name=node.name, param_type_names=[], return_type_name="any"
        )
        func_meta.is_user_defined = True
        self.analyzer.registry.register(func_meta)
        
        # 将嵌套函数注册为当前作用域的符号
        sym = FunctionSymbol(name=node.name, kind=SymbolKind.FUNCTION, def_node=node, spec=func_meta)
        self._define(sym, node)
        # 不递归进入函数体（函数体的局部符号由 SemanticAnalyzer.visit_IbFunctionDef 负责）

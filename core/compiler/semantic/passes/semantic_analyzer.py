from typing import Dict, Optional, List, Any
from core.domain import ast as ast
from core.compiler.support.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.foundation.host_interface import HostInterface

from core.domain import symbols
from core.domain.symbols import (
    SymbolTable, SymbolKind, TypeSymbol, FunctionSymbol, VariableSymbol, 
    StaticType, FunctionType, ClassType, ModuleType, ListType, DictType,
    STATIC_ANY, STATIC_VOID, STATIC_INT, STATIC_STR, STATIC_FLOAT, STATIC_BOOL, STATIC_BEHAVIOR
)
from core.domain.symbols import get_builtin_type
from .prelude import Prelude
from .collector import SymbolCollector, LocalSymbolCollector, SymbolExtractor
from .resolver import TypeResolver
from core.domain.blueprint import CompilationResult

class SemanticAnalyzer:
    """
    语义分析器：执行静态分析和类型检查。
    贯彻“一切皆对象”思想：Analyzer 仅作为调度者，核心逻辑由 Type 对象自决议。
    """
    def __init__(self, issue_tracker: Optional[DiagnosticReporter] = None, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None, registry: Optional[Any] = None):
        self.symbol_table = SymbolTable() # 全局静态符号表
        self.issue_tracker = issue_tracker or IssueTrackerAdapter(IssueTracker())
        self.host_interface = host_interface
        self.debugger = debugger or core_debugger
        self.registry = registry # [NEW] 注册表上下文
        self.current_return_type: Optional[StaticType] = None
        self.current_class: Optional[ClassType] = None
        self.in_behavior_expr = False
        self.scene_stack = [ast.IbScene.GENERAL] # 场景上下文栈
        self.node_scenes: Dict[ast.IbASTNode, ast.IbScene] = {} # 侧表：节点 ID -> 场景
        self.node_to_symbol: Dict[ast.IbASTNode, symbols.Symbol] = {} # 侧表：节点 -> 符号
        self.node_to_type: Dict[ast.IbASTNode, str] = {} # 侧表：节点 ID -> 类型名称
        self.node_is_deferred: Dict[ast.IbASTNode, bool] = {} # 侧表：行为描述行是否延迟执行 (Lambda)

    def _init_builtins(self):
        """注册内置静态符号"""
        prelude = Prelude(self.host_interface, registry=self.registry)
        
        # 1. 注册内置函数
        for name, func_type in prelude.get_builtins().items():
            sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, type_signature=func_type, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 2. 注册内置类型
        for name, type_info in prelude.get_builtin_types().items():
            sym = TypeSymbol(name=name, kind=SymbolKind.BUILTIN_TYPE, static_type=type_info, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 3. 注册内置模块 (如果 Registry 中存在)
        for name, mod_type in prelude.get_builtin_modules().items():
            sym = symbols.VariableSymbol(name=name, kind=SymbolKind.MODULE, var_type=mod_type, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

    def analyze(self, node: ast.IbASTNode) -> CompilationResult:
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Starting static semantic analysis...")
        
        # 初始化内置符号
        self._init_builtins()
            
        # --- 多轮分析 (Multi-Pass) ---
        
        # Pass 1: 收集符号 (Classes, Functions)
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Pass 1: Collecting static symbols...")
        collector = SymbolCollector(self.symbol_table, self, self.issue_tracker)
        collector.collect(node)
        
        # Pass 2: 类型决议 (Inheritance, Signatures)
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Pass 2: Resolving static types...")
        resolver = TypeResolver(self.symbol_table, self)
        resolver.resolve(node)
        
        # Pass 3: 深度语义检查 (Body, Expressions, Type Checking)
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Pass 3: Deep checking...")
        self.visit(node)
        
        # [NEW Phase 5] 自检校验：确保侧表完整性
        # 仅在没有收集到错误的情况下执行完整性检查，因为解析失败的节点本身就无法绑定
        if not self.issue_tracker.has_errors():
            self._validate_integrity(node)
        
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Static analysis complete.")
        self.issue_tracker.check_errors()

        return CompilationResult(
            module_ast=node if isinstance(node, ast.IbModule) else None,
            symbol_table=self.symbol_table,
            node_scenes=self.node_scenes,
            node_to_symbol=self.node_to_symbol,
            node_to_type=self.node_to_type,
            node_is_deferred=self.node_is_deferred
        )

    def visit(self, node: ast.IbASTNode) -> StaticType:
        # [NEW] 记录场景上下文侧表
        if isinstance(node, ast.IbExpr):
            self.node_scenes[node] = self.scene_stack[-1]

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        res_type = visitor(node)
        
        # [NEW Phase 5] 记录类型推导侧表
        if isinstance(node, ast.IbExpr) and res_type:
            self.node_to_type[node] = res_type.prompt_name
            
        return res_type

    def generic_visit(self, node: ast.IbASTNode) -> StaticType:
        """
        [AUDIT] 严格访问模式：对于未明确处理的节点，不再静默返回 Any。
        """
        # 允许某些辅助节点（如 arg, alias）被跳过
        if isinstance(node, (ast.IbArg, ast.IbAlias)):
            return STATIC_ANY
            
        self.error(f"Internal compiler error: Unhandled AST node type '{node.__class__.__name__}'", node, code="INTERNAL_ERROR")
        return STATIC_ANY

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000", hint: Optional[str] = None):
        self.issue_tracker.error(message, node, code=code, hint=hint)

    def _visit_llmexcept(self, fallback: Optional[List[ast.IbStmt]]):
        """访问 llmexcept (llm_fallback) 块"""
        if fallback:
            # [Pass 2.5] 使用独立的 LocalSymbolCollector 进行预扫描
            LocalSymbolCollector(self.symbol_table, self).collect(fallback)
            for stmt in fallback:
                self.visit(stmt)

    # --- 访问者实现 ---

    def visit_IbModule(self, node: ast.IbModule):
        # [Pass 2.5] 预扫描模块作用域
        LocalSymbolCollector(self.symbol_table, self).collect(node.body)
        for stmt in node.body:
            self.visit(stmt)

    def visit_IbGlobalStmt(self, node: ast.IbGlobalStmt):
        if self.symbol_table.parent is None:
            self.error("Global declaration is not allowed in global scope", node, code="SEM_004")
            return
        
        for name in node.names:
            global_scope = self.symbol_table.get_global_scope()
            if name not in global_scope.symbols:
                self.error(f"Global variable '{name}' is not defined in global scope", node, code="SEM_001")
            else:
                self.symbol_table.add_global_ref(name)

    def visit_IbClassDef(self, node: ast.IbClassDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not isinstance(sym, symbols.TypeSymbol):
            return
            
        self.node_to_symbol[node] = sym
        
        old_table = self.symbol_table
        if sym.owned_scope:
            self.symbol_table = sym.owned_scope
            
        old_class = self.current_class
        self.current_class = sym.static_type
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.current_class = old_class
            self.symbol_table = old_table

    def _define_var(self, name: str, var_type: StaticType, node: ast.IbASTNode, allow_overwrite: bool = False):
        try:
            # [NEW] 如果符号已由 Scheduler 注入（如模块导入），则不再重新定义，仅绑定 UID
            existing = self.symbol_table.resolve(name)
            if existing:
                # 检查是否已在当前作用域定义
                if name in self.symbol_table.symbols:
                    if not allow_overwrite:
                        self.node_to_symbol[node] = existing
                        return existing
                else:
                    # 如果是全局变量在局部同名定义，这是 shadowing，允许
                    if existing.kind == SymbolKind.VARIABLE and any(existing is s for s in self.symbol_table.get_global_scope().symbols.values()):
                        pass # Shadowing is allowed
                    elif not allow_overwrite:
                        self.node_to_symbol[node] = existing
                        return existing

            sym = symbols.VariableSymbol(name=name, kind=symbols.SymbolKind.VARIABLE, var_type=var_type, def_node=node)
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            # [NEW Phase 5] 记录侧表映射
            self.node_to_symbol[node] = sym
            return sym
        except ValueError as e:
            self.error(str(e), node, code="SEM_003")
            return None

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if sym:
            self.node_to_symbol[node] = sym
            
        ret_type = sym.return_type if isinstance(sym, symbols.FunctionSymbol) else STATIC_VOID
        
        # 进入局部作用域
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table)
        self.symbol_table = local_scope
        
        # [NEW Phase 5] 将局部作用域回填到符号中，以便序列化器能够递归发现局部符号
        if isinstance(sym, symbols.FunctionSymbol):
            sym.owned_scope = local_scope
        
        # [NEW] 隐式 self 注入：如果是类方法，在局部作用域注入 self 符号
        if self.current_class:
            self._define_var("self", self.current_class, node)

        # 注册参数
        for i, arg_node in enumerate(node.args):
            # 索引偏移：类方法的签名中包含隐含的 self
            sig_idx = i + 1 if self.current_class else i
            arg_type = sym.param_types[sig_idx] if (isinstance(sym, symbols.FunctionSymbol) and sig_idx < len(sym.param_types)) else STATIC_ANY
            
            # 获取参数名节点
            name_node = arg_node
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                name_node = arg_node.target
            
            if isinstance(name_node, ast.IbArg):
                self._define_var(name_node.arg, arg_type, name_node)
            elif isinstance(name_node, ast.IbName):
                self._define_var(name_node.id, arg_type, name_node)
            
        # [Pass 2.5] 预扫描局部作用域
        LocalSymbolCollector(self.symbol_table, self).collect(node.body)

        old_ret = self.current_return_type
        self.current_return_type = ret_type
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.current_return_type = old_ret
            self.symbol_table = old_table

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if sym:
            self.node_to_symbol[node] = sym
            
        # 进入局部作用域以校验提示词中的占位符
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table)
        self.symbol_table = local_scope
        
        # [NEW Phase 5] 将局部作用域回填到符号中，以便序列化器能够递归发现局部符号
        if isinstance(sym, symbols.FunctionSymbol):
            sym.owned_scope = local_scope
        
        if self.current_class:
            self._define_var("self", self.current_class, node)
            
        for i, arg_node in enumerate(node.args):
            sig_idx = i + 1 if self.current_class else i
            arg_type = sym.param_types[sig_idx] if (isinstance(sym, symbols.FunctionSymbol) and sig_idx < len(sym.param_types)) else STATIC_ANY
            
            # 获取参数名节点
            name_node = arg_node
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                name_node = arg_node.target
            
            if isinstance(name_node, ast.IbArg):
                self._define_var(name_node.arg, arg_type, name_node)
            elif isinstance(name_node, ast.IbName):
                self._define_var(name_node.id, arg_type, name_node)
            
        # [Pass 2.5] 预扫描局部作用域（LLM 函数虽然没有标准 body，但其 prompt 中可能涉及变量引用）
        # 这里的预扫描主要是为了兼容未来可能在 LLM 函数中增加的局部定义
        # 注意：LLM 函数没有常规 body，这里暂不执行 collect，除非未来规范支持
        
        try:
            # 校验提示词段落中的表达式
            if node.sys_prompt:
                for segment in node.sys_prompt:
                    if isinstance(segment, ast.IbASTNode):
                        self.visit(segment)
            if node.user_prompt:
                for segment in node.user_prompt:
                    if isinstance(segment, ast.IbASTNode):
                        self.visit(segment)
        finally:
            self.symbol_table = old_table

    def visit_IbReturn(self, node: ast.IbReturn):
        if node.value:
            ret_type = self.visit(node.value)
            if self.current_return_type and not ret_type.is_assignable_to(self.current_return_type):
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got '{ret_type.name}'", node, code="SEM_003")
        else:
            if self.current_return_type and self.current_return_type != STATIC_VOID:
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got 'void'", node, code="SEM_003")

    def visit_IbAssign(self, node: ast.IbAssign):
        # 1. 预先计算右值类型，避免在循环中重复 visit
        val_type = self.visit(node.value) if node.value else STATIC_ANY
        
        # 2. 提取所有赋值目标中的变量名
        assigned_names = SymbolExtractor.get_assigned_names(node)
        
        # 3. 遍历所有 target 节点进行语义检查
        for target_node in node.targets:
            var_name = None
            declared_type = None
            sym = None
            actual_target = target_node
            
            if isinstance(target_node, ast.IbTypeAnnotatedExpr):
                declared_type = self._resolve_type(target_node.annotation)
                if isinstance(target_node.target, ast.IbName):
                    var_name = target_node.target.id
            elif isinstance(target_node, ast.IbName):
                var_name = target_node.id
            
            if var_name:
                # 处理变量赋值/声明
                if declared_type:
                    # 显式类型标注：检查是否冲突
                    if var_name in self.symbol_table.global_refs:
                        self.error(f"Cannot redeclare global variable '{var_name}' with type annotation", node, code="SEM_002")
                    
                    sym = self.symbol_table.symbols.get(var_name)
                    if not sym or sym.type_info.name in ("Any", "var"):
                        target_type = declared_type if declared_type.name not in ("var", "Any") else val_type
                        sym = symbols.VariableSymbol(name=var_name, kind=symbols.SymbolKind.VARIABLE, var_type=target_type, def_node=node)
                        try:
                            self.symbol_table.define(sym, allow_overwrite=True)
                        except ValueError as e:
                            self.error(str(e), node, code="SEM_002")
                
                if not sym:
                    # 无标注赋值或已存在符号
                    if var_name in self.symbol_table.global_refs:
                        global_scope = self.symbol_table.get_global_scope()
                        sym = global_scope.resolve(var_name)
                    else:
                        sym = self.symbol_table.symbols.get(var_name)
                        if not sym or sym.type_info.name in ("Any", "var"):
                            sym = self._define_var(var_name, val_type, node, allow_overwrite=(sym is not None))

                if sym:
                    self.node_to_symbol[actual_target] = sym
                    if isinstance(target_node, ast.IbTypeAnnotatedExpr) and isinstance(target_node.target, ast.IbName):
                        self.node_to_symbol[target_node.target] = sym
                    
                    # [NEW] 行为描述行 Lambda 化判断
                    if isinstance(node.value, ast.IbBehaviorExpr) and sym.type_info.is_callable:
                        self.node_is_deferred[node.value] = True
                    
                    if not val_type.is_assignable_to(sym.type_info):
                        self.error(f"Type mismatch: Cannot assign '{val_type.name}' to '{sym.type_info.name}'", node, code="SEM_003")
            else:
                # 处理属性或下标赋值 (e.g., p.val = 1)
                target_type = self.visit(target_node)
                if target_type and not val_type.is_assignable_to(target_type):
                    self.error(f"Type mismatch: Cannot assign '{val_type.name}' to target of type '{target_type.name}'", node, code="SEM_003")

    def visit_IbIf(self, node: ast.IbIf):
        self.scene_stack.append(ast.IbScene.BRANCH)
        try:
            self.visit(node.test)
            for stmt in node.body:
                self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)
        finally:
            self.scene_stack.pop()

    def visit_IbWhile(self, node: ast.IbWhile):
        self.scene_stack.append(ast.IbScene.LOOP)
        try:
            self.visit(node.test)
            for stmt in node.body:
                self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)
        finally:
            self.scene_stack.pop()

    def visit_IbFor(self, node: ast.IbFor):
        self.scene_stack.append(ast.IbScene.LOOP)
        try:
            iter_type = self.visit(node.iter)
            # 贯彻“一切皆对象”协议：询问类型如何提供迭代元素
            element_type = iter_type.get_iterator_type()
            
            for var_name, target in SymbolExtractor.get_assigned_names(node):
                # 检查是否已在 Pass 2.5 预扫描中定义
                sym = self.symbol_table.symbols.get(var_name)
                # 如果未定义，或者定义为 Any/var 占位符，则更新其类型
                if not sym or sym.type_info.name in ("Any", "var"):
                    sym = self._define_var(var_name, element_type, node, allow_overwrite=(sym is not None))
                else:
                    # 显式定义的变量（如带有类型标注），则执行类型更新
                    sym.var_type = element_type
                
                if sym:
                    self.node_to_symbol[target] = sym # [FIX] 同步 UID
            
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.scene_stack.pop()

    def visit_IbExprStmt(self, node: ast.IbExprStmt):
        return self.visit(node.value)

    def visit_IbAugAssign(self, node: ast.IbAugAssign):
        self.visit(node.target)
        self.visit(node.value)

    def visit_IbTry(self, node: ast.IbTry):
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_IbExceptHandler(self, node: ast.IbExceptHandler):
        if node.type:
            self.visit(node.type)
        for var_name, target in SymbolExtractor.get_assigned_names(node):
            # 检查是否已在 Pass 2.5 预扫描中定义
            sym = self.symbol_table.symbols.get(var_name)
            if not sym or sym.type_info.name in ("Any", "var"):
                sym = self._define_var(var_name, STATIC_ANY, node, allow_overwrite=(sym is not None))
            
            if sym:
                self.node_to_symbol[target] = sym # [AUDIT] 补全异常变量的 UID 绑定
            # 简单起见，暂时将异常变量视为 Any
        
        for stmt in node.body:
            self.visit(stmt)

    def visit_IbPass(self, node: ast.IbPass):
        return STATIC_VOID

    def visit_IbBreak(self, node: ast.IbBreak):
        return STATIC_VOID

    def visit_IbContinue(self, node: ast.IbContinue):
        return STATIC_VOID

    def visit_IbImport(self, node: ast.IbImport):
        # 在符号表中定义导入的名称
        for alias in node.names:
            name = alias.asname or alias.name
            # 定义为变量，类型为 Any (暂时不支持跨模块成员类型推导)
            sym = self._define_var(name, STATIC_ANY, node)
            if sym:
                sym.metadata["is_builtin"] = True
        return STATIC_VOID

    def visit_IbImportFrom(self, node: ast.IbImportFrom):
        for alias in node.names:
            if alias.name == '*':
                # import * 逻辑在静态分析阶段暂时跳过
                continue
            name = alias.asname or alias.name
            sym = self._define_var(name, STATIC_ANY, node)
            if sym:
                sym.metadata["is_builtin"] = True
        return STATIC_VOID

    def visit_IbIntentStmt(self, node: ast.IbIntentStmt):
        # 访问意图元数据
        self.visit(node.intent)
        # 访问意图块内部
        for stmt in node.body:
            self.visit(stmt)
        return STATIC_VOID

    def visit_IbAnnotatedStmt(self, node: ast.IbAnnotatedStmt):
        """处理带意图注释的语句包装节点"""
        # [NEW] 显式访问意图节点，确保其进入序列化池
        self.visit(node.intent)
        return self.visit(node.stmt)

    def visit_IbAnnotatedExpr(self, node: ast.IbAnnotatedExpr):
        """处理带意图注释的表达式包装节点"""
        # [NEW] 显式访问意图节点
        self.visit(node.intent)
        return self.visit(node.expr)

    def visit_IbIntentInfo(self, node: ast.IbIntentInfo):
        """访问意图元数据节点"""
        # 如果意图中有动态表达式，需要访问
        if node.expr:
            self.visit(node.expr)
        if node.segments:
            for seg in node.segments:
                if isinstance(seg, ast.IbASTNode):
                    self.visit(seg)
        return STATIC_VOID

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """处理带类型标注的表达式包装节点 (例如 Casts 或声明)"""
        # 1. 解析标注的类型
        annotated_type = self._resolve_type(node.annotation)
        
        # 2. 访问内部表达式并检查类型一致性
        inner_type = self.visit(node.target)
        
        # 如果是显式标注，我们认为结果类型就是标注的类型（类似于 Cast）
        # 但我们需要校验内部表达式是否能被视为该类型
        if not inner_type.is_assignable_to(annotated_type):
            # 注意：在声明阶段，visit_Assign 已经做了更细致的校验，
            # 这里的校验主要针对未来的 Cast 语法：(x as int)
            pass 
            
        return annotated_type

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """处理带过滤条件的表达式包装节点 (e.g., expr if filter)"""
        # 1. 访问被包装的表达式 (例如 While 的 test 或 For 的 iter)
        inner_type = self.visit(node.expr)
        
        # 2. 访问过滤条件，它必须返回布尔值 (或可视为布尔值)
        filter_type = self.visit(node.filter)
        
        # 3. 过滤后，表达式的类型保持不变
        return inner_type

    def visit_IbLLMExceptionalStmt(self, node: ast.IbLLMExceptionalStmt):
        """统一处理 LLM 回退逻辑包装节点"""
        # 1. 访问主语句
        self.visit(node.primary)
        # 2. 访问回退块
        self._visit_llmexcept(node.fallback)
        return STATIC_VOID

    def visit_IbRaise(self, node: ast.IbRaise):
        if node.exc:
            self.visit(node.exc)
        return STATIC_VOID

    def visit_IbRetry(self, node: ast.IbRetry):
        if node.hint:
            self.visit(node.hint)
        return STATIC_VOID

    def visit_IbCompare(self, node: ast.IbCompare) -> StaticType:
        left_type = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right_type = self.visit(comparator)
            res = left_type.get_operator_result(op, right_type)
            if not res:
                self.error(f"Comparison operator '{op}' not supported for types '{left_type.name}' and '{right_type.name}'", node, code="SEM_003")
            # 链式比较中，前一轮的右操作数成为下一轮的左操作数
            left_type = right_type
        
        return STATIC_BOOL

    def visit_IbBoolOp(self, node: ast.IbBoolOp) -> StaticType:
        for val in node.values:
            self.visit(val)
        return STATIC_BOOL

    def visit_IbListExpr(self, node: ast.IbListExpr) -> StaticType:
        element_type = STATIC_ANY
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        
        res = ListType(element_type)
        return res

    def visit_IbDict(self, node: ast.IbDict) -> StaticType:
        key_type = STATIC_ANY
        val_type = STATIC_ANY
        
        if node.keys:
            key_type = self.visit(node.keys[0])
            for key in node.keys[1:]:
                self.visit(key)
        
        if node.values:
            val_type = self.visit(node.values[0])
            for val in node.values[1:]:
                self.visit(val)
                
        return DictType(key_type, val_type)

    def visit_IbSubscript(self, node: ast.IbSubscript) -> StaticType:
        value_type = self.visit(node.value)
        key_type = self.visit(node.slice)
        
        # 贯彻“一切皆对象”协议：询问类型如何处理下标
        if not value_type.is_subscriptable:
            self.error(f"Type '{value_type.name}' is not subscriptable", node, code="SEM_003")
            return STATIC_ANY
            
        res = value_type.get_subscript_type(key_type)
        return res

    def visit_IbCastExpr(self, node: ast.IbCastExpr) -> StaticType:
        """类型强转语义分析"""
        self.visit(node.value)
        # 决议目标类型
        target_type = self.symbol_table.resolve(node.type_name)
        if target_type and isinstance(target_type, symbols.TypeSymbol):
            return target_type.static_type
        return STATIC_ANY

    def visit_IbBinOp(self, node: ast.IbBinOp) -> StaticType:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        
        # 贯彻“一切皆对象”：调用左操作数的自决议方法
        res = left_type.get_operator_result(node.op, right_type)
        if not res:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type.name}' and '{right_type.name}'", node, code="SEM_003")
            return STATIC_ANY
        return res

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp) -> StaticType:
        operand_type = self.visit(node.operand)
        
        # 贯彻“一切皆对象”：调用操作数的自决议方法 (other=None 表示一元运算)
        res = operand_type.get_operator_result(node.op, None)
        if not res:
            self.error(f"Unary operator '{node.op}' not supported for type '{operand_type.name}'", node, code="SEM_003")
            return STATIC_ANY
        return res

    def visit_IbConstant(self, node: ast.IbConstant) -> StaticType:
        val = node.value
        res = STATIC_ANY
        if isinstance(val, bool): res = STATIC_BOOL
        elif isinstance(val, int): res = STATIC_INT
        elif isinstance(val, float): res = STATIC_FLOAT
        elif isinstance(val, str): res = STATIC_STR
        elif val is None: res = STATIC_VOID
        return res

    def visit_IbName(self, node: ast.IbName) -> StaticType:
        # 1. 解析符号
        sym = self.symbol_table.resolve(node.id)
        
        if not sym:
            msg = f"Variable '{node.id}' is not defined"
            if self.in_behavior_expr:
                msg = f"Variable '{node.id}' used in behavior expression is not defined"
            self.error(msg, node, code="SEM_001")
            return STATIC_ANY

        # 2. [AUDIT] 显式全局声明规则优化：
        # - 内置类型、模块、全局函数、全局类允许直接访问（只读/调用）
        # - 全局变量在局部作用域修改或作为普通 Name 访问时，若非上述类型，则需声明 global
        if self.symbol_table.parent is not None:
            global_scope = self.symbol_table.get_global_scope()
            if node.id in global_scope.symbols:
                global_sym = global_scope.symbols[node.id]
                if sym == global_sym:
                    # [FIX] 显式全局声明规则放松：
                    # - 仅在“修改”（赋值）时强制要求 global 声明
                    # - 读取（Name 访问）时允许隐式引用全局变量（符合 Python/IBCI 2.0 习惯）
                    # if not is_safe and node.id not in self.symbol_table.global_refs:
                    #     self.error(f"Global variable '{node.id}' must be declared with 'global' before use in local scope", node, code="SEM_004")
                    #     return STATIC_ANY
                    pass

        self.node_to_symbol[node] = sym # 使用 UID 引用
        
        # 统一获取类型信息，不再需要 isinstance 判断
        res = sym.type_info
            
        return res

    def visit_IbAttribute(self, node: ast.IbAttribute) -> StaticType:
        base_type = self.visit(node.value)
        
        # 贯彻“一切皆对象”：询问类型对象如何解析其成员
        member_sym = base_type.resolve_member(node.attr)
        if member_sym:
            self.node_to_symbol[node] = member_sym
            return member_sym.type_info
            
        self.error(f"Type '{base_type.name}' has no member '{node.attr}'", node, code="SEM_001")
        return STATIC_ANY

    def visit_IbCall(self, node: ast.IbCall) -> StaticType:
        func_type = self.visit(node.func)
        arg_types = [self.visit(arg) for arg in node.args]
        
        # 1. 检查是否可调用 (使用接口属性)
        if not func_type.is_callable:
            self.error(f"Type '{func_type.name}' is not callable", node, code="SEM_003")
            return STATIC_ANY
            
        # 2. 贯彻“一切皆对象”：询问类型对象调用后的返回结果
        res = func_type.get_call_return(arg_types)
        if not res:
            # 如果是可调用类型，提供更详细的错误
            if func_type.name == "callable":
                # 尝试获取更具体的参数不匹配信息
                # 注意：这里我们依然保留了一些对 FunctionType 的具体属性访问，
                # 但不再依赖 isinstance 进行逻辑分支
                param_types = getattr(func_type, 'param_types', [])
                if len(arg_types) != len(param_types):
                    self.error(f"Function expected {len(param_types)} arguments, but got {len(arg_types)}", node, code="SEM_005")
                else:
                    for i, (expected, actual) in enumerate(zip(param_types, arg_types)):
                        if not actual.is_assignable_to(expected):
                            self.error(f"Argument {i+1} type mismatch: expected '{expected.name}', but got '{actual.name}'", node, code="SEM_003")
            else:
                self.error(f"Invalid call to '{func_type.name}'", node, code="SEM_003")
            return STATIC_ANY
            
        return res

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr) -> StaticType:
        self.in_behavior_expr = True
        try:
            for seg in node.segments:
                if isinstance(seg, ast.IbASTNode):
                    self.visit(seg)
        finally:
            self.in_behavior_expr = False
        return STATIC_BEHAVIOR

    def _resolve_type(self, node: Any, safe: bool = False) -> StaticType:
        if isinstance(node, ast.IbName):
            t = get_builtin_type(node.id)
            if t: return t
            sym = self.symbol_table.resolve(node.id)
            if isinstance(sym, symbols.TypeSymbol) and sym.static_type:
                # [NEW Phase 5] 记录类型引用的符号绑定
                self.node_to_symbol[node] = sym
                return sym.static_type
            self.error(f"Unknown type '{node.id}'", node, code="SEM_001")
        elif isinstance(node, ast.IbAttribute):
            # 处理 a.b 形式的类型 (如插件中的类)
            # [AUDIT] 在 safe 模式下（如预扫描阶段），禁止触发 visit()
            if safe:
                # 降级处理：仅支持简单的名称解析，不支持复杂的表达式类型
                if isinstance(node.value, ast.IbName):
                    base_sym = self.symbol_table.resolve(node.value.id)
                    if base_sym and base_sym.type_info:
                        member_sym = base_sym.type_info.resolve_member(node.attr)
                        if member_sym and isinstance(member_sym, symbols.TypeSymbol):
                            # [NEW Phase 5] 记录类型引用的符号绑定
                            self.node_to_symbol[node] = member_sym
                            return member_sym.static_type
                return STATIC_ANY
                
            base_type = self.visit(node.value)
            member_sym = base_type.resolve_member(node.attr)
            if member_sym and isinstance(member_sym, symbols.TypeSymbol) and member_sym.static_type:
                # [NEW Phase 5] 记录类型引用的符号绑定
                self.node_to_symbol[node] = member_sym
                return member_sym.static_type
            self.error(f"Unknown type '{node.attr}' in '{base_type.name}'", node, code="SEM_001")
        return STATIC_ANY

    def _validate_integrity(self, root: ast.IbASTNode):
        """[Phase 5] 语义完整性自检：确保所有引用节点都已绑定到侧表"""
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.DETAIL, "Performing semantic integrity self-check...")
        
        missing_bindings = []
        
        # 定义需要校验的节点集合
        BINDING_REQUIRED = (ast.IbName, ast.IbAttribute, ast.IbFunctionDef, ast.IbClassDef, ast.IbLLMFunctionDef, ast.IbArg)
        
        def check(node: Any):
            if not isinstance(node, ast.IbASTNode):
                return
            
            # 1. 检查符号绑定侧表
            if isinstance(node, BINDING_REQUIRED):
                # 排除内置类型 Name 节点，它们由解析器动态创建，通常不参与符号绑定
                if isinstance(node, ast.IbName) and node.id in ("int", "str", "float", "bool", "Any", "var", "none", "None"):
                    pass
                elif node not in self.node_to_symbol:
                    # 获取更具体的节点标识名
                    node_name = getattr(node, 'id', getattr(node, 'name', getattr(node, 'attr', 'unnamed')))
                    missing_bindings.append(f"{node.__class__.__name__} '{node_name}' (ID: {node})")
            
            # 2. 递归遍历子节点
            for attr in vars(node):
                val = getattr(node, attr)
                if isinstance(val, list):
                    for item in val: check(item)
                elif isinstance(val, ast.IbASTNode):
                    check(val)

        check(root)
        
        # 如果存在缺失，输出警告日志供调试
        if missing_bindings:
            msg = f"Semantic integrity issue: {len(missing_bindings)} node(s) missing symbol bindings in side table"
            # 使用警告级别报告，不阻塞编译，但在诊断输出中可见
            self.issue_tracker.warning(msg, root)
            
            # 详细列表仅输出到调试器
            self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, f"[INTEGRITY WARNING] {msg}:")
            for m in missing_bindings[:10]:
                self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, f"  - {m}")

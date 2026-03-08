from typing import Dict, Optional, List, Any
from core.domain import ast as ast
from core.compiler.support.diagnostics import DiagnosticReporter, DiagnosticSeverity
from core.compiler.support.issue_adapter import IssueTrackerAdapter
from core.support.diagnostics.issue_tracker import IssueTracker
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.support.host_interface import HostInterface

from core.domain import symbols
from core.domain.symbols import (
    SymbolTable, SymbolKind, TypeSymbol, FunctionSymbol, VariableSymbol, 
    StaticType, FunctionType, ClassType, ModuleType,
    STATIC_ANY, STATIC_VOID, STATIC_INT, STATIC_STR, STATIC_FLOAT, STATIC_BOOL, STATIC_BEHAVIOR
)
from core.domain.static_types import get_builtin_type
from .prelude import Prelude
from .collector import SymbolCollector, LocalSymbolCollector, SymbolExtractor
from .resolver import TypeResolver
from ..result import CompilationResult

class SemanticAnalyzer:
    """
    语义分析器：执行静态分析和类型检查。
    贯彻“一切皆对象”思想：Analyzer 仅作为调度者，核心逻辑由 Type 对象自决议。
    """
    def __init__(self, issue_tracker: Optional[DiagnosticReporter] = None, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None):
        self.symbol_table = SymbolTable() # 全局静态符号表
        # [AUDIT] 诊断抽象：使用传入的 reporter 或创建适配器
        self.issue_tracker = issue_tracker or IssueTrackerAdapter(IssueTracker())
        self.host_interface = host_interface
        self.debugger = debugger or core_debugger
        self.current_return_type: Optional[StaticType] = None
        self.current_class: Optional[ClassType] = None
        self.in_behavior_expr = False
        self.scene_stack = [ast.Scene.GENERAL] # 场景上下文栈
        self.node_scenes: Dict[str, ast.Scene] = {} # 侧表：节点 UID -> 场景
        self.node_to_symbol: Dict[str, str] = {} # 侧表：节点 UID -> 符号 UID
        self.node_to_type: Dict[str, str] = {} # 侧表：节点 UID -> 类型名称
        self.node_is_deferred: Dict[str, bool] = {} # 侧表：行为描述行是否延迟执行 (Lambda)

    def _init_builtins(self):
        """注册内置静态符号"""
        prelude = Prelude(self.host_interface)
        
        # 1. 注册内置函数
        for name, func_type in prelude.get_builtins().items():
            sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, type_signature=func_type, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 2. 注册内置类型
        for name, type_info in prelude.get_builtin_types().items():
            sym = TypeSymbol(name=name, kind=SymbolKind.BUILTIN_TYPE, static_type=type_info)
            self.symbol_table.define(sym)

    def analyze(self, node: ast.ASTNode) -> CompilationResult:
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
            module_ast=node if isinstance(node, ast.Module) else None,
            symbol_table=self.symbol_table,
            node_scenes=self.node_scenes,
            node_to_symbol=self.node_to_symbol,
            node_to_type=self.node_to_type,
            node_is_deferred=self.node_is_deferred
        )

    def visit(self, node: ast.ASTNode) -> StaticType:
        # [NEW] 记录场景上下文侧表
        if isinstance(node, ast.Expr):
            self.node_scenes[node.uid] = self.scene_stack[-1]

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        res_type = visitor(node)
        
        # [NEW Phase 5] 记录类型推导侧表
        if isinstance(node, ast.Expr) and res_type:
            self.node_to_type[node.uid] = res_type.name
            
        return res_type

    def generic_visit(self, node: ast.ASTNode) -> StaticType:
        """
        [AUDIT] 严格访问模式：对于未明确处理的节点，不再静默返回 Any。
        """
        # 允许某些辅助节点（如 arg, alias）被跳过
        if isinstance(node, (ast.arg, ast.alias)):
            return STATIC_ANY
            
        self.error(f"Internal compiler error: Unhandled AST node type '{node.__class__.__name__}'", node, code="INTERNAL_ERROR")
        return STATIC_ANY

    def error(self, message: str, node: ast.ASTNode, code: str = "SEMANTIC_ERROR"):
        self.issue_tracker.error(message, node)

    def _visit_llmexcept(self, fallback: Optional[List[ast.Stmt]]):
        """访问 llmexcept (llm_fallback) 块"""
        if fallback:
            # [Pass 2.5] 使用独立的 LocalSymbolCollector 进行预扫描
            LocalSymbolCollector(self.symbol_table, self).collect(fallback)
            for stmt in fallback:
                self.visit(stmt)

    # --- 访问者实现 ---

    def visit_Module(self, node: ast.Module):
        # [Pass 2.5] 预扫描模块作用域
        LocalSymbolCollector(self.symbol_table, self).collect(node.body)
        for stmt in node.body:
            self.visit(stmt)

    def visit_GlobalStmt(self, node: ast.GlobalStmt):
        # 1. 检查是否在全局作用域使用 global
        if self.symbol_table.parent is None:
            self.error("Global declaration is not allowed in global scope", node)
            return

        global_scope = self.symbol_table.get_global_scope()
        for name in node.names:
            # 2. 检查变量是否在全局定义
            sym = global_scope.symbols.get(name)
            if not sym:
                self.error(f"Global variable '{name}' is not defined in global scope", node)
                continue
            
            # 3. 记录到当前作用域的 global_refs
            self.symbol_table.global_refs.add(name)

    def visit_ClassDef(self, node: ast.ClassDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not isinstance(sym, symbols.TypeSymbol):
            return
            
        self.node_to_symbol[node.uid] = sym.uid
        
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

    def _define_var(self, name: str, var_type: StaticType, node: ast.ASTNode, allow_overwrite: bool = False):
        try:
            sym = symbols.VariableSymbol(name=name, kind=symbols.SymbolKind.VARIABLE, var_type=var_type, node_uid=node.uid)
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            # [NEW Phase 5] 记录侧表映射
            self.node_to_symbol[node.uid] = sym.uid
            return sym
        except ValueError as e:
            self.error(str(e), node)
            return None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if sym:
            self.node_to_symbol[node.uid] = sym.uid
            
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
            if isinstance(arg_node, ast.TypeAnnotatedExpr):
                name_node = arg_node.target
            
            if isinstance(name_node, ast.arg):
                self._define_var(name_node.arg, arg_type, name_node)
            elif isinstance(name_node, ast.Name):
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

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if sym:
            self.node_to_symbol[node.uid] = sym.uid
            
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
            if isinstance(arg_node, ast.TypeAnnotatedExpr):
                name_node = arg_node.target
            
            if isinstance(name_node, ast.arg):
                self._define_var(name_node.arg, arg_type, name_node)
            elif isinstance(name_node, ast.Name):
                self._define_var(name_node.id, arg_type, name_node)
            
        # [Pass 2.5] 预扫描局部作用域（LLM 函数虽然没有标准 body，但其 prompt 中可能涉及变量引用）
        # 这里的预扫描主要是为了兼容未来可能在 LLM 函数中增加的局部定义
        # 注意：LLM 函数没有常规 body，这里暂不执行 collect，除非未来规范支持
        
        try:
            # 校验提示词段落中的表达式
            if node.sys_prompt:
                for segment in node.sys_prompt:
                    if isinstance(segment, ast.ASTNode):
                        self.visit(segment)
            if node.user_prompt:
                for segment in node.user_prompt:
                    if isinstance(segment, ast.ASTNode):
                        self.visit(segment)
        finally:
            self.symbol_table = old_table

    def visit_Return(self, node: ast.Return):
        if node.value:
            ret_type = self.visit(node.value)
            if self.current_return_type and not ret_type.is_assignable_to(self.current_return_type):
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got '{ret_type.name}'", node)
        else:
            if self.current_return_type and self.current_return_type != STATIC_VOID:
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got 'void'", node)

    def visit_Assign(self, node: ast.Assign):
        # 1. 提取所有赋值目标中的变量名 (处理 Name 和 TypeAnnotatedExpr)
        assigned_names = SymbolExtractor.get_assigned_names(node)
        
        # 2. 遍历所有 target 节点进行语义检查
        for target_node in node.targets:
            # 获取该 target 对应的变量名（如果有）
            var_name = None
            declared_type = None
            sym = None # [FIX] 初始化，避免跨迭代污染
            actual_target = target_node
            
            if isinstance(target_node, ast.TypeAnnotatedExpr):
                declared_type = self._resolve_type(target_node.annotation)
                if isinstance(target_node.target, ast.Name):
                    var_name = target_node.target.id
            elif isinstance(target_node, ast.Name):
                var_name = target_node.id
            
            if var_name:
                # 处理变量赋值/声明
                if declared_type:
                    # 显式类型标注：局部优先原则
                    if var_name in self.symbol_table.global_refs:
                        self.error(f"Cannot redeclare global variable '{var_name}' with type annotation", node)
                    
                    sym = self.symbol_table.symbols.get(var_name)
                    if not sym or sym.type_info.name in ("Any", "var"):
                        val_type = self.visit(node.value) if node.value else STATIC_ANY
                        if declared_type.name in ("var", "Any"):
                            sym = symbols.VariableSymbol(name=var_name, kind=symbols.SymbolKind.VARIABLE, var_type=val_type, node_uid=node.uid)
                        else:
                            sym = symbols.VariableSymbol(name=var_name, kind=symbols.SymbolKind.VARIABLE, var_type=declared_type, node_uid=node.uid)
                        
                        try:
                            self.symbol_table.define(sym, allow_overwrite=True)
                            self.node_to_symbol[actual_target.uid] = sym.uid
                        except ValueError as e:
                            self.error(str(e), node)
                
                if sym:
                    # 如果 target_node 是 TypeAnnotatedExpr，我们也给内部 Name 绑上 UID
                    if isinstance(target_node, ast.TypeAnnotatedExpr) and isinstance(target_node.target, ast.Name):
                        self.node_to_symbol[target_node.target.uid] = sym.uid
                    else:
                        self.node_to_symbol[actual_target.uid] = sym.uid
                    
                    if node.value:
                        val_type = self.visit(node.value)
                        
                        # [NEW] 行为描述行 Lambda 化判断：如果目标类型是 callable
                        if isinstance(node.value, ast.BehaviorExpr) and sym.type_info.name == "callable":
                            self.node_is_deferred[node.value.uid] = True
                        
                        if not val_type.is_assignable_to(sym.type_info):
                            self.error(f"Type mismatch: Cannot assign '{val_type.name}' to '{sym.type_info.name}'", node)
                else:
                    # 无标注赋值
                    if var_name in self.symbol_table.global_refs:
                        global_scope = self.symbol_table.get_global_scope()
                        sym = global_scope.resolve(var_name)
                        if node.value:
                            val_type = self.visit(node.value)
                            if not val_type.is_assignable_to(sym.type_info):
                                self.error(f"Type mismatch: Cannot assign '{val_type.name}' to global '{var_name}' of type '{sym.type_info.name}'", node)
                    else:
                        sym = self.symbol_table.symbols.get(var_name)
                        if not sym or sym.type_info.name in ("Any", "var"):
                            val_type = self.visit(node.value) if node.value else STATIC_ANY
                            sym = self._define_var(var_name, val_type, node, allow_overwrite=(sym is not None))
                        
                        if sym:
                            self.node_to_symbol[actual_target.uid] = sym.uid
                            if node.value:
                                val_type = self.visit(node.value)
                                if not val_type.is_assignable_to(sym.type_info):
                                    self.error(f"Type mismatch: Cannot assign '{val_type.name}' to local '{var_name}' of type '{sym.type_info.name}'", node)
            else:
                # 处理属性或下标赋值 (e.g., p.val = 1)
                target_type = self.visit(target_node)
                if node.value:
                    val_type = self.visit(node.value)
                    if not val_type.is_assignable_to(target_type):
                        self.error(f"Type mismatch: Cannot assign '{val_type.name}' to target of type '{target_type.name}'", node)

    def visit_If(self, node: ast.If):
        self.visit(node.test)
        
        self.scene_stack.append(ast.Scene.BRANCH)
        try:
            for stmt in node.body:
                self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)
        finally:
            self.scene_stack.pop()

    def visit_While(self, node: ast.While):
        self.visit(node.test)
        
        self.scene_stack.append(ast.Scene.LOOP)
        try:
            for stmt in node.body:
                self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)
        finally:
            self.scene_stack.pop()

    def visit_For(self, node: ast.For):
        iter_type = self.visit(node.iter)
        # 获取迭代元素的类型
        element_type = iter_type.element_type
        
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
                self.node_to_symbol[target.uid] = sym.uid # [FIX] 同步 UID
        
        self.scene_stack.append(ast.Scene.LOOP)
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.scene_stack.pop()

    def visit_ExprStmt(self, node: ast.ExprStmt):
        return self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        self.visit(node.target)
        self.visit(node.value)

    def visit_Try(self, node: ast.Try):
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type:
            self.visit(node.type)
        for var_name, target in SymbolExtractor.get_assigned_names(node):
            # 检查是否已在 Pass 2.5 预扫描中定义
            sym = self.symbol_table.symbols.get(var_name)
            if not sym or sym.type_info.name in ("Any", "var"):
                sym = self._define_var(var_name, STATIC_ANY, node, allow_overwrite=(sym is not None))
            
            if sym:
                self.node_to_symbol[target.uid] = sym.uid # [AUDIT] 补全异常变量的 UID 绑定
            # 简单起见，暂时将异常变量视为 Any
        
        for stmt in node.body:
            self.visit(stmt)

    def visit_Pass(self, node: ast.Pass):
        return STATIC_VOID

    def visit_Break(self, node: ast.Break):
        return STATIC_VOID

    def visit_Continue(self, node: ast.Continue):
        return STATIC_VOID

    def visit_Import(self, node: ast.Import):
        # 语义阶段仅校验，不执行导入逻辑（由 Scheduler 处理）
        return STATIC_VOID

    def visit_ImportFrom(self, node: ast.ImportFrom):
        return STATIC_VOID

    def visit_IntentStmt(self, node: ast.IntentStmt):
        # 访问意图元数据
        self.visit(node.intent)
        # 访问意图块内部
        for stmt in node.body:
            self.visit(stmt)
        return STATIC_VOID

    def visit_AnnotatedStmt(self, node: ast.AnnotatedStmt):
        """处理带意图注释的语句包装节点"""
        # [NEW] 显式访问意图节点，确保其进入序列化池
        self.visit(node.intent)
        return self.visit(node.stmt)

    def visit_AnnotatedExpr(self, node: ast.AnnotatedExpr):
        """处理带意图注释的表达式包装节点"""
        # [NEW] 显式访问意图节点
        self.visit(node.intent)
        return self.visit(node.expr)

    def visit_IntentInfo(self, node: ast.IntentInfo):
        """访问意图元数据节点"""
        # 如果意图中有动态表达式，需要访问
        if node.expr:
            self.visit(node.expr)
        if node.segments:
            for seg in node.segments:
                if isinstance(seg, ast.ASTNode):
                    self.visit(seg)
        return STATIC_VOID

    def visit_TypeAnnotatedExpr(self, node: ast.TypeAnnotatedExpr):
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

    def visit_FilteredExpr(self, node: ast.FilteredExpr):
        """处理带过滤条件的表达式包装节点 (e.g., expr if filter)"""
        # 1. 访问被包装的表达式 (例如 While 的 test 或 For 的 iter)
        inner_type = self.visit(node.expr)
        
        # 2. 访问过滤条件，它必须返回布尔值 (或可视为布尔值)
        filter_type = self.visit(node.filter)
        
        # 3. 过滤后，表达式的类型保持不变
        return inner_type

    def visit_LLMExceptionalStmt(self, node: ast.LLMExceptionalStmt):
        """统一处理 LLM 回退逻辑包装节点"""
        # 1. 访问主语句
        self.visit(node.primary)
        # 2. 访问回退块
        self._visit_llmexcept(node.fallback)
        return STATIC_VOID

    def visit_Raise(self, node: ast.Raise):
        if node.exc:
            self.visit(node.exc)
        return STATIC_VOID

    def visit_Retry(self, node: ast.Retry):
        if node.hint:
            self.visit(node.hint)
        return STATIC_VOID

    def visit_Compare(self, node: ast.Compare) -> StaticType:
        left_type = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right_type = self.visit(comparator)
            res = left_type.get_operator_result(op, right_type)
            if not res:
                self.error(f"Comparison operator '{op}' not supported for types '{left_type.name}' and '{right_type.name}'", node)
            # 链式比较中，前一轮的右操作数成为下一轮的左操作数
            left_type = right_type
        
        return STATIC_BOOL

    def visit_BoolOp(self, node: ast.BoolOp) -> StaticType:
        for val in node.values:
            self.visit(val)
        return STATIC_BOOL

    def visit_ListExpr(self, node: ast.ListExpr) -> StaticType:
        from core.domain.symbols import ListType
        element_type = STATIC_ANY
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        
        res = ListType(element_type)
        return res

    def visit_Dict(self, node: ast.Dict) -> StaticType:
        from core.domain.symbols import DictType
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

    def visit_Subscript(self, node: ast.Subscript) -> StaticType:
        value_type = self.visit(node.value)
        self.visit(node.slice)
        res = value_type.element_type
        return res

    def visit_BinOp(self, node: ast.BinOp) -> StaticType:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        
        # 贯彻“一切皆对象”：调用左操作数的自决议方法
        res = left_type.get_operator_result(node.op, right_type)
        if not res:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type.name}' and '{right_type.name}'", node)
            return STATIC_ANY
        return res

    def visit_UnaryOp(self, node: ast.UnaryOp) -> StaticType:
        operand_type = self.visit(node.operand)
        
        # 贯彻“一切皆对象”：调用操作数的自决议方法 (other=None 表示一元运算)
        res = operand_type.get_operator_result(node.op, None)
        if not res:
            self.error(f"Unary operator '{node.op}' not supported for type '{operand_type.name}'", node)
            return STATIC_ANY
        return res

    def visit_Constant(self, node: ast.Constant) -> StaticType:
        val = node.value
        res = STATIC_ANY
        if isinstance(val, bool): res = STATIC_BOOL
        elif isinstance(val, int): res = STATIC_INT
        elif isinstance(val, float): res = STATIC_FLOAT
        elif isinstance(val, str): res = STATIC_STR
        elif val is None: res = STATIC_VOID
        return res

    def visit_Name(self, node: ast.Name) -> StaticType:
        # 1. 解析符号
        sym = self.symbol_table.resolve(node.id)
        
        if not sym:
            msg = f"Variable '{node.id}' is not defined"
            if self.in_behavior_expr:
                msg = f"Variable '{node.id}' used in behavior expression is not defined"
            self.error(msg, node)
            return STATIC_ANY

        # 2. [AUDIT] 强制显式全局声明规则：
        # 如果符号定义在顶层全局作用域，且当前处于局部作用域，则必须显式声明 global
        if self.symbol_table.parent is not None:
            global_scope = self.symbol_table.get_global_scope()
            # 检查解析出的符号是否来自全局作用域
            if node.id in global_scope.symbols and sym == global_scope.symbols[node.id]:
                is_builtin = sym.kind == symbols.SymbolKind.BUILTIN_TYPE or sym.metadata.get("is_builtin")
                if not is_builtin and node.id not in self.symbol_table.global_refs:
                    self.error(f"Global variable '{node.id}' must be declared with 'global' before use in local scope", node)
                    return STATIC_ANY

        self.node_to_symbol[node.uid] = sym.uid # 使用 UID 引用
        
        # 统一获取类型信息，不再需要 isinstance 判断
        res = sym.type_info
            
        return res

    def visit_Attribute(self, node: ast.Attribute) -> StaticType:
        base_type = self.visit(node.value)
        
        # 贯彻“一切皆对象”：询问类型对象如何解析其成员
        member_sym = base_type.resolve_member(node.attr)
        if member_sym:
            self.node_to_symbol[node.uid] = member_sym.uid # 使用 UID 引用
            res = member_sym.type_info
            return res
            
        self.error(f"Type '{base_type.name}' has no member '{node.attr}'", node)
        return STATIC_ANY

    def visit_Call(self, node: ast.Call) -> StaticType:
        func_type = self.visit(node.func)
        arg_types = [self.visit(arg) for arg in node.args]
        
        # 1. 检查是否可调用 (使用接口属性)
        if not func_type.is_callable:
            self.error(f"Type '{func_type.name}' is not callable", node)
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
                    self.error(f"Function expected {len(param_types)} arguments, but got {len(arg_types)}", node)
                else:
                    for i, (expected, actual) in enumerate(zip(param_types, arg_types)):
                        if not actual.is_assignable_to(expected):
                            self.error(f"Argument {i+1} type mismatch: expected '{expected.name}', but got '{actual.name}'", node)
            else:
                self.error(f"Invalid call to '{func_type.name}'", node)
            return STATIC_ANY
            
        return res

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr) -> StaticType:
        self.in_behavior_expr = True
        try:
            for seg in node.segments:
                if isinstance(seg, ast.ASTNode):
                    self.visit(seg)
        finally:
            self.in_behavior_expr = False
        return STATIC_BEHAVIOR

    def _resolve_type(self, node: Any, safe: bool = False) -> StaticType:
        if isinstance(node, ast.Name):
            t = get_builtin_type(node.id)
            if t: return t
            sym = self.symbol_table.resolve(node.id)
            if isinstance(sym, symbols.TypeSymbol) and sym.static_type:
                # [NEW Phase 5] 记录类型引用的符号绑定
                self.node_to_symbol[node.uid] = sym.uid
                return sym.static_type
            self.error(f"Unknown type '{node.id}'", node)
        elif isinstance(node, ast.Attribute):
            # 处理 a.b 形式的类型 (如插件中的类)
            # [AUDIT] 在 safe 模式下（如预扫描阶段），禁止触发 visit()
            if safe:
                # 降级处理：仅支持简单的名称解析，不支持复杂的表达式类型
                if isinstance(node.value, ast.Name):
                    base_sym = self.symbol_table.resolve(node.value.id)
                    if base_sym and base_sym.type_info:
                        member_sym = base_sym.type_info.resolve_member(node.attr)
                        if member_sym and isinstance(member_sym, symbols.TypeSymbol):
                            # [NEW Phase 5] 记录类型引用的符号绑定
                            self.node_to_symbol[node.uid] = member_sym.uid
                            return member_sym.static_type
                return STATIC_ANY
                
            base_type = self.visit(node.value)
            member_sym = base_type.resolve_member(node.attr)
            if member_sym and isinstance(member_sym, symbols.TypeSymbol) and member_sym.static_type:
                # [NEW Phase 5] 记录类型引用的符号绑定
                self.node_to_symbol[node.uid] = member_sym.uid
                return member_sym.static_type
            self.error(f"Unknown type '{node.attr}' in '{base_type.name}'", node)
        return STATIC_ANY

    def _validate_integrity(self, root: ast.ASTNode):
        """[Phase 5] 语义完整性自检：确保所有引用节点都已绑定到侧表"""
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.DETAIL, "Performing semantic integrity self-check...")
        
        missing_bindings = []
        
        # 定义需要校验的节点集合
        BINDING_REQUIRED = (ast.Name, ast.Attribute, ast.FunctionDef, ast.ClassDef, ast.LLMFunctionDef, ast.arg)
        
        def check(node: Any):
            if not isinstance(node, ast.ASTNode):
                return
            
            # 1. 检查符号绑定侧表
            if isinstance(node, BINDING_REQUIRED):
                # 排除内置类型 Name 节点，它们由解析器动态创建，通常不参与符号绑定
                if isinstance(node, ast.Name) and node.id in ("int", "str", "float", "bool", "Any", "var", "none", "None"):
                    pass
                elif node.uid not in self.node_to_symbol:
                    # 获取更具体的节点标识名
                    node_name = getattr(node, 'id', getattr(node, 'name', getattr(node, 'attr', 'unnamed')))
                    missing_bindings.append(f"{node.__class__.__name__} '{node_name}' (UID: {node.uid})")
            
            # 2. 递归遍历子节点
            for attr in vars(node):
                val = getattr(node, attr)
                if isinstance(val, list):
                    for item in val: check(item)
                elif isinstance(val, ast.ASTNode):
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

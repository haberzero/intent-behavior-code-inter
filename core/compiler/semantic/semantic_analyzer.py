from typing import Dict, Optional, List, Any
from core.types import parser_types as ast
from core.compiler.support.diagnostics import DiagnosticReporter, DiagnosticSeverity
from core.compiler.support.issue_adapter import IssueTrackerAdapter
from core.support.diagnostics.issue_tracker import IssueTracker
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.support.host_interface import HostInterface

from . import symbols
from .symbols import (
    SymbolTable, SymbolKind, TypeSymbol, FunctionSymbol, VariableSymbol, 
    StaticType, FunctionType, ClassType, ModuleType,
    STATIC_ANY, STATIC_VOID, STATIC_INT, STATIC_STR, STATIC_FLOAT, STATIC_BOOL
)
from .types import get_builtin_type
from .prelude import Prelude
from .collector import SymbolCollector, LocalSymbolCollector, SymbolExtractor
from .resolver import TypeResolver
from .result import CompilationResult

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
        collector = SymbolCollector(self.symbol_table, self.issue_tracker)
        collector.collect(node)
        
        # Pass 2: 类型决议 (Inheritance, Signatures)
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Pass 2: Resolving static types...")
        resolver = TypeResolver(self.symbol_table, self)
        resolver.resolve(node)
        
        # Pass 3: 深度语义检查 (Body, Expressions, Type Checking)
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Pass 3: Deep checking...")
        self.visit(node)
        
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Static analysis complete.")
        self.issue_tracker.check_errors()

        return CompilationResult(
            module_ast=node if isinstance(node, ast.Module) else None,
            symbol_table=self.symbol_table
        )

    def visit(self, node: ast.ASTNode) -> StaticType:
        # [NEW] 记录表达式场景上下文
        if isinstance(node, ast.Expr):
            self.node_scenes[node.uid] = self.scene_stack[-1]

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

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
            return sym
        except ValueError as e:
            self.error(str(e), node)
            return None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        sym = self.symbol_table.resolve(node.name)
        ret_type = sym.return_type if isinstance(sym, symbols.FunctionSymbol) else STATIC_VOID
        
        # 进入局部作用域
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        
        # [NEW] 隐式 self 注入：如果是类方法，在局部作用域注入 self 符号
        if self.current_class:
            self._define_var("self", self.current_class, node)

        # 注册参数
        for i, arg in enumerate(node.args):
            # 索引偏移：类方法的签名中包含隐含的 self
            sig_idx = i + 1 if self.current_class else i
            arg_type = sym.param_types[sig_idx] if (isinstance(sym, symbols.FunctionSymbol) and sig_idx < len(sym.param_types)) else STATIC_ANY
            self._define_var(arg.arg, arg_type, arg)
            
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
        
        # 进入局部作用域以校验提示词中的占位符
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table)
        
        if self.current_class:
            self._define_var("self", self.current_class, node)
            
        for i, arg in enumerate(node.args):
            sig_idx = i + 1 if self.current_class else i
            arg_type = sym.param_types[sig_idx] if (isinstance(sym, symbols.FunctionSymbol) and sig_idx < len(sym.param_types)) else STATIC_ANY
            self._define_var(arg.arg, arg_type, arg)
            
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
        if node.type_annotation:
            declared_type = self._resolve_type(node.type_annotation)
            for var_name, target in SymbolExtractor.get_assigned_names(node):
                # [NEW] 局部优先原则：带有类型标注的赋值总是定义新变量
                if var_name in self.symbol_table.global_refs:
                    self.error(f"Cannot redeclare global variable '{var_name}' with type annotation", node)
                
                # 检查是否已在 Pass 2.5 预扫描中定义
                sym = self.symbol_table.symbols.get(var_name)
                # [LIFECYCLE] 如果预扫描阶段未定义，或者定义为 Any/var 占位符，则在此处建立正式定义
                if not sym or sym.type_info.name in ("Any", "var"):
                    if declared_type.name == "var" or declared_type.name == "Any":
                        val_type = self.visit(node.value) if node.value else STATIC_ANY
                        sym = symbols.VariableSymbol(name=var_name, kind=symbols.SymbolKind.VARIABLE, var_type=val_type, node_uid=node.uid)
                    else:
                        sym = symbols.VariableSymbol(name=var_name, kind=symbols.SymbolKind.VARIABLE, var_type=declared_type, node_uid=node.uid)
                    
                    try:
                        # 允许覆盖 Pass 1/2.5 的占位符
                        self.symbol_table.define(sym, allow_overwrite=True)
                    except ValueError as e:
                        self.error(str(e), node)
                
                if sym:
                    target.symbol_uid = sym.uid # [FIX] 同步 UID
                
                # 类型检查
                if node.value:
                    val_type = self.visit(node.value)
                    if not val_type.is_assignable_to(sym.type_info):
                        self.error(f"Type mismatch: Cannot assign '{val_type.name}' to '{sym.type_info.name}'", node)
        else:
            for var_name, target in SymbolExtractor.get_assigned_names(node):
                # [NEW] 局部优先语义逻辑：
                # 1. 检查是否显式声明为 global
                if var_name in self.symbol_table.global_refs:
                    # 查找全局符号
                    global_scope = self.symbol_table.get_global_scope()
                    sym = global_scope.resolve(var_name)
                    # (由于 GlobalStmt 已校验存在性，这里 sym 理论上一定存在)
                    if node.value:
                        val_type = self.visit(node.value)
                        if not val_type.is_assignable_to(sym.type_info):
                            self.error(f"Type mismatch: Cannot assign '{val_type.name}' to global '{var_name}' of type '{sym.type_info.name}'", node)
                else:
                    # 2. 局部优先：仅在当前作用域查找（不再向上递归 resolve）
                    sym = self.symbol_table.symbols.get(var_name)
                    
                    # [LIFECYCLE] 如果符号尚未定义，或者是之前收集到的 Any/var 占位符，则执行隐式定义
                    if not sym or sym.type_info.name in ("Any", "var"):
                        # 隐式局部声明
                        val_type = self.visit(node.value) if node.value else STATIC_ANY
                        # 如果是占位符，允许覆盖
                        sym = self._define_var(var_name, val_type, node, allow_overwrite=(sym is not None))
                        if sym:
                            target.symbol_uid = sym.uid # [FIX] 同步 UID
                    else:
                        if node.value:
                            val_type = self.visit(node.value)
                            if not val_type.is_assignable_to(sym.type_info):
                                self.error(f"Type mismatch: Cannot assign '{val_type.name}' to local '{var_name}' of type '{sym.type_info.name}'", node)
            
            # 处理属性赋值 (e.g., db.port = 8080)
            if isinstance(node.targets[0], ast.Attribute):
                target = node.targets[0]
                target_type = self.visit(target)
                val_type = self.visit(node.value)
                if not val_type.is_assignable_to(target_type):
                    self.error(f"Type mismatch: Cannot assign '{val_type.name}' to attribute of type '{target_type.name}'", node)

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
                target.symbol_uid = sym.uid # [FIX] 同步 UID
        
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
                target.symbol_uid = sym.uid # [AUDIT] 补全异常变量的 UID 绑定
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
        # 访问意图块内部
        for stmt in node.body:
            self.visit(stmt)
        return STATIC_VOID

    def visit_AnnotatedStmt(self, node: ast.AnnotatedStmt):
        """处理带意图注释的语句包装节点"""
        # TODO: 在此处实现意图与行为的一致性检查逻辑
        return self.visit(node.stmt)

    def visit_AnnotatedExpr(self, node: ast.AnnotatedExpr):
        """处理带意图注释的表达式包装节点"""
        return self.visit(node.expr)

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
        
        node.inferred_type = STATIC_BOOL
        return STATIC_BOOL

    def visit_BoolOp(self, node: ast.BoolOp) -> StaticType:
        for val in node.values:
            self.visit(val)
        node.inferred_type = STATIC_BOOL
        return STATIC_BOOL

    def visit_ListExpr(self, node: ast.ListExpr) -> StaticType:
        from .symbols import ListType
        element_type = STATIC_ANY
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        
        res = ListType(element_type)
        node.inferred_type = res
        return res

    def visit_Dict(self, node: ast.Dict) -> StaticType:
        for key in node.keys:
            self.visit(key)
        for val in node.values:
            self.visit(val)
        node.inferred_type = STATIC_ANY # TODO: Implement DictType
        return STATIC_ANY

    def visit_Subscript(self, node: ast.Subscript) -> StaticType:
        value_type = self.visit(node.value)
        self.visit(node.slice)
        res = value_type.element_type
        node.inferred_type = res
        return res

    def visit_BinOp(self, node: ast.BinOp) -> StaticType:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        
        # 贯彻“一切皆对象”：调用左操作数的自决议方法
        res = left_type.get_operator_result(node.op, right_type)
        if not res:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type.name}' and '{right_type.name}'", node)
            return STATIC_ANY
        node.inferred_type = res
        return res

    def visit_UnaryOp(self, node: ast.UnaryOp) -> StaticType:
        operand_type = self.visit(node.operand)
        
        # 贯彻“一切皆对象”：调用操作数的自决议方法 (other=None 表示一元运算)
        res = operand_type.get_operator_result(node.op, None)
        if not res:
            self.error(f"Unary operator '{node.op}' not supported for type '{operand_type.name}'", node)
            return STATIC_ANY
        node.inferred_type = res
        return res

    def visit_Constant(self, node: ast.Constant) -> StaticType:
        val = node.value
        res = STATIC_ANY
        if isinstance(val, bool): res = STATIC_BOOL
        elif isinstance(val, int): res = STATIC_INT
        elif isinstance(val, float): res = STATIC_FLOAT
        elif isinstance(val, str): res = STATIC_STR
        elif val is None: res = STATIC_VOID
        node.inferred_type = res
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

        node.symbol_uid = sym.uid # 使用 UID 引用
        
        # 统一获取类型信息，不再需要 isinstance 判断
        res = sym.type_info
            
        node.inferred_type = res
        return res

    def visit_Attribute(self, node: ast.Attribute) -> StaticType:
        base_type = self.visit(node.value)
        
        # 贯彻“一切皆对象”：询问类型对象如何解析其成员
        member_sym = base_type.resolve_member(node.attr)
        if member_sym:
            node.symbol_uid = member_sym.uid # 使用 UID 引用
            res = member_sym.type_info
            node.inferred_type = res
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
            # 如果是函数类型，提供更详细的错误
            if func_type.name == "function":
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
            
        node.inferred_type = res
        return res

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr) -> StaticType:
        self.in_behavior_expr = True
        try:
            for seg in node.segments:
                if isinstance(seg, ast.ASTNode):
                    self.visit(seg)
        finally:
            self.in_behavior_expr = False
        node.inferred_type = STATIC_STR
        return STATIC_STR

    def _resolve_type(self, node: Any, safe: bool = False) -> StaticType:
        if isinstance(node, ast.Name):
            t = get_builtin_type(node.id)
            if t: return t
            sym = self.symbol_table.resolve(node.id)
            if isinstance(sym, symbols.TypeSymbol) and sym.static_type:
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
                            return member_sym.static_type
                return STATIC_ANY
                
            base_type = self.visit(node.value)
            member_sym = base_type.resolve_member(node.attr)
            if member_sym and isinstance(member_sym, symbols.TypeSymbol) and member_sym.static_type:
                return member_sym.static_type
            self.error(f"Unknown type '{node.attr}' in '{base_type.name}'", node)
        return STATIC_ANY

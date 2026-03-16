from typing import Dict, Optional, List, Any
from core.domain import ast as ast
from core.compiler.support.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.foundation.host_interface import HostInterface

from core.domain import symbols
from core.domain.symbols import (
    SymbolTable, SymbolKind, TypeSymbol, FunctionSymbol, VariableSymbol
)
from core.domain.types.descriptors import (
    TypeDescriptor, ClassMetadata, FunctionMetadata, ListMetadata, DictMetadata,
    ModuleMetadata, BoundMethodMetadata
)

from .prelude import Prelude
from .collector import SymbolCollector, LocalSymbolCollector, SymbolExtractor
from .resolver import TypeResolver
from core.domain.blueprint import CompilationResult

class SemanticAnalyzer:
    """
    语义分析器：执行静态分析和类型检查。
    贯彻“一切皆对象”思想：Analyzer 仅作为调度者，核心逻辑由 TypeDescriptor (Axiom) 自决议。
    """
    def __init__(self, issue_tracker: Optional[DiagnosticReporter] = None, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None, registry: Optional[Any] = None):
        self.symbol_table = SymbolTable() # 全局静态符号表
        self.issue_tracker = issue_tracker or IssueTracker()
        self.host_interface = host_interface
        self.debugger = debugger or core_debugger
        
        # [Strict Registry] 语义分析必须依赖有效的注册表上下文
        self.registry = registry
             
        if self.registry is None:
            raise ValueError("SemanticAnalyzer requires a valid MetadataRegistry instance. 'None' is not allowed.")
        
        # [Strict Registry] 缓存常用描述符以提高性能并确保标识一致性
        self._any_desc = self.registry.resolve("Any")
        self._void_desc = self.registry.resolve("void")
        self._bool_desc = self.registry.resolve("bool")
        self._int_desc = self.registry.resolve("int")
        self._str_desc = self.registry.resolve("str")
        self._behavior_desc = self.registry.resolve("behavior")

        self.current_return_type: Optional[TypeDescriptor] = None
        self.current_class: Optional[ClassMetadata] = None
        self.in_behavior_expr = False
        self.scene_stack = [ast.IbScene.GENERAL] # 场景上下文栈
        self.node_scenes: Dict[ast.IbASTNode, ast.IbScene] = {} # 侧表：节点 ID -> 场景
        self.node_to_symbol: Dict[ast.IbASTNode, symbols.Symbol] = {} # 侧表：节点 -> 符号
        self.node_to_type: Dict[ast.IbASTNode, TypeDescriptor] = {} # 侧表：节点 -> 类型对象
        self.node_is_deferred: Dict[ast.IbASTNode, bool] = {} # 侧表：行为描述行是否延迟执行 (Lambda)
        self.node_intents: Dict[ast.IbASTNode, List[ast.IbIntentInfo]] = {} # 侧表：节点 -> 意图列表
        
        # 初始化 Prelude
        self.prelude = Prelude(self.host_interface, registry=self.registry)

    def _init_builtins(self):
        """注册内置静态符号"""
        
        # 1. 注册内置函数
        for name, func_desc in self.prelude.get_builtins().items():
            sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, descriptor=func_desc, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 2. 注册内置类型
        for name, type_desc in self.prelude.get_builtin_types().items():
            sym = TypeSymbol(name=name, kind=SymbolKind.BUILTIN_TYPE, descriptor=type_desc, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 3. 注册内置模块 (如果 Registry 中存在)
        for name, mod_desc in self.prelude.get_builtin_modules().items():
            sym = symbols.VariableSymbol(name=name, kind=SymbolKind.MODULE, descriptor=mod_desc, metadata={"is_builtin": True})
            self.symbol_table.define(sym)

    def analyze(self, node: ast.IbASTNode, raise_on_error: bool = True) -> CompilationResult:
        self.debugger.enter_scope(CoreModule.SEMANTIC, "Starting static semantic analysis...")
        try:
            # 初始化内置符号
            self._init_builtins()
                
            # --- 多轮分析 (Multi-Pass) ---
            
            # Pass 1: 收集符号 (Classes, Functions)
            self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 1: Collecting static symbols...")
            collector = SymbolCollector(self.symbol_table, self, self.issue_tracker)
            collector.collect(node)
            self.debugger.exit_scope(CoreModule.SEMANTIC)
            
            # Pass 2: 类型决议 (Inheritance, Signatures)
            self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 2: Resolving static types...")
            resolver = TypeResolver(self.symbol_table, self)
            resolver.resolve(node)
            self.debugger.exit_scope(CoreModule.SEMANTIC)
            
            # Pass 3: 深度语义检查 (Body, Expressions, Type Checking)
            self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 3: Deep checking...")
            self.visit(node)
            self.debugger.exit_scope(CoreModule.SEMANTIC)
            
            # [NEW Phase 5] 自检校验：确保侧表完整性
            # 仅在没有收集到错误的情况下执行完整性检查，因为解析失败的节点本身就无法绑定
            if not self.issue_tracker.has_errors():
                self._validate_integrity(node)
            
            self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Static analysis complete.")
            
            if raise_on_error:
                self.issue_tracker.check_errors()

            return CompilationResult(
                module_ast=node if isinstance(node, ast.IbModule) else None,
                symbol_table=self.symbol_table,
                node_scenes=self.node_scenes,
                node_to_symbol=self.node_to_symbol,
                node_to_type=self.node_to_type,
                node_is_deferred=self.node_is_deferred,
                node_intents=self.node_intents
            )
        finally:
            self.debugger.exit_scope(CoreModule.SEMANTIC)

    def visit(self, node: ast.IbASTNode) -> TypeDescriptor:
        # [NEW] 意图涂抹关联：将 Parser 暂存在节点上的意图转入侧表，实现 AST 扁平化
        # [IES 2.0 Policy] 侧表仅记录“当前节点特有”的涂抹意图（即通过 @ 标注的意图）。
        # 块级意图（通过 intent 语句定义）由解释器在执行时通过 AST 结构动态维护在栈中。
        # 这样避免了静态分析时重复涂抹导致的逻辑冲突。
        if hasattr(node, "_pending_intents"):
            intents = getattr(node, "_pending_intents")
            if intents:
                self.node_intents[node] = intents

        # [NEW] 记录场景上下文侧表
        if isinstance(node, ast.IbExpr):
            self.node_scenes[node] = self.scene_stack[-1]

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        res_type = visitor(node)
        
        # [NEW Phase 5] 记录类型推导侧表
        if isinstance(node, ast.IbExpr) and res_type:
            self.node_to_type[node] = res_type
            
        return res_type

    def generic_visit(self, node: ast.IbASTNode) -> TypeDescriptor:
        """
        [AUDIT] 严格访问模式：对于未明确处理的节点，不再静默返回 Any。
        """
        # 允许某些辅助节点（如 arg, alias）被跳过
        if isinstance(node, (ast.IbArg, ast.IbAlias)):
            return self._any_desc
            
        self.error(f"Internal compiler error: Unhandled AST node type '{node.__class__.__name__}'", node, code="INTERNAL_ERROR")
        return self._any_desc

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
        return self._void_desc

    def visit_IbGlobalStmt(self, node: ast.IbGlobalStmt):
        if self.symbol_table.parent is None:
            self.error("Global declaration is not allowed in global scope", node, code="SEM_004")
            return self._void_desc
        
        for name in node.names:
            global_scope = self.symbol_table.get_global_scope()
            if name not in global_scope.symbols:
                self.error(f"Global variable '{name}' is not defined in global scope", node, code="SEM_001")
            else:
                self.symbol_table.add_global_ref(name)
        return self._void_desc

    def visit_IbClassDef(self, node: ast.IbClassDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not isinstance(sym, symbols.TypeSymbol):
            return self._void_desc
            
        self.node_to_symbol[node] = sym
        
        old_table = self.symbol_table
        if sym.owned_scope:
            self.symbol_table = sym.owned_scope
            
        old_class = self.current_class
        # sym.descriptor 应该是 ClassMetadata
        if isinstance(sym.descriptor, ClassMetadata):
            self.current_class = sym.descriptor
        else:
            self.current_class = None # Should not happen

        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.current_class = old_class
            self.symbol_table = old_table
        return self._void_desc

    def _define_var(self, name: str, var_type: TypeDescriptor, node: ast.IbASTNode, allow_overwrite: bool = False):
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
                    if not (existing.kind == SymbolKind.VARIABLE and any(existing is s for s in self.symbol_table.get_global_scope().symbols.values())):
                        if not allow_overwrite:
                            self.node_to_symbol[node] = existing
                            return existing

            sym = symbols.VariableSymbol(name=name, kind=symbols.SymbolKind.VARIABLE, descriptor=var_type, def_node=node)
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            
            # [Axiom Hook] 同步到描述符的成员表中 (保持物理隔离下的元数据完备性)
            if self.current_class:
                self.current_class.members[name] = sym

            # [NEW Phase 5] 记录侧表映射
            self.node_to_symbol[node] = sym
            return sym
        except ValueError as e:
            self.error(str(e), node, code="SEM_003")
            return None

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not isinstance(sym, symbols.FunctionSymbol):
            return self._void_desc
            
        self.node_to_symbol[node] = sym
        
        # [NEW] 决议真实的函数签名并更新元数据
        param_types = [self._resolve_type(arg.annotation) for arg in node.args]
        # 类方法第一个参数是 self
        if self.current_class:
            param_types.insert(0, self.current_class)
            
        ret_type = self._resolve_type(node.returns)
        
        # 更新已注册的元数据对象 (原地修改以保持引用一致性)
        if isinstance(sym.descriptor, FunctionMetadata):
            sym.descriptor.param_types = param_types
            sym.descriptor.return_type = ret_type
            
        # 进入局部作用域
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table)
        self.symbol_table = local_scope
        
        # [NEW Phase 5] 将局部作用域回填到符号中，以便序列化器能够递归发现局部符号
        if isinstance(sym, symbols.FunctionSymbol):
            sym.owned_scope = local_scope
        
        # [NEW] 隐式 self 注入：如果是类方法，在局部作用域注入 self 符号
        if self.current_class:
            # self 的类型就是当前类
            self._define_var("self", self.current_class, node)

        # 注册参数
        for i, arg_node in enumerate(node.args):
            # 索引偏移：类方法的签名中包含隐含的 self
            sig_idx = i + 1 if self.current_class else i
            arg_type = param_types[sig_idx] if sig_idx < len(param_types) else self._any_desc
            
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
        return self._void_desc

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not isinstance(sym, symbols.FunctionSymbol):
            return self._void_desc
            
        self.node_to_symbol[node] = sym
        
        # [NEW] 决议真实的函数签名并更新元数据
        param_types = [self._resolve_type(arg.annotation) for arg in node.args]
        if self.current_class:
            param_types.insert(0, self.current_class)
            
        ret_type = self._resolve_type(node.returns)
        
        if isinstance(sym.descriptor, FunctionMetadata):
            sym.descriptor.param_types = param_types
            sym.descriptor.return_type = ret_type
            
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
            arg_type = param_types[sig_idx] if sig_idx < len(param_types) else self._any_desc
            
            # 获取参数名节点
            name_node = arg_node
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                name_node = arg_node.target
            
            if isinstance(name_node, ast.IbArg):
                self._define_var(name_node.arg, arg_type, name_node)
            elif isinstance(name_node, ast.IbName):
                self._define_var(name_node.id, arg_type, name_node)
            
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
        return self._void_desc

    def visit_IbReturn(self, node: ast.IbReturn):
        if node.value:
            ret_type = self.visit(node.value)
            if self.current_return_type and not ret_type.is_assignable_to(self.current_return_type):
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got '{ret_type.name}'", node, code="SEM_003")
        else:
            if self.current_return_type and self.current_return_type != self._void_desc:
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got 'void'", node, code="SEM_003")
        return self._void_desc

    def visit_IbAssign(self, node: ast.IbAssign):
        # 1. 预先计算右值类型，避免在循环中重复 visit
        val_type = self.visit(node.value) if node.value else self._any_desc
        
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
            elif isinstance(target_node, (ast.IbAttribute, ast.IbSubscript)):
                # 处理属性赋值 (obj.x = 1) 或 下标赋值 (list[0] = 1)
                # 递归调用 visit 来决议目标位置的类型
                target_type = self.visit(target_node)
                # 检查类型兼容性
                if not val_type.is_assignable_to(target_type):
                    hint = val_type.get_diff_hint(target_type)
                    self.error(f"Cannot assign '{val_type.name}' to '{target_type.name}'", node, code="SEM_003", hint=hint)
                continue
            
            if var_name:
                # [NEW] 决议最终目标类型 (Inference Policy)
                sym = self.symbol_table.symbols.get(var_name)
                
                if declared_type:
                    # 1. 有显式标注：优先尊重标注，除非标注是 'var' (需要推导)
                    if declared_type.name == "var":
                        target_type = val_type
                    else:
                        target_type = declared_type
                    
                    # [SEM_002] 检查是否在当前作用域重复声明
                    if var_name in self.symbol_table.symbols:
                        existing = self.symbol_table.symbols[var_name]
                        # [Fix] 允许同一个节点在 Pass 3 更新它在 Pass 1 定义的符号类型
                        if existing.def_node is not node:
                            # 如果不是内置符号，且不是同类型的重新赋值（IBCI 允许同名覆盖但通常通过 allow_overwrite 控制）
                            # 这里我们遵循更严格的静态语言规则：同作用域禁止显式类型重声明
                            self.error(f"Variable '{var_name}' is already defined in this scope", node, code="SEM_002")
                    
                    # 定义或更新符号
                    sym = self._define_var(var_name, target_type, node, allow_overwrite=True)
                else:
                    # 2. 无标注：如果尚未定义，或者现有定义是动态的 (Any/var)，则进行推导
                    if not sym or sym.descriptor.is_dynamic():
                        sym = self._define_var(var_name, val_type, node, allow_overwrite=(sym is not None))
                
                if sym:
                    self.node_to_symbol[actual_target] = sym
                    self.node_to_type[target_node] = sym.descriptor
                    if isinstance(target_node, ast.IbTypeAnnotatedExpr) and isinstance(target_node.target, ast.IbName):
                        self.node_to_symbol[target_node.target] = sym
                        self.node_to_type[target_node.target] = sym.descriptor
                    
                    # [NEW] 行为描述行 Lambda 化判断
                    # 只有当目标类型明确要求具备调用能力，或者是动态类型时，才进行延迟推断
                    target_desc = sym.descriptor
                    is_explicit_callable = False
                    
                    if target_desc:
                        # 使用公理系统检查能力
                        call_cap = target_desc.get_call_trait()
                        is_dynamic = target_desc.is_dynamic()
                        
                        is_explicit_callable = (call_cap is not None) or is_dynamic
                    
                    if isinstance(node.value, ast.IbBehaviorExpr) and is_explicit_callable:
                        self.node_is_deferred[node.value] = True
                    
                    if not val_type.is_assignable_to(sym.descriptor):
                        hint = val_type.get_diff_hint(sym.descriptor)
                        self.error(f"Type mismatch: Cannot assign '{val_type.name}' to '{sym.descriptor.name}'", node, code="SEM_003", hint=hint)
            else:
                # 处理属性或下标赋值 (e.g., p.val = 1)
                target_type = self.visit(target_node)
                if target_type and not val_type.is_assignable_to(target_type):
                    hint = val_type.get_diff_hint(target_type)
                    self.error(f"Type mismatch: Cannot assign '{val_type.name}' to target of type '{target_type.name}'", node, code="SEM_003", hint=hint)
        
        # 4. 处理回退块
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return self._void_desc

    def visit_IbIf(self, node: ast.IbIf):
        # 1. 条件测试属于 BRANCH 场景
        self.scene_stack.append(ast.IbScene.BRANCH)
        try:
            self.visit(node.test)
        finally:
            self.scene_stack.pop()
            
        # 2. Body 和 Orelse 恢复父级场景
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
            
        # 3. 回退块
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return self._void_desc

    def visit_IbWhile(self, node: ast.IbWhile):
        # 1. 循环条件属于 LOOP 场景
        self.scene_stack.append(ast.IbScene.LOOP)
        try:
            self.visit(node.test)
        finally:
            self.scene_stack.pop()
            
        # 2. 循环体
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
            
        # 3. 回退块
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return self._void_desc

    def visit_IbFor(self, node: ast.IbFor):
        # 1. 迭代头部属于 LOOP 场景
        self.scene_stack.append(ast.IbScene.LOOP)
        try:
            iter_type = self.visit(node.iter)
            # 贯彻“一切皆对象”协议：询问类型如何提供迭代元素
            iter_trait = iter_type.get_iter_trait()
            if iter_trait:
                element_type = iter_type.get_element_type()
            else:
                self.error(f"Type '{iter_type.name}' is not iterable", node.iter, code="SEM_003")
                element_type = self._any_desc
            
            for var_name, target in SymbolExtractor.get_assigned_names(node):
                # 检查是否已在 Pass 2.5 预扫描中定义
                sym = self.symbol_table.symbols.get(var_name)
                # 如果未定义，或者定义为 Any/var 占位符，则进行推导
                if not sym or sym.descriptor.is_dynamic():
                    sym = self._define_var(var_name, element_type, target, allow_overwrite=(sym is not None))
                else:
                    # 显式定义的变量（如带有类型标注），则执行类型更新
                    if isinstance(sym, VariableSymbol):
                        sym.descriptor = element_type
                
                if sym:
                    self.node_to_symbol[target] = sym # [FIX] 同步 UID
        finally:
            self.scene_stack.pop()
            
        # 2. 循环体
        for stmt in node.body:
            self.visit(stmt)
            
        # 3. 回退块
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return self._void_desc

    def visit_IbExprStmt(self, node: ast.IbExprStmt):
        res = self.visit(node.value)
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return res

    def visit_IbAugAssign(self, node: ast.IbAugAssign):
        self.visit(node.target)
        self.visit(node.value)
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return self._void_desc

    def visit_IbTry(self, node: ast.IbTry):
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)
        if node.llm_fallback:
            self._visit_llmexcept(node.llm_fallback)
        return self._void_desc

    def visit_IbExceptHandler(self, node: ast.IbExceptHandler):
        if node.type:
            self.visit(node.type)
            
        # 获取 Exception 类型描述符
        exc_type = self.prelude.get_builtin_types().get("Exception", self._any_desc)
        
        for var_name, target in SymbolExtractor.get_assigned_names(node):
            # 检查是否已在 Pass 2.5 预扫描中定义
            sym = self.symbol_table.symbols.get(var_name)
            if not sym or sym.descriptor.is_dynamic():
                # [Strict Exception] 异常变量默认为 Exception 类型，而非 Any
                sym = self._define_var(var_name, exc_type, node, allow_overwrite=(sym is not None))
            
            if sym:
                self.node_to_symbol[target] = sym # [AUDIT] 补全异常变量的 UID 绑定
        
        for stmt in node.body:
            self.visit(stmt)
        return self._void_desc

    def visit_IbPass(self, node: ast.IbPass):
        return self._void_desc

    def visit_IbBreak(self, node: ast.IbBreak):
        return self._void_desc

    def visit_IbContinue(self, node: ast.IbContinue):
        return self._void_desc

    def visit_IbImport(self, node: ast.IbImport):
        # 在符号表中定义导入的名称
        for alias in node.names:
            name = alias.asname or alias.name
            
            # [Strict Import] 符号应由 Scheduler 预先注入
            sym = self.symbol_table.resolve(name)
            if sym:
                self.node_to_symbol[node] = sym
            else:
                self.error(f"Module '{name}' not found or failed to load", node, code="SEM_001")
                # 仅作为错误恢复，定义为 Any
                self._define_var(name, self._any_desc, node)

        return self._void_desc

    def visit_IbImportFrom(self, node: ast.IbImportFrom):
        for alias in node.names:
            if alias.name == '*':
                # import * 由 Scheduler 处理符号注入，此处无需操作
                continue
                
            name = alias.asname or alias.name
            
            # [Strict Import] 符号应由 Scheduler 预先注入
            sym = self.symbol_table.resolve(name)
            if sym:
                self.node_to_symbol[node] = sym
            else:
                self.error(f"Cannot import name '{alias.name}' from '{node.module}'", node, code="SEM_001")
                self._define_var(name, self._any_desc, node)
                
        return self._void_desc

    def visit_IbIntentStmt(self, node: ast.IbIntentStmt):
        # 1. 访问意图元数据（检查其中的表达式等）
        self.visit(node.intent)
        
        # 2. 访问意图块内部
        for stmt in node.body:
            self.visit(stmt)
            
        return self._void_desc

    def visit_IbIntentInfo(self, node: ast.IbIntentInfo):
        """访问意图元数据节点"""
        # 如果意图中有动态表达式，需要访问
        if node.expr:
            self.visit(node.expr)
        if node.segments:
            for seg in node.segments:
                if isinstance(seg, ast.IbASTNode):
                    self.visit(seg)
        return self._void_desc

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """处理带类型标注的表达式包装节点 (例如 Casts 或声明)"""
        # 1. 解析标注的类型
        annotated_type = self._resolve_type(node.annotation)
        
        # 2. 访问内部表达式并检查类型一致性
        inner_type = self.visit(node.target)
        
        # 如果是显式标注，我们认为结果类型就是标注的类型（类似于 Cast）
        # 但我们需要校验内部表达式是否能被视为该类型
        if not inner_type.is_assignable_to(annotated_type):
            self.error(f"Type mismatch: Expression of type '{inner_type.name}' cannot be cast/assigned to '{annotated_type.name}'", node, code="SEM_003")
            
        return annotated_type

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """处理带过滤条件的表达式包装节点 (e.g., expr if filter)"""
        # 1. 访问被包装的表达式 (例如 While 的 test 或 For 的 iter)
        inner_type = self.visit(node.expr)
        
        # 2. 访问过滤条件，它必须返回布尔值 (或可视为布尔值)
        filter_type = self.visit(node.filter)
        
        # 3. 过滤后，表达式的类型保持不变
        return inner_type

    def visit_IbRaise(self, node: ast.IbRaise):
        if node.exc:
            self.visit(node.exc)
        return self._void_desc

    def visit_IbRetry(self, node: ast.IbRetry):
        if node.hint:
            self.visit(node.hint)
        return self._void_desc

    def visit_IbCompare(self, node: ast.IbCompare) -> TypeDescriptor:
        left_type = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right_type = self.visit(comparator)
            res = left_type.get_operator_result(op, right_type)
            if not res:
                self.error(f"Comparison operator '{op}' not supported for types '{left_type.name}' and '{right_type.name}'", node, code="SEM_003")
            # 链式比较中，前一轮的右操作数成为下一轮的左操作数
            left_type = right_type
        
        return self._bool_desc

    def visit_IbBoolOp(self, node: ast.IbBoolOp) -> TypeDescriptor:
        for val in node.values:
            self.visit(val)
        return self._bool_desc

    def visit_IbListExpr(self, node: ast.IbListExpr) -> TypeDescriptor:
        element_type = self._any_desc
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        
        # [Axiom-Driven] 使用 Factory 创建 ListMetadata
        # 严格模式：直接使用 Registry 工厂，并进行即时注册以注入公理
        desc = self.registry.factory.create_list(element_type)
        self.registry.register(desc)
        return desc

    def visit_IbDict(self, node: ast.IbDict) -> TypeDescriptor:
        key_type = self._any_desc
        val_type = self._any_desc
        
        if node.keys:
            key_type = self.visit(node.keys[0])
            for key in node.keys[1:]:
                self.visit(key)
        
        if node.values:
            val_type = self.visit(node.values[0])
            for val in node.values[1:]:
                self.visit(val)
                
        # [Axiom-Driven] 使用 Factory 创建 DictMetadata
        # 严格模式：直接使用 Registry 工厂并注册
        desc = self.registry.factory.create_dict(key_type, val_type)
        self.registry.register(desc)
        return desc

    def visit_IbSubscript(self, node: ast.IbSubscript) -> TypeDescriptor:
        value_type = self.visit(node.value)
        key_type = self.visit(node.slice)
        
        # 贯彻“一切皆对象”协议：询问类型如何处理下标
        trait = value_type.get_subscript_trait()
        if not trait:
            self.error(f"Type '{value_type.name}' is not subscriptable", node, code="SEM_003")
            return self._any_desc
            
        res = value_type.resolve_item(key_type)
        return res or self._any_desc

    def visit_IbCastExpr(self, node: ast.IbCastExpr) -> TypeDescriptor:
        """类型强转语义分析"""
        self.visit(node.value)
        # 决议目标类型
        target_type = self._resolve_type_by_name(node.type_name)
        if target_type:
            return target_type
        return self._any_desc
        
    def _resolve_type_by_name(self, name: str) -> Optional[TypeDescriptor]:
        # Helper for CastExpr which uses string name
        sym = self.symbol_table.resolve(name)
        if isinstance(sym, symbols.TypeSymbol):
            return sym.descriptor
        # Try builtins
        return self.prelude.get_builtin_types().get(name)

    def visit_IbBinOp(self, node: ast.IbBinOp) -> TypeDescriptor:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        
        # 贯彻“一切皆对象”：调用左操作数的自决议方法
        res = left_type.get_operator_result(node.op, right_type)
        if not res:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type.name}' and '{right_type.name}'", node, code="SEM_003")
            return self._any_desc
        return res

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp) -> TypeDescriptor:
        operand_type = self.visit(node.operand)
        
        # 贯彻“一切皆对象”：调用操作数的自决议方法 (other=None 表示一元运算)
        res = operand_type.get_operator_result(node.op, None)
        if not res:
            self.error(f"Unary operator '{node.op}' not supported for type '{operand_type.name}'", node, code="SEM_003")
            return self._any_desc
        return res

    def visit_IbConstant(self, node: ast.IbConstant) -> TypeDescriptor:
        val = node.value
        # [Strict Registry] 从注册表获取描述符，确保物理隔离下的标识一致性
        if isinstance(val, bool): return self.registry.resolve("bool")
        elif isinstance(val, int): return self.registry.resolve("int")
        elif isinstance(val, float): return self.registry.resolve("float")
        elif isinstance(val, str): return self.registry.resolve("str")
        elif val is None: return self.registry.resolve("void")
        return self.registry.resolve("Any")

    def visit_IbName(self, node: ast.IbName) -> TypeDescriptor:
        # 1. 解析符号
        sym = self.symbol_table.resolve(node.id)
        
        if not sym:
            msg = f"Variable '{node.id}' is not defined"
            if self.in_behavior_expr:
                msg = f"Variable '{node.id}' used in behavior expression is not defined"
            self.error(msg, node, code="SEM_001")
            return self._any_desc

        self.node_to_symbol[node] = sym # 使用 UID 引用
        
        # 统一获取类型信息
        res = sym.descriptor
            
        return res

    def visit_IbAttribute(self, node: ast.IbAttribute) -> TypeDescriptor:
        base_type = self.visit(node.value)
        
        # 2. 处理内置方法注入
        member_sym = base_type.resolve_member(node.attr)
        
        if member_sym:
            self.node_to_symbol[node] = member_sym
            
            # [Axiom Hook] 自动合成绑定方法 (Bound Method)
            # 如果是实例方法且不是静态方法，则合成 BoundMethodMetadata
            if member_sym.kind == symbols.SymbolKind.FUNCTION and not member_sym.metadata.get("is_static"):
                # 如果是类方法且第一个参数名为 self，或者是内置方法且 param_types[0] 是 Receiver 类型
                # 简单判断：如果 receiver 不是模块，则视为绑定调用
                if not isinstance(base_type, ModuleMetadata):
                    return BoundMethodMetadata(receiver_type=base_type, function_type=member_sym.descriptor)
            
            return member_sym.descriptor
            
        # 2. [Dynamic Resolution] 如果是动态类型（Any/var），允许访问任意属性并返回 Any
        if base_type.is_dynamic():
            # [IES 2.0] 动态代理：创建一个虚拟符号记录在侧表中
            virtual_sym = symbols.VariableSymbol(
                name=node.attr, 
                kind=symbols.SymbolKind.VARIABLE, 
                descriptor=self._any_desc, 
                metadata={"is_dynamic_proxy": True}
            )
            self.node_to_symbol[node] = virtual_sym
            return self._any_desc

        self.error(f"Type '{base_type.name}' has no member '{node.attr}'", node, code="SEM_001")
        return self._any_desc

    def visit_IbCall(self, node: ast.IbCall) -> TypeDescriptor:
        func_type = self.visit(node.func)
        arg_types = [self.visit(arg) for arg in node.args]
        
        # 1. 检查是否可调用 (使用 Trait 契约)
        call_trait = func_type.get_call_trait()
        if not call_trait:
            self.error(f"Type '{func_type.name}' is not callable", node, code="SEM_003")
            return self._any_desc
            
        # 2. 贯彻“一切皆对象”：询问类型对象调用后的返回结果
        res = func_type.resolve_return(arg_types)
        if not res:
            # 尝试获取更具体的错误信息
            if isinstance(func_type, FunctionMetadata):
                param_types = func_type.param_types
                if len(arg_types) != len(param_types):
                    self.error(f"Function expected {len(param_types)} arguments, but got {len(arg_types)}", node, code="SEM_005")
                else:
                    for i, (expected, actual) in enumerate(zip(param_types, arg_types)):
                        if not actual.is_assignable_to(expected):
                            hint = actual.get_diff_hint(expected)
                            self.error(f"Argument {i+1} type mismatch: expected '{expected.name}', but got '{actual.name}'", node, code="SEM_003", hint=hint)
            else:
                self.error(f"Invalid call to '{func_type.name}'", node, code="SEM_003")
            return self._any_desc
            
        return res

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr) -> TypeDescriptor:
        self.in_behavior_expr = True
        try:
            for seg in node.segments:
                if isinstance(seg, ast.IbASTNode):
                    self.visit(seg)
        finally:
            self.in_behavior_expr = False
        return self._behavior_desc

    def _resolve_type(self, node: Optional[ast.IbASTNode], safe: bool = False) -> TypeDescriptor:
        """解析 AST 节点中的类型标注 (Axiom-Driven)"""
        if not node: return self._void_desc
        
        if isinstance(node, ast.IbName):
            # 1. 尝试内置类型 (int, str, list 等)
            t = self.prelude.get_builtin_types().get(node.id)
            if t: return t
            
            # 2. 尝试符号表解析 (e.g., class name)
            sym = self.symbol_table.resolve(node.id)
            if sym:
                self.node_to_symbol[node] = sym
                # [FIX] 如果符号本身就是 TypeSymbol，直接返回其 descriptor
                if isinstance(sym, symbols.TypeSymbol):
                    return sym.descriptor
                return sym.descriptor
                
            if not safe:
                self.error(f"Unknown type '{node.id}'", node, code="SEM_001")
            return self._any_desc
            
        elif isinstance(node, ast.IbSubscript):
            # 处理泛型标注 (e.g., list[int], dict[str, int])
            base_type = self._resolve_type(node.value, safe=safe)
            
            # 决议泛型参数
            if isinstance(node.slice, ast.IbTuple):
                generic_args = [self._resolve_type(elt, safe=safe) for elt in node.slice.elts]
            else:
                generic_args = [self._resolve_type(node.slice, safe=safe)]
                
            # [Axiom-Driven] 使用 Factory 创建特化类型
            if base_type.name == "list" and len(generic_args) >= 1:
                desc = self.registry.factory.create_list(generic_args[0])
                self.registry.register(desc)
                return desc
            elif base_type.name == "dict" and len(generic_args) >= 2:
                desc = self.registry.factory.create_dict(generic_args[0], generic_args[1])
                self.registry.register(desc)
                return desc
            
            return base_type

        elif isinstance(node, ast.IbAttribute):
            if safe:
                if isinstance(node.value, ast.IbName):
                    base_sym = self.symbol_table.resolve(node.value.id)
                    if base_sym and base_sym.descriptor:
                        member_sym = base_sym.descriptor.resolve_member(node.attr)
                        if member_sym:
                            self.node_to_symbol[node] = member_sym
                            return member_sym.descriptor
                return self._any_desc
                
            base_type = self.visit(node.value)
            member_sym = base_type.resolve_member(node.attr)
            if member_sym:
                self.node_to_symbol[node] = member_sym
                return member_sym.descriptor
            self.error(f"Unknown type '{node.attr}' in '{base_type.name}'", node, code="SEM_001")
            
        return self._any_desc

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
                if node not in self.node_to_symbol:
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
            self.issue_tracker.warning(msg, root)
            
            self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, f"[INTEGRITY WARNING] {msg}:")
            for m in missing_bindings[:10]:
                self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, f"  - {m}")

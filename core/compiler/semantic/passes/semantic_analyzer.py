from typing import Dict, Optional, List, Any
from core.kernel import ast as ast
from core.compiler.common.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.host.host_interface import HostInterface

from core.kernel import symbols
from core.kernel.symbols import (
    SymbolTable, SymbolKind, TypeSymbol, FunctionSymbol, VariableSymbol
)
from core.kernel.types.descriptors import (
    TypeDescriptor, ClassMetadata, FunctionMetadata, ListMetadata, DictMetadata,
    ModuleMetadata, BoundMethodMetadata
)

from .prelude import Prelude
from .collector import SymbolCollector, LocalSymbolCollector, SymbolExtractor
from .resolver import TypeResolver
from .side_table import SideTableManager
from .scope_manager import ScopeManager
from core.kernel.blueprint import CompilationResult

class SemanticAnalyzer:
    """
    语义分析器：执行静态分析和类型检查。
    贯彻"一切皆对象"思想：Analyzer 仅作为调度者，核心逻辑由 TypeDescriptor (Axiom) 自决议。

     使用组件组合模式：
    - SideTableManager: 管理语义分析侧表
    - ScopeManager: 管理作用域和场景栈
    """
    def __init__(self, issue_tracker: Optional[DiagnosticReporter] = None, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None, registry: Optional[Any] = None, module_name: Optional[str] = None):
        self.issue_tracker = issue_tracker or IssueTracker()
        self.host_interface = host_interface
        self.debugger = debugger or core_debugger
        self.registry = registry
        self._module_name = module_name

        if self.registry is None:
            raise ValueError("SemanticAnalyzer requires a valid MetadataRegistry instance. 'None' is not allowed.")

        self._any_desc = self.registry.resolve("any")
        self._auto_desc = self.registry.resolve("auto")
        self._void_desc = self.registry.resolve("void")
        self._bool_desc = self.registry.resolve("bool")
        self._int_desc = self.registry.resolve("int")
        self._str_desc = self.registry.resolve("str")
        self._behavior_desc = self.registry.resolve("behavior")

        self.current_return_type: Optional[TypeDescriptor] = None
        self.current_class: Optional[ClassMetadata] = None
        self.in_behavior_expr = False

        self.prelude = Prelude(self.host_interface, registry=self.registry)

        self.side_table = SideTableManager()
        self.scope_manager = ScopeManager(module_name=module_name)

        self.symbol_table = self.scope_manager.global_scope()

    def _init_builtins(self):
        """注册内置静态符号"""
        
        # 1. 注册内置函数
        for name, func_desc in self.prelude.get_builtins().items():
            # 使用全局唯一的内置符号 UID，消除模块相关性
            sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, descriptor=func_desc, uid=f"builtin:{name}", metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 2. 注册内置类型
        for name, type_desc in self.prelude.get_builtin_types().items():
            # 仅注册真正的内置类型为 builtin UID。
            # 如果描述符标记为 is_user_defined，说明它是从外部或残留注册表中混入的，跳过。
            if getattr(type_desc, 'is_user_defined', False):
                continue
                
            sym = TypeSymbol(name=name, kind=SymbolKind.CLASS, descriptor=type_desc, uid=f"builtin:{name}", metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 3. 注册内置模块 (如果 Registry 中存在)
        for name, mod_desc in self.prelude.get_builtin_modules().items():
            sym = symbols.VariableSymbol(name=name, kind=SymbolKind.MODULE, descriptor=mod_desc, uid=f"builtin:{name}", metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 4. 注册内置变量/常量 (如 __file__, __dir__)
        for name, var_desc in self.prelude.get_builtin_variables().items():
            sym = symbols.VariableSymbol(name=name, kind=SymbolKind.VARIABLE, descriptor=var_desc, uid=f"builtin:{name}", is_const=True, metadata={"is_builtin": True})
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
            
            # Pass 3: llmexcept 关联和合法性检查
            self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 3: llmexcept binding and validation...")
            self._bind_llm_except(node)
            self.debugger.exit_scope(CoreModule.SEMANTIC)
            
            # Pass 3.5: 意图注释上下文验证 (@/@! 必须紧跟 LLM 调用)
            self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 3.5: Validating intent annotation context...")
            self._validate_intent_annotation_context(node)
            self.debugger.exit_scope(CoreModule.SEMANTIC)

            # Pass 4: 深度语义检查 (Body, Expressions, Type Checking)
            self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 4: Deep checking...")
            self.visit(node)
            self.debugger.exit_scope(CoreModule.SEMANTIC)
            
            # 自检校验：确保侧表完整性
            # 仅在没有收集到错误的情况下执行完整性检查，因为解析失败的节点本身就无法绑定
            if not self.issue_tracker.has_errors():
                self._validate_integrity(node)
            
            self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Static analysis complete.")
            
            if raise_on_error:
                self.issue_tracker.check_errors()

            return CompilationResult(
                module_ast=node if isinstance(node, ast.IbModule) else None,
                symbol_table=self.symbol_table,
                node_scenes=self.side_table.node_scenes,
                node_to_symbol=self.side_table.node_to_symbol,
                node_to_type=self.side_table.node_to_type,
                node_is_deferred=self.side_table.node_is_deferred,
                node_to_loc=self.side_table.node_to_loc,
                decision_maps=self.side_table.decision_maps,
                node_protection=self.side_table.node_protection
            )
        finally:
            self.debugger.exit_scope(CoreModule.SEMANTIC)

    def _bind_llm_except(self, node: ast.IbASTNode) -> None:
        """
        Pass 3: llmexcept 关联和合法性检查。
        
        遍历 AST，将 llmexcept 语句与前一个语句关联，
        并检查 llmexcept 的 target 是否包含 @~...~ 行为描述。
        """
        if isinstance(node, ast.IbModule):
            self._bind_llm_except_in_body(node.body, node)
        elif isinstance(node, ast.IbFunctionDef):
            self._bind_llm_except_in_body(node.body, node)
        elif isinstance(node, ast.IbLLMFunctionDef):
            pass
        elif isinstance(node, ast.IbClassDef):
            for method in node.body:
                if isinstance(method, ast.IbFunctionDef):
                    self._bind_llm_except_in_body(method.body, method)
                elif isinstance(method, ast.IbLLMFunctionDef):
                    pass

    def _bind_llm_except_in_body(self, body: List[ast.IbStmt], parent: ast.IbASTNode) -> None:
        """
        处理语句块中的 llmexcept 关联。

        注意：不扁平化 body，保持 IbLLMExceptionalStmt 作为包装器结构。
        这样解释器可以正确处理 LLMUncertaintyError。
        """
        if not body:
            return

        new_body = []
        i = 0
        while i < len(body):
            stmt = body[i]

            if isinstance(stmt, ast.IbLLMExceptionalStmt):
                # llmexcept 是一个独立的语句，需要与前一个语句关联
                if not new_body:
                    self.issue_tracker.error(
                        f"llmexcept must follow a statement, but no previous statement found.",
                        stmt, code="SEM_051"
                    )
                    i += 1
                    continue

                prev_stmt = new_body[-1]

                # 检查前一个语句是否包含行为描述
                if not self._stmt_contains_behavior(prev_stmt):
                    self.issue_tracker.error(
                        f"llmexcept must follow a statement containing a behavior expression '@~...~'. "
                        f"Found: '{prev_stmt.__class__.__name__}' without IbBehaviorExpr.",
                        stmt, code="SEM_050"
                    )

                # 关联侧表：被保护节点 UID -> llmexcept 处理器节点 UID
                # 这是实现解释器 visit 拦截的核心
                self.side_table.bind_protection(prev_stmt, stmt)

                # 同时在 AST 中建立关联，确保序列化时包含 target 字段
                stmt.target = prev_stmt

                # IbLLMExceptionalStmt 保留在 body 中，确保 Pass 4 深度检查和序列化能够访问到它
                # 它的重复执行问题将由 Interpreter.visit 逻辑处理
                new_body.append(stmt)

                # 递归处理 llmexcept body
                for body_stmt in stmt.body:
                    self._bind_llm_except(body_stmt)
            else:
                new_body.append(stmt)
                # 递归处理子节点
                self._bind_llm_except(stmt)

            i += 1

        # 更新 body
        if isinstance(parent, ast.IbModule):
            parent.body = new_body
        elif isinstance(parent, (ast.IbFunctionDef, ast.IbLLMFunctionDef)):
            parent.body = new_body
        elif isinstance(parent, ast.IbClassDef):
            # [FIX] 找到对应的 method 并更新其 body
            for method in parent.body:
                if isinstance(method, (ast.IbFunctionDef, ast.IbLLMFunctionDef)) and method.body is body:
                    method.body = new_body
                    break

    def _stmt_contains_behavior(self, stmt: ast.IbStmt) -> bool:
        """
        检查语句是否包含行为描述 @~...~。
        """
        if isinstance(stmt, ast.IbExprStmt):
            return self._expr_contains_behavior(stmt.value)
        elif isinstance(stmt, ast.IbIf):
            return self._expr_contains_behavior(stmt.test)
        elif isinstance(stmt, ast.IbWhile):
            return self._expr_contains_behavior(stmt.test)
        elif isinstance(stmt, ast.IbFor):
            return self._expr_contains_behavior(stmt.iter)
        elif isinstance(stmt, ast.IbAssign):
            return self._expr_contains_behavior(stmt.value)
        elif isinstance(stmt, ast.IbReturn):
            if stmt.value:
                return self._expr_contains_behavior(stmt.value)
        elif isinstance(stmt, ast.IbLLMExceptionalStmt):
            return self._stmt_contains_behavior(stmt.target) if stmt.target else False
        return False

    def _expr_contains_behavior(self, expr: ast.IbExpr) -> bool:
        """
        检查表达式是否包含行为描述 @~...~。
        """
        if isinstance(expr, ast.IbBehaviorExpr):
            return True
        elif isinstance(expr, ast.IbCall):
            # 检查方法调用
            if self._expr_contains_behavior(expr.func):
                return True
            for arg in expr.args:
                if self._expr_contains_behavior(arg):
                    return True
        elif isinstance(expr, ast.IbBinOp):
            return self._expr_contains_behavior(expr.left) or self._expr_contains_behavior(expr.right)
        elif isinstance(expr, ast.IbCompare):
            return self._expr_contains_behavior(expr.left) or self._expr_contains_behavior(expr.comparators[0])
        elif isinstance(expr, ast.IbUnaryOp):
            return self._expr_contains_behavior(expr.operand)
        elif isinstance(expr, ast.IbIfExp):
            return (self._expr_contains_behavior(expr.test) or 
                    self._expr_contains_behavior(expr.body) or 
                    self._expr_contains_behavior(expr.orelse))
        return False

    def visit(self, node: ast.IbASTNode) -> TypeDescriptor:
        # 标记作用域定义节点 (元数据驱动)
        if isinstance(node, (ast.IbModule, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbClassDef)):
            setattr(node, "_is_scope", True)

        self.side_table.bind_location(node, {
            "file_path": self.issue_tracker.file_path,
            "line": node.lineno,
            "column": node.col_offset
        })

        # 记录场景上下文侧表
        if isinstance(node, ast.IbExpr):
            self.side_table.bind_scene(node, self.scope_manager.current_scene())

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        res_type = visitor(node)
        
        # 记录类型推导侧表
        if isinstance(node, ast.IbExpr) and res_type:
            self.side_table.bind_type(node, res_type)
            
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
        if code == "INT_001":
            import traceback
            traceback.print_stack()
            raise Exception(message)
        self.issue_tracker.error(message, node, code=code, hint=hint)

    def visit_IbLLMExceptionalStmt(self, node: ast.IbLLMExceptionalStmt):
        """
        访问 llmexcept 语句。
        
        IbLLMExceptionalStmt 在 Pass 3 被 _bind_llm_except 处理，
        这里只需要访问 body 中的语句。
        """
        for stmt in node.body:
            self.visit(stmt)
        return self._void_desc

    def visit_IbRetry(self, node: ast.IbRetry):
        """访问 retry 语句"""
        return self._void_desc

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
        if not sym or not sym.is_type:
            return self._void_desc
            
        self.side_table.bind_symbol(node, sym)
        
        old_table = self.symbol_table
        if sym.owned_scope:
            self.symbol_table = sym.owned_scope
            
        old_class = self.current_class
        # 使用 is_class() 判定，消除对 ClassMetadata 的直接依赖
        if sym.descriptor.is_class():
            # 内部仍需类型转换为 ClassMetadata 以支持 members 访问，但判定逻辑已公理化
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

            # 只有当变量已在 *当前* 作用域定义时，才考虑复用或覆盖。
            # 如果变量在父级作用域，则直接定义新符号以实现遮蔽。
            if name in self.symbol_table.symbols:
                existing = self.symbol_table.symbols[name]
                if not allow_overwrite:
                    self.side_table.bind_symbol(node, existing)
                    return existing
            
            # 检查是否由 Scheduler 注入的特殊符号（如模块）
            # 这些符号通常在全局表中，不应被随意遮蔽，除非是局部变量
            if name not in self.symbol_table.symbols:
                existing_global = self.symbol_table.resolve(name)
                if existing_global and existing_global.kind in (SymbolKind.MODULE, SymbolKind.CLASS):
                    # 模块和类在语义上不建议被遮蔽，但如果是 auto 定义则允许
                    pass

            sym = symbols.VariableSymbol(name=name, kind=symbols.SymbolKind.VARIABLE, descriptor=var_type, def_node=node)
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            
            # [Axiom Hook] 同步到描述符的成员表中 (保持物理隔离下的元数据完备性)
            if self.current_class:
                self.current_class.members[name] = sym

            # 记录侧表映射
            self.side_table.bind_symbol(node, sym)
            return sym
        except ValueError as e:
            self.error(str(e), node, code="SEM_003")
            return None

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not sym.is_function:
            return self._void_desc
            
        self.side_table.bind_symbol(node, sym)
        # 决议真实的函数签名并更新元数据
        param_types = [self._resolve_type(arg.annotation) for arg in node.args]
        # 类方法第一个参数是 self
        if self.current_class:
            param_types.insert(0, self.current_class)
            
        ret_type = self._resolve_type(node.returns)
        
        # 使用 WritableTrait 更新元数据，消除对实现类的直接依赖
        call_trait = sym.descriptor.get_call_trait()
        writable = call_trait.get_writable_trait() if call_trait else None

        if writable:
            # 安全回填分析得到的参数与返回类型
            writable.update_signature(param_types, ret_type)
            
        # 进入局部作用域
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table, name=node.name)
        self.symbol_table = local_scope
        
        # 将局部作用域回填到符号中，以便序列化器能够递归发现局部符号
        if sym.is_function:
            sym.owned_scope = local_scope
        
        # 隐式 self 注入：如果是类方法，在局部作用域注入 self 符号
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
        if not sym or not sym.is_function:
            return self._void_desc
            
        self.side_table.bind_symbol(node, sym)
        # 决议真实的函数签名并更新元数据
        param_types = [self._resolve_type(arg.annotation) for arg in node.args]
        if self.current_class:
            param_types.insert(0, self.current_class)
            
        ret_type = self._resolve_type(node.returns) if node.returns else self._str_desc
        # [P3 FIX] LLM 函数默认返回 str 而非 void
        # 注意：这里的 "str" 语义是"文本接收"（LLM 生成的内容），而非纯字符串类型
        # [Future Evolution] 未来演进方向：
        # 1. ReceiveMode 枚举统一处理 IMMEDIATE/DEFERRED/CLASS_CAST 上下文
        # 2. ParserCapability.get_llm_prompt_fragment() 注入系统提示词
        # 3. TypeAxiom.get_return_type_hint() 提供类型特定的返回提示
        
        # 使用 WritableTrait 更新元数据，消除对实现类的直接依赖
        call_trait = sym.descriptor.get_call_trait()
        writable = call_trait.get_writable_trait() if call_trait else None
        
        if writable:
            # 安全回填分析得到的参数与返回类型
            writable.update_signature(param_types, ret_type)
            
        # 进入局部作用域以校验提示词中的占位符
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table, name=node.name)
        self.symbol_table = local_scope
        
        # 将局部作用域回填到符号中，以便序列化器能够递归发现局部符号
        if sym.is_function:
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
            if ret_type is None:
                self.error(f"Invalid return type: got None (void or unknown)", node, code="SEM_003")
            elif self.current_return_type and not ret_type.is_assignable_to(self.current_return_type):
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
                # 决议最终目标类型 (Inference Policy)
                sym = self.symbol_table.symbols.get(var_name)
                
                if declared_type:
                    # 1. 有显式标注：优先尊重标注，除非标注是动态的 (auto/any)
                    if declared_type.is_dynamic():
                        target_type = val_type
                    else:
                        target_type = declared_type
                    
                    # [SEM_002] 检查是否在当前作用域重复声明
                    if var_name in self.symbol_table.symbols:
                        existing = self.symbol_table.symbols[var_name]
                        # 允许同一个节点在 Pass 3 更新它在 Pass 1 定义的符号类型
                        if existing.def_node is not node:
                            # 如果不是内置符号，且不是同类型的重新赋值（IBCI 允许同名覆盖但通常通过 allow_overwrite 控制）
                            # 这里我们遵循更严格的静态语言规则：同作用域禁止显式类型重声明
                            self.error(f"Variable '{var_name}' is already defined in this scope", node, code="SEM_002")
                    
                    # 定义或更新符号
                    sym = self._define_var(var_name, target_type, node, allow_overwrite=True)
                else:
                    # 2. 无标注：如果尚未定义，或者现有定义是动态的 (any/auto)，则进行推导
                    if not sym or sym.descriptor.is_dynamic():
                        sym = self._define_var(var_name, val_type, node, allow_overwrite=(sym is not None))
                
                if sym:
                    self.side_table.bind_symbol(actual_target, sym)
                    self.side_table.bind_type(target_node, sym.descriptor)
                    if isinstance(target_node, ast.IbTypeAnnotatedExpr) and isinstance(target_node.target, ast.IbName):
                        self.side_table.bind_symbol(target_node.target, sym)
                        self.side_table.bind_type(target_node.target, sym.descriptor)
                    
                    # [P2 FIX] 行为描述行 Lambda 化判断 + 即时上下文处理
                    # [Future Evolution] 未来将演进为 ReceiveMode 枚举：
                    # - IMMEDIATE: 即时执行上下文，behavior 表达式直接执行 LLM 调用
                    # - DEFERRED: 延迟执行上下文，behavior 表达式被包装为 callable
                    # - CLASS_CAST: 类型转换上下文，behavior 表达式执行后进行类型转换
                    # 相关演进：ParserCapability.get_llm_prompt_fragment() 用于注入系统提示词
                    target_desc = sym.descriptor
                    is_explicit_callable = False

                    if target_desc:
                        call_cap = target_desc.get_call_trait()
                        is_dynamic = target_desc.is_dynamic()

                        is_explicit_callable = (call_cap is not None) or is_dynamic

                    if isinstance(node.value, ast.IbBehaviorExpr):
                        if is_explicit_callable:
                            # 延迟上下文：behavior 表达式被包装为 callable，延迟执行
                            self.side_table.set_deferred(node.value, True)
                            val_type = self._behavior_desc
                        else:
                            # [P2 FIX] 即时上下文：behavior 表达式立即执行，返回 str 类型（LLM 调用结果）
                            # 注意：这里的 "str" 语义是"文本接收"，而非纯字符串类型
                            # [Future] 未来可通过 ReceiveMode.IMMEDIATE 统一处理，并在解释器层面注入相关提示词
                            self.side_table.set_deferred(node.value, False)
                            val_type = self._str_desc
                    
                    if not val_type.is_assignable_to(sym.descriptor):
                        hint = val_type.get_diff_hint(sym.descriptor)
                        self.error(f"Type mismatch: Cannot assign '{val_type.name}' to '{sym.descriptor.name}'", node, code="SEM_003", hint=hint)
            else:
                # 处理属性或下标赋值 (e.g., p.val = 1)
                target_type = self.visit(target_node)
                if target_type and not val_type.is_assignable_to(target_type):
                    hint = val_type.get_diff_hint(target_type)
                    self.error(f"Type mismatch: Cannot assign '{val_type.name}' to target of type '{target_type.name}'", node, code="SEM_003", hint=hint)
        
        return self._void_desc

    def visit_IbIf(self, node: ast.IbIf):
        # 1. 条件测试属于 BRANCH 场景
        self.scope_manager.push_scene(ast.IbScene.BRANCH)
        # 记录控制流节点本身的场景
        self.side_table.bind_scene(node, ast.IbScene.BRANCH)
        try:
            self.visit(node.test)
        finally:
            self.scope_manager.pop_scene()
            
        # 2. Body 和 Orelse 恢复父级场景
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
            
        return self._void_desc

    def visit_IbWhile(self, node: ast.IbWhile):
        # 1. 循环条件属于 LOOP 场景
        self.scope_manager.push_scene(ast.IbScene.LOOP)
        # 记录控制流节点本身的场景
        self.side_table.bind_scene(node, ast.IbScene.LOOP)
        try:
            self.visit(node.test)
        finally:
            self.scope_manager.pop_scene()
            
        # 2. 循环体
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
            
        return self._void_desc

    def visit_IbFor(self, node: ast.IbFor):
        # 1. 迭代头部属于 LOOP 场景
        self.scope_manager.push_scene(ast.IbScene.LOOP)
        # 记录控制流节点本身的场景
        self.side_table.bind_scene(node, ast.IbScene.LOOP)
        try:
            iter_type = self.visit(node.iter)
            
            # 统一循环协议检查
            if node.target is None:
                # 情况 1: 条件驱动模式 (for @~...~: 或 for is_ready():)
                # 语义：等同于 while，要求表达式具有“布尔评估能力”
                # 贯彻“一切皆对象”协议：询问类型是否支持布尔决议
                # 即使是 behavior 类型，在 is_truthy 协议下也是合法的
                if not iter_type.is_dynamic() and not iter_type.is_behavior() and iter_type.name != "bool":
                    # TODO: 未来可引入 BooleanCapability 接口进行更严谨的校验
                    pass
            else:
                # 情况 2: 标准迭代模式 (for i in list: 或 for i in @~...~:)
                # 贯彻“一切皆对象”协议：询问类型如何提供迭代元素
                # 如果是 behavior 类型，我们认为它“潜在可迭代”
                if iter_type.is_behavior():
                    element_type = self._any_desc 
                else:
                    iter_trait = iter_type.get_iter_trait()
                    if iter_trait:
                        # 通过 TypeDescriptor 统一获取 element_type，以支持引用解析
                        element_type = iter_type.get_element_type() or self._any_desc
                    else:
                        self.error(f"Type '{iter_type.name}' is not iterable", node.iter, code="SEM_003")
                        element_type = self._any_desc
                
                for var_name, target in SymbolExtractor.get_assigned_names(node):
                    # 优先使用显式类型标注，而非推导出的 element_type
                    effective_type = element_type
                    if isinstance(target, ast.IbTypeAnnotatedExpr):
                        effective_type = self.visit(target.annotation)
                    
                    # 检查是否已在 Pass 2.5 预扫描中定义
                    sym = self.symbol_table.symbols.get(var_name)
                    
                    # [STABILIZATION] 只有当新类型比现有类型更精确时才更新
                    if not sym or sym.descriptor.is_dynamic():
                        sym = self._define_var(var_name, effective_type, target, allow_overwrite=(sym is not None))
                    elif not effective_type.is_dynamic():
                        # 如果新类型不是 Any，则强制更新（覆盖之前的推导）
                        sym.descriptor = effective_type
                    
                    if sym:
                        self.side_table.bind_symbol(target, sym)
        finally:
            self.scope_manager.pop_scene()
            
        # 2. 循环体
        for stmt in node.body:
            self.visit(stmt)
            
        return self._void_desc

    def visit_IbExprStmt(self, node: ast.IbExprStmt):
        res = self.visit(node.value)
        return res

    def visit_IbAugAssign(self, node: ast.IbAugAssign):
        self.visit(node.target)
        self.visit(node.value)
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
                self.side_table.bind_symbol(target, sym)

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
                # 绑定到 alias 节点，以便解释器正确获取 UID
                self.side_table.bind_symbol(alias, sym)
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
                # 绑定到 alias 节点
                self.side_table.bind_symbol(alias, sym)
            else:
                self.error(f"Cannot import name '{alias.name}' from '{node.module}'", node, code="SEM_001")
                self._define_var(name, self._any_desc, node)
                
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

    def visit_IbIntentAnnotation(self, node: ast.IbIntentAnnotation):
        """访问意图注释节点 - @ 和 @! 专用"""
        # 访问内部的意图信息
        self.visit(node.intent)
        return self._void_desc

    def visit_IbIntentStackOperation(self, node: ast.IbIntentStackOperation):
        """访问意图栈操作节点 - @+ 和 @- 专用"""
        # 访问内部的意图信息
        self.visit(node.intent)
        return self._void_desc

    def _validate_intent_annotation_context(self, node: ast.IbASTNode) -> None:
        """
        Pass 3.5: 意图注释上下文验证。

        检查 IbIntentAnnotation (@/@!) 必须紧跟**后面**的行为表达式。
        @+/@- (IbIntentStackOperation) 可以独立存在，无需检查。

        正确用法示例：
            @ 用简洁回复
            result = @~打招呼~
        """
        if isinstance(node, ast.IbModule):
            self._validate_intent_in_body(node.body)
        elif isinstance(node, ast.IbFunctionDef):
            self._validate_intent_in_body(node.body)
        elif isinstance(node, ast.IbLLMFunctionDef):
            pass
        elif isinstance(node, ast.IbClassDef):
            for method in node.body:
                if isinstance(method, ast.IbFunctionDef):
                    self._validate_intent_in_body(method.body)
                elif isinstance(method, ast.IbLLMFunctionDef):
                    pass

    def _validate_intent_in_body(self, body: List[ast.IbStmt]) -> None:
        """验证语句块中的意图注释上下文"""
        if not body:
            return

        i = 0
        while i < len(body):
            stmt = body[i]

            if isinstance(stmt, ast.IbIntentAnnotation):
                if i == len(body) - 1:
                    self.issue_tracker.error(
                        f"Intent annotation '@' must be followed by a behavior expression '@~...~'. "
                        f"This is the last statement with no following LLM call.",
                        stmt, code="SEM_060"
                    )
                else:
                    next_stmt = body[i + 1]
                    if not self._stmt_contains_behavior(next_stmt):
                        self.issue_tracker.error(
                            f"Intent annotation '@' must be followed by a behavior expression '@~...~'. "
                            f"Following statement is '{next_stmt.__class__.__name__}' which does not contain a behavior expression.",
                            stmt, code="SEM_060"
                        )

            elif isinstance(stmt, ast.IbLLMExceptionalStmt):
                self._validate_intent_in_body(stmt.body)

            i += 1

    def _stmt_contains_behavior(self, stmt: ast.IbStmt) -> bool:
        """检查语句是否包含行为表达式"""
        if isinstance(stmt, ast.IbExprStmt):
            return self._expr_contains_behavior(stmt.value)
        elif isinstance(stmt, ast.IbAssign):
            return self._expr_contains_behavior(stmt.value)
        elif isinstance(stmt, ast.IbReturn):
            if stmt.value:
                return self._expr_contains_behavior(stmt.value)
        elif isinstance(stmt, ast.IbExprStmt) and isinstance(stmt.value, ast.IbBehaviorExpr):
            return True
        return False

    def _expr_contains_behavior(self, expr: ast.IbExpr) -> bool:
        """检查表达式是否包含行为表达式"""
        if isinstance(expr, ast.IbBehaviorExpr):
            return True
        if isinstance(expr, ast.IbCall):
            func = expr.func
            if isinstance(func, ast.IbAttribute):
                if func.attr in ("call", "complete", "generate", "execute", "run", "invoke", "ask"):
                    return True
                if isinstance(func.value, ast.IbName):
                    if func.value.id in ("llm", "LLM", "model", "Model", "ai", "AI"):
                        return True
            elif isinstance(func, ast.IbName):
                if func.id in ("call", "complete", "generate", "llm", "LLM"):
                    return True
        return False

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
        if not res:
            # 特殊处理：如果是 list 且 key 是 int，返回其 element_type
            if value_type.get_base_axiom_name() == "list" and key_type.get_base_axiom_name() == "int":
                return value_type.get_element_type() or self._any_desc
            # 如果是 list/str 且 key 是 slice，返回自身类型
            if value_type.get_base_axiom_name() in ("list", "str") and key_type.get_base_axiom_name() == "slice":
                return value_type
            
        return res or self._any_desc

    def visit_IbSlice(self, node: ast.IbSlice) -> TypeDescriptor:
        """分析切片表达式"""
        if node.lower: self.visit(node.lower)
        if node.upper: self.visit(node.upper)
        if node.step: self.visit(node.step)
        
        # 暂时返回预定义的 slice 描述符
        return self.registry.resolve("slice") or self._any_desc

    def visit_IbCastExpr(self, node: ast.IbCastExpr) -> TypeDescriptor:
        """类型强转语义分析"""
        self.visit(node.value)
        # 支持复杂类型标注 (如 list[int])，消除硬编码名称查找
        target_type = self._resolve_type(node.type_annotation)
        if target_type:
            self.side_table.bind_type(node, target_type)
            return target_type
        return self._any_desc
        
    def _resolve_type_by_name(self, name: str) -> Optional[TypeDescriptor]:
        # Helper for CastExpr which uses string name
        sym = self.symbol_table.resolve(name)
        if sym and sym.is_type:
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
        # 委托给注册表根据原生值解析描述符，消除分析器对 Python 类型的硬编码依赖
        desc = self.registry.resolve_from_value(val)
        if desc:
            return desc
        return self.registry.resolve("any")

    def visit_IbName(self, node: ast.IbName) -> TypeDescriptor:
        # 1. 解析符号
        sym = self.symbol_table.resolve(node.id)
        
        if not sym:
            msg = f"Variable '{node.id}' is not defined"
            if self.in_behavior_expr:
                msg = f"Variable '{node.id}' used in behavior expression is not defined"
            self.error(msg, node, code="SEM_001")
            return self._any_desc

        self.side_table.bind_symbol(node, sym)
        
        # 统一获取类型信息
        res = sym.descriptor
            
        return res

    def visit_IbAttribute(self, node: ast.IbAttribute) -> TypeDescriptor:
        base_type = self.visit(node.value)
        
        # 2. 处理内置方法注入
        member_sym = base_type.resolve_member(node.attr)
        
        if member_sym:
            self.side_table.bind_symbol(node, member_sym)
            # [Axiom Hook] 自动合成绑定方法 (Bound Method)
            # 如果是实例方法且不是静态方法，则合成 BoundMethodMetadata
            if member_sym.is_function and not member_sym.metadata.get("is_static"):
                # 使用 is_module() 判断，取代对 ModuleMetadata 的依赖
                if not base_type.is_module():
                    # 使用工厂创建以确保驻留和能力注入
                    return self.registry.factory.create_bound_method(base_type, member_sym.descriptor)
            
            return member_sym.descriptor
            
        # 2. [Dynamic Resolution] 如果是动态类型（any/auto），允许访问任意属性并返回 any
        if base_type.is_dynamic():
            # 动态代理：创建一个虚拟符号记录在侧表中
            virtual_sym = symbols.VariableSymbol(
                name=node.attr, 
                kind=symbols.SymbolKind.VARIABLE, 
                descriptor=self._any_desc, 
                metadata={"is_dynamic_proxy": True}
            )
            self.side_table.bind_symbol(node, virtual_sym)
            return self._any_desc

        self.error(f"Type '{base_type.name}' has no member '{node.attr}'", node, code="SEM_001")
        return self._any_desc

    def visit_IbCall(self, node: ast.IbCall) -> TypeDescriptor:
        func_type = self.visit(node.func)
        arg_types = [self.visit(arg) for arg in node.args]
        
        # 0. 特殊处理内置类型的构造函数调用
        # 当 TypeDescriptor 没有 get_call_trait() 但类型名是内置类型时，
        # 允许构造函数调用并返回对应类型
        if isinstance(func_type, TypeDescriptor) and not func_type.get_call_trait():
            type_name = func_type.name
            if type_name in ('str', 'int', 'float', 'bool', 'list', 'dict'):
                return func_type
        
        # 1. 检查是否可调用 (使用 Trait 契约)
        call_trait = func_type.get_call_trait()
        if not call_trait:
            self.error(f"Type '{func_type.name}' is not callable", node, code="SEM_003")
            return self._any_desc
            
        # 2. 贯彻“一切皆对象”：询问类型对象调用后的返回结果
        res = func_type.resolve_return(arg_types)
        
        if not res:
            # 通过 Trait 提取签名信息进行诊断
            if call_trait and hasattr(call_trait, 'param_types'):
                param_types = call_trait.param_types
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
        # 绑定当前执行场景 (BRANCH/LOOP/GENERAL)，以便运行时注入正确的系统提示词
        self.side_table.bind_scene(node, self.scope_manager.current_scene())
        
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
                self.side_table.bind_symbol(node, sym)
                # 如果符号本身就是 TypeSymbol，直接返回其 descriptor
                if sym.is_type:
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
                
            # 使用 resolve_specialization 替代硬编码判断，实现真正的类型演算
            return base_type.resolve_specialization(generic_args)

        elif isinstance(node, ast.IbAttribute):
            if safe:
                if isinstance(node.value, ast.IbName):
                    base_sym = self.symbol_table.resolve(node.value.id)
                    if base_sym and base_sym.descriptor:
                        member_sym = base_sym.descriptor.resolve_member(node.attr)
                        if member_sym:
                            self.side_table.bind_symbol(node, member_sym)
                            return member_sym.descriptor
                return self._any_desc
                
            base_type = self.visit(node.value)
            member_sym = base_type.resolve_member(node.attr)
            if member_sym:
                self.side_table.bind_symbol(node, member_sym)
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
                if not self.side_table.get_symbol(node):
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

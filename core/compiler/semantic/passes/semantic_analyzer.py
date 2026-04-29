from typing import Dict, Optional, List, Any
from core.kernel import ast as ast
from core.compiler.common.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

from core.kernel import symbols
from core.kernel.symbols import (
    SymbolTable, SymbolKind, TypeSymbol, FunctionSymbol, VariableSymbol
)
from core.kernel.spec import IbSpec, ClassSpec, FuncSpec, ListSpec, DictSpec, ModuleSpec, BoundMethodSpec

from .prelude import Prelude
from .collector import SymbolCollector, LocalSymbolCollector, SymbolExtractor
from .resolver import TypeResolver
from .side_table import SideTableManager
from .scope_manager import ScopeManager
from .behavior_dependency_analyzer import BehaviorDependencyAnalyzer
from core.kernel.blueprint import CompilationResult

class SemanticAnalyzer:
    """
    语义分析器：执行静态分析和类型检查。
    贯彻"一切皆对象"思想：Analyzer 仅作为调度者，核心逻辑由 IbSpec (Axiom) 自决议。

     使用组件组合模式：
    - SideTableManager: 管理语义分析侧表
    - ScopeManager: 管理作用域和场景栈
    """
    def __init__(self, issue_tracker: Optional[DiagnosticReporter] = None, debugger: Optional[Any] = None, registry: Optional[Any] = None, module_name: Optional[str] = None):
        self.issue_tracker = issue_tracker or IssueTracker()
        self.debugger = debugger or core_debugger
        self.registry = registry
        self._module_name = module_name

        if self.registry is None:
            raise ValueError("SemanticAnalyzer requires a valid SpecRegistry instance. 'None' is not allowed.")

        self._any_desc = self.registry.resolve("any")
        self._auto_desc = self.registry.resolve("auto")
        self._fn_desc = self.registry.resolve("fn")    # fn: callable inference sentinel
        self._void_desc = self.registry.resolve("void")
        self._bool_desc = self.registry.resolve("bool")
        self._int_desc = self.registry.resolve("int")
        self._str_desc = self.registry.resolve("str")
        self._behavior_desc = self.registry.resolve("behavior")
        self._deferred_desc = self.registry.resolve("deferred")

        self.current_return_type: Optional[IbSpec] = None
        self.current_class: Optional[ClassSpec] = None
        self.in_behavior_expr = False

        # When inside an `-> auto` function, accumulates all observed return types.
        # None means we are NOT in an auto-return function.
        self._auto_return_types: Optional[List[IbSpec]] = None

        # §9.2: llmexcept body 外部作用域快照（read-only 约束）
        # 非 None 时表示当前正在分析 llmexcept body；值为进入 body 前的变量名集合。
        self._llmexcept_outer_scope_names: Optional[frozenset] = None

        self.prelude = Prelude(registry=self.registry)

        self.side_table = SideTableManager()
        self.scope_manager = ScopeManager(module_name=module_name)

        self.symbol_table = self.scope_manager.global_scope()

    def _init_builtins(self):
        """注册内置静态符号"""
        
        # 1. 注册内置函数
        for name, func_desc in self.prelude.get_builtins().items():
            # 使用全局唯一的内置符号 UID，消除模块相关性
            sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, spec=func_desc, uid=f"builtin:{name}", metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 2. 注册内置类型
        for name, type_desc in self.prelude.get_builtin_types().items():
            # 仅注册真正的内置类型为 builtin UID。
            # 如果描述符标记为 is_user_defined，说明它是从外部或残留注册表中混入的，跳过。
            if getattr(type_desc, 'is_user_defined', False):
                continue
                
            sym = TypeSymbol(name=name, kind=SymbolKind.CLASS, spec=type_desc, uid=f"builtin:{name}", metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 3. 注册内置模块 (如果 Registry 中存在)
        for name, mod_desc in self.prelude.get_builtin_modules().items():
            sym = symbols.VariableSymbol(name=name, kind=SymbolKind.MODULE, spec=mod_desc, uid=f"builtin:{name}", metadata={"is_builtin": True})
            self.symbol_table.define(sym)

        # 4. 注册内置变量/常量 (如 __file__, __dir__)
        for name, var_desc in self.prelude.get_builtin_variables().items():
            sym = symbols.VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=var_desc, uid=f"builtin:{name}", is_const=True, metadata={"is_builtin": True})
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

            # Pass 5 (M5a): IbBehaviorExpr LLM 依赖图分析（DDG）
            # 仅在前序 Pass 无错误时才运行，避免因部分绑定缺失产生噪音误差。
            if not self.issue_tracker.has_errors():
                self.debugger.enter_scope(CoreModule.SEMANTIC, "Pass 5: Behavior dependency analysis (DDG)...")
                BehaviorDependencyAnalyzer(self.side_table).analyze(node)
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
                node_to_symbol=self.side_table.node_to_symbol,
                node_to_type=self.side_table.node_to_type,
                node_is_deferred=self.side_table.node_is_deferred,
                node_deferred_mode=self.side_table.node_deferred_mode,
                node_to_loc=self.side_table.node_to_loc,
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
        # [Task 1.1] 递归进入控制流容器节点，确保嵌套在循环/条件/try中的 llmexcept 能正确关联
        elif isinstance(node, ast.IbFor):
            self._bind_llm_except_in_body(node.body, node)
            if node.orelse:
                self._bind_llm_except_in_body(node.orelse, node)
        elif isinstance(node, ast.IbIf):
            self._bind_llm_except_in_body(node.body, node)
            if node.orelse:
                self._bind_llm_except_in_body(node.orelse, node)
        elif isinstance(node, ast.IbWhile):
            self._bind_llm_except_in_body(node.body, node)
            if node.orelse:
                self._bind_llm_except_in_body(node.orelse, node)
        elif isinstance(node, ast.IbTry):
            self._bind_llm_except_in_body(node.body, node)
            for handler in node.handlers:
                self._bind_llm_except_in_body(handler.body, handler)
            if node.orelse:
                self._bind_llm_except_in_body(node.orelse, node)
            if node.finalbody:
                self._bind_llm_except_in_body(node.finalbody, node)
        elif isinstance(node, ast.IbSwitch):
            for case in node.cases:
                self._bind_llm_except_in_body(case.body, case)

    def _bind_llm_except_in_body(self, body: List[ast.IbStmt], parent: ast.IbASTNode) -> None:
        """
        处理语句块中的 llmexcept 关联。

        C11：IbLLMExceptionalStmt 在 body 中**替换**其 target 而非紧随其后。

        正则情形（prev_stmt 不是条件驱动 for 循环）：
          - new_body 中弹出 prev_stmt，仅保留 IbLLMExceptionalStmt（它的 target
            字段直接指向 prev_stmt node）。
          - 容器 handler 遍历 body 时直接遇到 IbLLMExceptionalStmt 节点，
            vm_handle_IbLLMExceptionalStmt 负责 yield 其 target_uid 并管理 retry 循环。

        条件驱动 for 循环情形（prev_stmt 是 target=None 的 IbFor）：
          - IbFor 保留在 body 中，IbLLMExceptionalStmt **不**写入 body。
          - llmexcept handler 通过 ``IbFor.llmexcept_handler`` 字段直接引用，
            vm_handle_IbFor 在条件求值返回 uncertain 时内联执行 handler body 并重试。

        C11/P3（已完成）：所有 llmexcept 关联均通过 AST 字段建立，旧的
        ``node_protection`` 侧表 + ``_apply_protection_redirect`` 重定向机制已删除。
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

                # [Task 1.2 / C11/P1] 对条件驱动 for 循环的特殊处理：
                # llmexcept 保护的是条件表达式本身，而非整个 for 循环节点。
                # P1 修复：将 IbLLMExceptionalStmt 直接挂载到 IbFor.llmexcept_handler，
                # 不再使用已删除的 node_protection 侧表 + stmt.target = cond_expr。
                # 旧方案的缺陷：visit_IbLLMExceptionalStmt 会再次 visit(node.target = cond_expr)，
                # 从而将 node_to_type[behavior_expr] 从 bool 覆写为 behavior，
                # 导致运行时 IbBehaviorExpr 返回 IbString('0') 而非 IbBool(False)，
                # 造成条件驱动 for 循环永不退出（IbString('0') 是 truthy）。
                if isinstance(prev_stmt, ast.IbFor) and prev_stmt.target is None:
                    cond_expr = prev_stmt.iter
                    if not self._expr_contains_behavior(cond_expr):
                        self.issue_tracker.error(
                            "llmexcept following a condition-driven 'for' loop requires a behavior expression "
                            "'@~...~' as the loop condition.",
                            stmt, code="SEM_050"
                        )
                    # C11/P1: 将 llmexcept handler 直接挂载到 IbFor.llmexcept_handler；
                    # 显式保持 stmt.target = None（区别于正则情形）；
                    # IbLLMExceptionalStmt 不加入 body，IbFor 是 body 中的唯一主体。
                    stmt.target = None
                    prev_stmt.llmexcept_handler = stmt
                    # 仅递归处理 llmexcept body，不 append stmt 到 new_body
                    for body_stmt in stmt.body:
                        self._bind_llm_except(body_stmt)
                    i += 1
                    continue
                else:
                    # 检查前一个语句是否包含行为描述
                    if not self._stmt_contains_behavior(prev_stmt):
                        self.issue_tracker.error(
                            f"llmexcept must follow a statement containing a behavior expression '@~...~'. "
                            f"Found: '{prev_stmt.__class__.__name__}' without IbBehaviorExpr.",
                            stmt, code="SEM_050"
                        )
                    # C11: 正则情形——IbLLMExceptionalStmt 替换 prev_stmt 成为
                    # body 中的唯一条目；target 字段直接引用 prev_stmt node。
                    stmt.target = prev_stmt
                    new_body.pop()  # 弹出已入队的 prev_stmt
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
        # IbClassDef 需要特殊处理：找到对应的 method 并更新其 body
        if isinstance(parent, ast.IbClassDef):
            for method in parent.body:
                if isinstance(method, (ast.IbFunctionDef, ast.IbLLMFunctionDef)) and method.body is body:
                    method.body = new_body
                    break
        else:
            # 通用更新：按引用恒等性确定 body/orelse/finalbody 哪个字段传入了本次调用
            if hasattr(parent, 'body') and parent.body is body:
                parent.body = new_body
            elif hasattr(parent, 'orelse') and parent.orelse is body:
                parent.orelse = new_body
            elif hasattr(parent, 'finalbody') and parent.finalbody is body:
                parent.finalbody = new_body

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
        检查表达式是否包含行为描述 @~...~ 或 LLM 函数调用。
        """
        if isinstance(expr, (ast.IbBehaviorExpr, ast.IbBehaviorInstance)):
            return True
        elif isinstance(expr, ast.IbCastExpr):
            return self._expr_contains_behavior(expr.value)
        elif isinstance(expr, ast.IbTypeAnnotatedExpr):
            return self._expr_contains_behavior(expr.target)
        elif isinstance(expr, ast.IbFilteredExpr):
            return self._expr_contains_behavior(expr.expr) or self._expr_contains_behavior(expr.filter)
        elif isinstance(expr, ast.IbCall):
            func = expr.func
            if isinstance(func, ast.IbName):
                func_name = func.id
                sym = self.symbol_table.resolve(func_name)
                if sym:
                    if sym.kind == SymbolKind.LLM_FUNCTION or sym.metadata.get("is_llm"):
                        return True
            elif isinstance(func, ast.IbAttribute):
                if func.attr in ("call", "complete", "generate", "execute", "run", "invoke", "ask"):
                    return True
                if isinstance(func.value, ast.IbName):
                    if func.value.id in ("llm", "LLM", "model", "Model", "ai", "AI"):
                        return True
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

    def visit(self, node: ast.IbASTNode) -> IbSpec:
        # 标记作用域定义节点 (元数据驱动)
        if isinstance(node, (ast.IbModule, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbClassDef)):
            setattr(node, "_is_scope", True)

        self.side_table.bind_location(node, {
            "file_path": self.issue_tracker.file_path,
            "line": node.lineno,
            "column": node.col_offset
        })

        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        res_type = visitor(node)
        
        # 记录类型推导侧表
        if isinstance(node, ast.IbExpr) and res_type:
            self.side_table.bind_type(node, res_type)
            
        return res_type

    def generic_visit(self, node: ast.IbASTNode) -> IbSpec:
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

    def warn(self, message: str, node: ast.IbASTNode, code: str = "SEM_000", hint: Optional[str] = None):
        self.issue_tracker.warning(message, node, code=code, hint=hint)

    # ------------------------------------------------------------------ #
    # Return-path analysis helpers                                        #
    # ------------------------------------------------------------------ #

    def _all_paths_return(self, body: List[ast.IbStmt]) -> bool:
        """
        Conservative return-path check: returns True only if every execution
        path through *body* is guaranteed to hit a `return <value>` or `raise`.

        Rules (mirrors C/C++ flow analysis):
        - `return <value>` → terminal                       (bare `return` is not)
        - `raise`          → terminal
        - `if` with both branches fully returning → terminal
        - `switch` with a default case and all cases returning → terminal
        - `try` blocks are conservatively treated as non-terminal
        - Loops (`for`/`while`) are conservatively non-terminal (may not execute)
        - All other statements are transparent (pass-through)
        """
        for stmt in body:
            if isinstance(stmt, ast.IbReturn):
                if stmt.value is not None:
                    return True
            elif isinstance(stmt, ast.IbRaise):
                return True
            elif isinstance(stmt, ast.IbIf):
                has_else = bool(stmt.orelse)
                if has_else and self._all_paths_return(stmt.body) and self._all_paths_return(stmt.orelse):
                    return True
            elif isinstance(stmt, ast.IbSwitch):
                if self._switch_all_paths_return(stmt):
                    return True
        return False

    def _switch_all_paths_return(self, node: ast.IbSwitch) -> bool:
        """Return True if every case branch (including a default) returns."""
        has_default = any(c.pattern is None for c in node.cases)
        if not has_default:
            return False
        return all(self._all_paths_return(c.body) for c in node.cases)

    def visit_IbLLMExceptionalStmt(self, node: ast.IbLLMExceptionalStmt):
        """
        访问 llmexcept 语句。

        C11：IbLLMExceptionalStmt 已替换 prev_stmt 进入 body 主列表。
        ``node.target`` 是原 prev_stmt（IbAssign 或条件 for 的 IbFor），
        Pass 4 需先 visit 它以完成符号绑定、类型检查等。

        body 访问期间启用 §9.2 read-only 约束：捕获进入 body 前的外部
        作用域变量名集合，visit_IbAssign 在检测到对这些变量的赋值时发出 SEM_052。

        由于 LocalSymbolCollector（Pass 2.5）会把 body 内声明的变量预扫描进
        symbol_table.symbols，需排除 body 内直接声明（有类型标注）的变量，
        以避免误报 body-local 变量的 SEM_052。
        """
        # C11: 先访问 target（正则情形为 IbAssign；条件 for 情形为 IbFor）
        if node.target is not None:
            self.visit(node.target)

        # 收集 body 直接层级声明的变量名（body-local），以便从外部作用域集合中排除
        body_declared_names = self._collect_llmexcept_body_declared_names(node.body)

        saved_outer_scope = self._llmexcept_outer_scope_names
        self._llmexcept_outer_scope_names = (
            frozenset(self.symbol_table.symbols.keys()) - body_declared_names
        )
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self._llmexcept_outer_scope_names = saved_outer_scope
        return self._void_desc

    def _collect_llmexcept_body_declared_names(self, body: List[ast.IbStmt]) -> frozenset:
        """
        收集 llmexcept body 直接层级（非嵌套）中 **真正新声明** 的变量名。

        判断依据：LocalSymbolCollector（Pass 2.5）在预扫描时，若某变量在 body 外已存在，
        则 **不会** 覆盖其符号；只有在外部未定义时，才以 body 内的 IbAssign 节点作为
        def_node 创建新符号。因此，若 ``existing.def_node is stmt``，该变量是
        body-local 新声明；若 def_node 指向别处，则是对外部作用域变量的重声明。
        """
        result: set = set()
        for stmt in body:
            if isinstance(stmt, ast.IbAssign):
                for target in stmt.targets:
                    if (isinstance(target, ast.IbTypeAnnotatedExpr)
                            and isinstance(target.target, ast.IbName)):
                        name = target.target.id
                        existing = self.symbol_table.symbols.get(name)
                        # 仅当 LocalSymbolCollector 以本 stmt 为 def_node 预扫描时，
                        # 才视为 body-local 新声明（否则是外部变量的重声明，属于违规）
                        if existing is not None and existing.def_node is stmt:
                            result.add(name)
        return frozenset(result)

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
                # Python semantics: 'global x' is valid even if x is not yet defined in global scope.
                # Create a placeholder global symbol with 'any' type so that later assignments
                # inside this function can correctly route to the global scope.
                global_sym = symbols.VariableSymbol(
                    name=name,
                    kind=symbols.SymbolKind.VARIABLE,
                    spec=self._any_desc,
                    def_node=node,
                )
                global_scope.define(global_sym)
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
        # 使用 is_class() 判定，消除对 ClassSpec 的直接依赖
        if isinstance(sym.spec, ClassSpec):
            # 内部仍需类型转换为 ClassSpec 以支持 members 访问，但判定逻辑已公理化
            self.current_class = sym.spec
        else:
            self.current_class = None # Should not happen

        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.current_class = old_class
            self.symbol_table = old_table
        return self._void_desc

    def _define_var(self, name: str, var_type: IbSpec, node: ast.IbASTNode, allow_overwrite: bool = False):
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

            sym = symbols.VariableSymbol(name=name, kind=symbols.SymbolKind.VARIABLE, spec=var_type, def_node=node)
            self.symbol_table.define(sym, allow_overwrite=allow_overwrite)
            
            # [Axiom Hook] 同步到描述符的成员表中 (保持物理隔离下的元数据完备性)
            if self.current_class:
                from core.kernel.spec.member import MemberSpec
                self.current_class.members[name] = MemberSpec(
                    name=name,
                    kind="field",
                    type_name=sym.spec.name if sym.spec else "any",
                )

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
            
        # 没有返回类型标注时默认 auto（编译期推断），而非 void
        ret_type = self._resolve_type(node.returns) if node.returns else self._auto_desc
        
        # 使用 WritableTrait 更新元数据，消除对实现类的直接依赖
        call_trait = self.registry.get_call_cap(sym.spec or self._any_desc)
        writable = call_trait.get_writable_trait() if call_trait else None

        if writable:
            # 安全回填分析得到的参数与返回类型
            writable.update_signature(param_types, ret_type)
        else:
            # Known Limit 2 修复：嵌套函数的 FuncSpec 未被 Pass 2 (TypeResolver) 处理，
            # 此时直接创建携带正确签名的 FuncSpec 并替换符号的 spec。
            # 对于顶层函数，Pass 2 已正确设置 spec，此处为幂等操作。
            updated_spec = self.registry.factory.create_func(
                name=node.name,
                param_type_names=[p.name for p in param_types],
                return_type_name=ret_type.name if ret_type else "void"
            )
            updated_spec.is_user_defined = True
            sym.spec = updated_spec
            
        # 进入局部作用域
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table, name=node.name)
        self.symbol_table = local_scope
        
        # 将局部作用域回填到符号中，以便序列化器能够递归发现局部符号
        if sym.is_function:
            sym.owned_scope = local_scope
        
        # 临时保存并清除 current_class，避免函数参数（self、形参）和
        # 函数体内的局部变量被错误注册为类的成员字段。
        # current_class 的真实值仍可通过 saved_class 在需要时访问。
        saved_class = self.current_class
        
        # 隐式 self 注入：如果是类方法，在局部作用域注入 self 符号
        if saved_class:
            # self 的类型就是当前类
            self.current_class = None  # 防止 _define_var 将 self 注册为类成员
            self._define_var("self", saved_class, node)
            
            # super() 支持：在类方法作用域内注入 super 符号。
            # 类型：如果父类存在则为父类类型（ClassSpec），否则为 any。
            # super 符号使用固定 UID "builtin:super"，与运行时 IbSuperProxy 注入一致。
            parent_spec = None
            if saved_class.parent_name:
                parent_spec = self.registry.resolve(saved_class.parent_name)
            super_type = parent_spec if parent_spec else self._any_desc
            super_sym = symbols.VariableSymbol(
                name="super",
                kind=symbols.SymbolKind.VARIABLE,
                spec=super_type,
                def_node=node,
            )
            super_sym.uid = "builtin:super"
            self.symbol_table.define(super_sym, allow_overwrite=True)

        # 注册参数（current_class=None 确保参数不会被注册为类成员）
        self.current_class = None
        for i, arg_node in enumerate(node.args):
            # 索引偏移：类方法的签名中包含隐含的 self
            sig_idx = i + 1 if saved_class else i
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
        old_auto_returns = self._auto_return_types

        is_auto_return = (ret_type is self._auto_desc)
        if is_auto_return:
            # Accumulate actual return types to infer the real return type.
            self._auto_return_types = []
            self.current_return_type = None  # no constraint yet; collect first
        else:
            self._auto_return_types = None
            self.current_return_type = ret_type

        try:
            for stmt in node.body:
                self.visit(stmt)

            # ── Return-path analysis ──────────────────────────────────────
            if is_auto_return:
                # Resolve inferred return type from collected branches
                unique = list({s.name: s for s in (self._auto_return_types or [])}.values())
                if not unique:
                    inferred = self._void_desc
                elif len(unique) == 1:
                    inferred = unique[0]
                else:
                    self.error(
                        f"Function '{node.name}' is declared '-> auto' but returns conflicting types: "
                        + ", ".join(f"'{s.name}'" for s in unique),
                        node, code="SEM_026",
                    )
                    inferred = self._any_desc

                # Backfill the inferred type into the function spec.
                # `writable` and `sym` are already in scope from above.
                if writable:
                    writable.update_signature(param_types, inferred)
                elif sym.spec and isinstance(sym.spec, FuncSpec):
                    sym.spec.return_type_name = inferred.name

            elif ret_type is not self._void_desc:
                # Non-void non-auto function: warn if not all paths return
                if not self._all_paths_return(node.body):
                    self.warn(
                        f"Not all code paths in function '{node.name}' return a value.",
                        node, code="SEM_025",
                        hint="Add a return statement at the end of the function.",
                    )
        finally:
            self.current_return_type = old_ret
            self._auto_return_types = old_auto_returns
            self.current_class = saved_class  # 恢复类上下文
            self.symbol_table = old_table

        # [Pass 2 backfill] 将解析后的方法签名回填到类成员表的 MethodMemberSpec 中。
        # 在 Pass 1（Collector）中，MethodMemberSpec 只记录方法名和占位类型，
        # 返回类型和参数类型为默认值（"void"/"[]"）。
        # Pass 2 结束后，sym.spec（FuncSpec）携带了正确签名，可以回填。
        # 这使得 resolve_member('__call__') 能够返回正确的方法签名，
        # 从而支持 fn 变量持有可调用类实例后的准确调用返回类型推断。
        if saved_class and node.name in saved_class.members:
            from core.kernel.spec.member import MethodMemberSpec as _MethodMemberSpec
            m = saved_class.members[node.name]
            if isinstance(m, _MethodMemberSpec) and isinstance(sym.spec, FuncSpec):
                # 跳过 self（类方法的第一个参数）
                user_params = param_types[1:] if saved_class else param_types
                m.param_type_names = [p.name for p in user_params]
                m.return_type_name = sym.spec.return_type_name

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
        call_trait = self.registry.get_call_cap(sym.spec or self._any_desc)
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
        
        # 与 visit_IbFunctionDef 对称：临时清除 current_class，
        # 防止函数参数和局部变量被注册为类成员。
        saved_class = self.current_class
        
        if saved_class:
            self.current_class = None
            self._define_var("self", saved_class, node)
        
        self.current_class = None
        for i, arg_node in enumerate(node.args):
            sig_idx = i + 1 if saved_class else i
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
            self.current_class = saved_class  # 恢复类上下文
            self.symbol_table = old_table
        return self._void_desc

    def visit_IbReturn(self, node: ast.IbReturn):
        if node.value:
            # 禁止 `return @~...~`：行为表达式的目标类型由左值驱动，
            # 直接出现在 return 处会导致输出约束不明确。
            # 用户应先赋值给有类型的局部变量，再 return 该变量。
            if isinstance(node.value, (ast.IbBehaviorExpr, ast.IbBehaviorInstance)):
                self.error(
                    "Cannot use a behavior expression directly in a return statement. "
                    "Assign it to a typed local variable first, then return that variable.",
                    node, code="SEM_003",
                )
                return self._void_desc
            ret_type = self.visit(node.value)
            if ret_type is None:
                self.error(f"Invalid return type: got None (void or unknown)", node, code="SEM_003")
            elif self._auto_return_types is not None:
                # Inside an `-> auto` function: accumulate the return type.
                self._auto_return_types.append(ret_type)
            elif self.current_return_type and not self.registry.is_assignable(ret_type, self.current_return_type):
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got '{ret_type.name}'", node, code="SEM_003")
        else:
            if self._auto_return_types is not None:
                # bare `return` in an auto function contributes void
                self._auto_return_types.append(self._void_desc)
            elif self.current_return_type and self.current_return_type != self._void_desc:
                self.error(f"Invalid return type: expected '{self.current_return_type.name}', got 'void'", node, code="SEM_003")
        return self._void_desc

    def visit_IbAssign(self, node: ast.IbAssign):
        # 预先计算右值类型
        val_type = self.visit(node.value) if node.value else self._any_desc

        # Design 3 修复：编译期检测 void 函数返回值赋值
        # 当右值类型为 void 时（如调用无返回值函数），赋值无意义，发出编译错误
        if node.value and val_type is self._void_desc:
            # 只在右值是函数调用时报错（避免误报其他 void 表达式如语句块）
            if isinstance(node.value, ast.IbCall):
                func_name = ""
                if isinstance(node.value.func, ast.IbName):
                    func_name = node.value.func.id
                elif isinstance(node.value.func, ast.IbAttribute):
                    func_name = f"...{node.value.func.attr}"
                self.error(
                    f"Cannot assign result of void function '{func_name}()' to a variable. "
                    f"The function does not return a value.",
                    node, code="SEM_003"
                )
        
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
                # Bug 修复：行为表达式赋值给字段/下标时，val_type 是 behavior（来自
                # visit_IbBehaviorExpr 的返回值），与字段的具体类型不兼容，会产生误报
                # SEM_003。正确处理：绑定字段的期望类型给行为表达式（供 LLM executor
                # 的 _get_expected_type_hint 使用），跳过 behavior→target 的类型兼容检查。
                if isinstance(node.value, ast.IbBehaviorExpr):
                    if target_type and not self.registry.is_dynamic(target_type):
                        self.side_table.bind_type(node.value, target_type)
                    self.side_table.set_deferred(node.value, False)
                    continue
                # 检查类型兼容性
                if not self.registry.is_assignable(val_type, target_type):
                    hint = self.registry.get_diff_hint(val_type, target_type)
                    self.error(f"Cannot assign '{val_type.name}' to '{target_type.name}'", node, code="SEM_003", hint=hint)
                continue
            elif isinstance(target_node, ast.IbTuple):
                # 元组解包：(int x, int y) = (10, 20)
                # 逐个定义元组内的变量
                for elt in target_node.elts:
                    if isinstance(elt, ast.IbTypeAnnotatedExpr):
                        elt_type = self._resolve_type(elt.annotation)
                        if isinstance(elt.target, (ast.IbName, ast.IbArg)):
                            elt_name = elt.target.id if isinstance(elt.target, ast.IbName) else elt.target.arg
                            elt_sym = self._define_var(elt_name, elt_type, elt, allow_overwrite=True)
                            self.side_table.bind_symbol(elt, elt_sym)
                            self.side_table.bind_type(elt, elt_sym.spec)
                            if isinstance(elt.target, ast.IbName):
                                self.side_table.bind_symbol(elt.target, elt_sym)
                                self.side_table.bind_type(elt.target, elt_sym.spec)
                    elif isinstance(elt, ast.IbName):
                        elt_sym = self.symbol_table.resolve(elt.id)
                        if elt_sym:
                            self.side_table.bind_symbol(elt, elt_sym)
                continue
            
            if var_name:
                # §9.2: llmexcept body read-only 约束
                # 如果当前位于 llmexcept body 内，禁止对外部作用域变量的任何赋值（含重声明）。
                # 允许：在 body 内声明全新的局部变量（该名称在外部作用域不存在）。
                # 禁止：对快照进入前已存在的外部变量的一切写入（无论是否带类型标注）。
                if (self._llmexcept_outer_scope_names is not None
                        and var_name in self._llmexcept_outer_scope_names):
                    self.error(
                        f"Cannot assign to '{var_name}' inside a llmexcept handler body: "
                        f"writes to outer-scope variables break snapshot isolation. "
                        f"Use 'retry \"hint\"' to provide correction guidance instead.",
                        node, code="SEM_052"
                    )

                # global 声明：如果变量已声明为 global，将赋值绑定到全局作用域的符号，
                # 不在本地作用域中创建新符号。
                if var_name in self.symbol_table.global_refs:
                    global_scope = self.symbol_table.get_global_scope()
                    global_sym = global_scope.symbols.get(var_name)
                    if global_sym:
                        self.side_table.bind_symbol(actual_target, global_sym)
                        self.side_table.bind_type(target_node, global_sym.spec)
                        if isinstance(target_node, ast.IbTypeAnnotatedExpr) and isinstance(target_node.target, ast.IbName):
                            self.side_table.bind_symbol(target_node.target, global_sym)
                            self.side_table.bind_type(target_node.target, global_sym.spec)
                    continue

                # 决议最终目标类型 (Inference Policy)
                sym = self.symbol_table.symbols.get(var_name)
                
                if declared_type:
                    # 0. fn 声明：可调用类型推导，类似 auto 但要求 RHS 是可调用的。
                    #    fn f = myFunc  → f 持有 myFunc 的具体 callable spec (FuncSpec 等)
                    #    fn f = 42      → SEM_003 (42 不可调用)
                    if declared_type.name == "fn":
                        if isinstance(val_type, ClassSpec):
                            # ClassSpec 分两种情况：
                            # (a) 类名引用（构造器）：fn f = Dog → 始终允许
                            # (b) 类实例引用：fn f = dog_instance → 需要类定义了 __call__
                            is_constructor_ref = (
                                isinstance(node.value, ast.IbName) and
                                self.symbol_table.resolve(node.value.id) is not None and
                                self.symbol_table.resolve(node.value.id).kind == SymbolKind.CLASS
                            )
                            if is_constructor_ref:
                                # fn f = Dog — f 持有构造器引用，始终有效
                                target_type = val_type
                            elif '__call__' in val_type.members:
                                # fn f = callable_instance — 类定义了 __call__，有效
                                target_type = val_type
                            else:
                                self.error(
                                    f"'fn' requires a callable on the right-hand side. "
                                    f"Type '{val_type.name}' does not define a '__call__' method. "
                                    f"Add 'func __call__(self, ...)' to '{val_type.name}' "
                                    f"to make its instances callable via 'fn'.",
                                    node, code="SEM_003"
                                )
                                target_type = self.registry.resolve("callable") or self._any_desc
                        elif self.registry.is_callable(val_type):
                            # FuncSpec / deferred / behavior / bound_method 等
                            target_type = val_type
                        elif self.registry.is_dynamic(val_type):
                            # 右值是 any/auto：保守推导为 callable
                            target_type = self.registry.resolve("callable") or self._any_desc
                        else:
                            self.error(
                                f"'fn' requires a callable on the right-hand side, "
                                f"but got '{val_type.name}'. "
                                f"Use 'fn f = myFunction' or 'fn f = myLambda'.",
                                node, code="SEM_003"
                            )
                            target_type = self.registry.resolve("callable") or self._any_desc
                    # 1. 有显式标注：优先尊重标注，除非标注是动态的 (auto/any)
                    elif self.registry.is_dynamic(declared_type):
                        if declared_type.name == "any":
                            # `any` 是真正的动态类型：变量的 spec 永久保持为 any，
                            # 不因首次赋值的实际类型而窄化，允许后续赋值为任意类型。
                            target_type = self._any_desc
                        else:
                            # `auto`：从首次赋值的实际类型推断并锁定 spec。
                            # 特殊情况：即时行为表达式（@~...~，非延迟模式）的 LLM 输出
                            # 天然是字符串，不应推断为 behavior spec（behavior 是延迟对象的
                            # 类型标记，而非 LLM 输出类型）。
                            target_type = self._str_desc if self.registry.is_behavior(val_type) else val_type
                    else:
                        target_type = declared_type
                    
                    # [SEM_002] 检查是否在当前作用域重复声明
                    if var_name in self.symbol_table.symbols:
                        existing = self.symbol_table.symbols[var_name]
                        # 允许同一个节点在 Pass 3 更新它在 Pass 1 定义的符号类型
                        if existing.def_node is not node:
                            self.error(f"Variable '{var_name}' is already defined in this scope", node, code="SEM_002")
                    
                    # 定义或更新符号
                    sym = self._define_var(var_name, target_type, node, allow_overwrite=True)
                else:
                    # 2. 无标注：对首次定义的变量使用 any 语义（不绑定到右值类型）。
                    # 明确的类型推导（锁定到具体类型）只能通过显式类型标注或 auto 关键字实现。
                    # any 例外：sym.spec 已为 any 时保持不变，允许后续任意类型赋值。
                    spec_is_any = sym is not None and sym.spec is not None and sym.spec.name == "any"
                    if not sym:
                        # 首次定义，无类型标注 → any 语义
                        sym = self._define_var(var_name, self._any_desc, node, allow_overwrite=False)
                    elif self.registry.is_dynamic(sym.spec or self._any_desc) and not spec_is_any:
                        # 现有符号是动态类型（auto），重新推导（保留旧行为）
                        sym = self._define_var(var_name, val_type, node, allow_overwrite=True)
                
                if sym:
                    self.side_table.bind_symbol(actual_target, sym)
                    self.side_table.bind_type(target_node, sym.spec)
                    if isinstance(target_node, ast.IbTypeAnnotatedExpr) and isinstance(target_node.target, ast.IbName):
                        self.side_table.bind_symbol(target_node.target, sym)
                        self.side_table.bind_type(target_node.target, sym.spec)
                    
                    # 检查是否是行为描述表达式（裸 @~...~）
                    inner_behavior_expr = None
                    if isinstance(node.value, ast.IbBehaviorExpr):
                        inner_behavior_expr = node.value
                    elif isinstance(node.value, ast.IbCastExpr) and isinstance(node.value.value, ast.IbBehaviorExpr):
                        # (Type)@~...~ 已废弃，解析器会发出 PAR_010 错误。
                        # 防御性兜底：如果此路径被到达，也在语义层报错。
                        self.error(
                            "Cast expression '(Type) @~...~' is no longer supported. "
                            "Use 'TYPE fn varname = lambda: @~...~' or 'TYPE fn varname = snapshot: @~...~' instead.",
                            node, code="SEM_DEPRECATED"
                        )

                    if inner_behavior_expr:
                        # 即时上下文：behavior 表达式立即执行
                        self.side_table.set_deferred(inner_behavior_expr, False)
                        # 从赋值目标 sym.spec 获取类型，传递给 IbBehaviorExpr 以构建正确的提示词
                        if sym and sym.spec and not self.registry.is_dynamic(sym.spec or self._any_desc):
                            self.side_table.bind_type(inner_behavior_expr, sym.spec)
                            val_type = sym.spec
                        else:
                            val_type = self._str_desc
                    
                    if node.value is not None and not self.registry.is_assignable(val_type, sym.spec):
                        # fn / typed-fn 声明：已在相应分支报告了错误，跳过重复检查
                        from core.kernel.spec.specs import DeferredSpec as _DS
                        is_fn_decl = declared_type and (
                            declared_type.name == "fn" or isinstance(declared_type, _DS)
                        )
                        if not is_fn_decl:
                            hint = self.registry.get_diff_hint(val_type, sym.spec)
                            self.error(f"Type mismatch: Cannot assign '{val_type.name}' to '{sym.spec.name}'", node, code="SEM_003", hint=hint)
            else:
                # 处理属性或下标赋值 (e.g., p.val = 1)
                target_type = self.visit(target_node)
                if target_type and not self.registry.is_assignable(val_type, target_type):
                    hint = self.registry.get_diff_hint(val_type, target_type)
                    self.error(f"Type mismatch: Cannot assign '{val_type.name}' to target of type '{target_type.name}'", node, code="SEM_003", hint=hint)
        
        return self._void_desc

    def visit_IbIf(self, node: ast.IbIf):
        test_type = self.visit(node.test)

        if isinstance(node.test, ast.IbBehaviorExpr):
            self.side_table.bind_type(node.test, self._bool_desc)

        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

        return self._void_desc

    def visit_IbSwitch(self, node: ast.IbSwitch):
        """访问 switch-case 语句"""
        self.visit(node.test)

        for case in node.cases:
            self.visit(case)

        return self._void_desc

    def visit_IbCase(self, node: ast.IbCase):
        """访问 switch case"""
        if node.pattern:
            self.visit(node.pattern)

        for stmt in node.body:
            self.visit(stmt)

        return self._void_desc

    def visit_IbBehaviorInstance(self, node: ast.IbBehaviorInstance) -> IbSpec:
        """
        [DEPRECATED] IbBehaviorInstance 对应的 (Type) @~...~ 语法已废弃 (PAR_010)。
        该节点不再由解析器产生。此访问者仅作防御性兜底，正常情况下不会被调用。
        """
        self.error(
            "Cast expression '(Type) @~...~' is no longer supported. "
            "Use 'int lambda varname = @~...~' or 'int snapshot varname = @~...~' instead.",
            node, code="SEM_DEPRECATED"
        )
        return self._any_desc

    def visit_IbWhile(self, node: ast.IbWhile):
        test_type = self.visit(node.test)

        if isinstance(node.test, ast.IbBehaviorExpr):
            self.side_table.bind_type(node.test, self._bool_desc)

        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

        return self._void_desc

    def visit_IbFor(self, node: ast.IbFor):
        iter_type = self.visit(node.iter)
        
        if isinstance(node.iter, ast.IbBehaviorExpr):
            self.side_table.bind_type(node.iter, self._bool_desc)

        # 统一循环协议检查
        if node.target is None:
            # 情况 1: 条件驱动模式 (for @~...~: 或 for is_ready():)
            # 语义：等同于 while，要求表达式具有“布尔评估能力”
            # 贯彻“一切皆对象”协议：询问类型是否支持布尔决议
            # 即使是 behavior 类型，在 is_truthy 协议下也是合法的
            if not self.registry.is_dynamic(iter_type) and not self.registry.is_behavior(iter_type) and iter_type.get_base_name() != "bool":
                # 未来可引入 BooleanCapability 接口进行更严谨的校验（见 PENDING_TASKS.md §3.x）
                pass
        else:
            # 情况 2: 标准迭代模式 (for i in list: 或 for i in @~...~:)
            # 贯彻“一切皆对象”协议：询问类型如何提供迭代元素
            # 如果是 behavior 类型，我们认为它“潜在可迭代”
            if self.registry.is_behavior(iter_type):
                element_type = self._any_desc 
            else:
                from core.kernel.spec.specs import ClassSpec as _ClassSpec
                iter_cap = self.registry.get_iter_cap(iter_type)
                # __iter__ 协议：用户类若定义了 __iter__ 方法，视为可迭代
                has_iter_method = (
                    iter_cap is None
                    and isinstance(iter_type, _ClassSpec)
                    and self.registry.resolve_member(iter_type, "__iter__") is not None
                )
                if iter_cap:
                    # 通过 registry 统一获取 element_type，以支持引用解析
                    element_type = self.registry.resolve_iter_element(iter_type) or self._any_desc
                elif has_iter_method:
                    # __iter__ 方法返回 list，元素类型暂为 any
                    element_type = self._any_desc
                else:
                    self.error(f"Type '{iter_type.name}' is not iterable", node.iter, code="SEM_003")
                    element_type = self._any_desc
            
            # ── 双条目去重背景说明 ──
            # ``SymbolExtractor.get_assigned_names`` 对带类型标注的 target 会同时
            # 展开两条记录：``(name, IbTypeAnnotatedExpr)`` 用于读取 annotation，
            # ``(name, IbName)`` 用于绑定标识符节点。若元组目标使用类型标注
            # （如 ``for (int x, int y) in coords``），无去重会让后处理的 IbName
            # 条目用未标注的 element_type 覆盖前面写入的精确类型。
            entries = SymbolExtractor.get_assigned_names(node)
            typed_names = {n for n, t in entries if isinstance(t, ast.IbTypeAnnotatedExpr)}
            # 元组解包目标时每个 element 各有自己的（可选）注解，整体 element_type
            # 不应被作为各分量的兜底类型——元组分量类型由 element_type 的成员推导
            # 决定，这里没有可靠的成员类型时，宁可保持 any 也不要把整体 tuple 类型
            # 作为分量类型。
            is_tuple_target = isinstance(node.target, ast.IbTuple)

            for var_name, target in entries:
                is_typed_target = isinstance(target, ast.IbTypeAnnotatedExpr)
                # 双条目去重：同名 IbName 条目仅做 side_table 绑定，跳过类型重定义。
                if (not is_typed_target) and var_name in typed_names:
                    sym = self.symbol_table.symbols.get(var_name)
                    if sym:
                        self.side_table.bind_symbol(target, sym)
                    continue

                # 优先使用显式类型标注，而非推导出的 element_type
                if is_typed_target:
                    effective_type = self.visit(target.annotation)
                elif is_tuple_target:
                    # 元组解包但未给该元素加注解：保持 any，不要使用整体 element_type
                    effective_type = self._any_desc
                else:
                    effective_type = element_type

                # 检查是否已在 Pass 2.5 预扫描中定义
                sym = self.symbol_table.symbols.get(var_name)

                # [STABILIZATION] 只有当新类型比现有类型更精确时才更新
                if not sym or self.registry.is_dynamic(sym.spec or self._any_desc):
                    sym = self._define_var(var_name, effective_type, target, allow_overwrite=(sym is not None))
                elif not self.registry.is_dynamic(effective_type):
                    # 如果新类型不是 Any，则强制更新（覆盖之前的推导）
                    sym.spec = effective_type

                if sym:
                    self.side_table.bind_symbol(target, sym)

        for stmt in node.body:
            self.visit(stmt)

        # C11/P1: 条件驱动 for 情形——IbLLMExceptionalStmt 不在 body 中，
        # 但其 handler body 的符号绑定必须在此显式触发。
        # 通过 node.llmexcept_handler 直接引用（C11/P3 已删除 node_protection 侧表）。
        if node.target is None and node.llmexcept_handler is not None:
            self.visit(node.llmexcept_handler)

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
            if not sym or self.registry.is_dynamic(sym.spec or self._any_desc):
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

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """处理带类型标注的表达式包装节点 (例如 Casts 或声明)"""
        # 1. 解析标注的类型
        annotated_type = self._resolve_type(node.annotation)
        
        # 2. 访问内部表达式并检查类型一致性
        inner_type = self.visit(node.target)
        
        # 如果是显式标注，我们认为结果类型就是标注的类型（类似于 Cast）
        # 但我们需要校验内部表达式是否能被视为该类型
        if not self.registry.is_assignable(inner_type, annotated_type):
            self.error(f"Type mismatch: Expression of type '{inner_type.name}' cannot be cast/assigned to '{annotated_type.name}'", node, code="SEM_003")
            
        return annotated_type

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """处理带过滤条件的表达式包装节点 (e.g., expr if filter)"""
        # 1. 访问被包装的表达式 (例如 While 的 test 或 For 的 iter)
        inner_type = self.visit(node.expr)

        # 2. 访问过滤条件，它必须返回布尔值 (或可视为布尔值)
        filter_type = self.visit(node.filter)

        # BugFix: 若过滤条件是行为表达式（AI filter），必须将其绑定为 bool 类型上下文，
        # 与 visit_IbIf / visit_IbWhile / visit_IbFor 对 test/iter 的处理保持对称。
        # 注意：`bind_type` 必须放在 `self.visit()` **之后**——`visit()` 末尾会用
        # `_behavior_desc` 覆写 `node_to_type[node.filter]`，先绑后访会被覆盖，
        # 导致 execute_behavior_expression 拿不到 type_hint，
        # 进而将 LLM 原始响应（如 "0"）包装为 IbString 而非 IbBool，
        # 使得 is_truthy 判定始终为 True，过滤条件完全失效。
        if isinstance(node.filter, ast.IbBehaviorExpr):
            self.side_table.bind_type(node.filter, self._bool_desc)

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

    def visit_IbCompare(self, node: ast.IbCompare) -> IbSpec:
        left_type = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right_type = self.visit(comparator)
            # 成员检测运算符：要求右侧为可迭代容器类型（str/list/dict/any）
            if op in ("in", "not in"):
                # Use get_base_name() so generic containers (list[int], dict[str,int]) are
                # correctly classified — specialised specs have name="list[int]" but
                # get_base_name()="list".  Dynamic types (any/auto) are always allowed.
                if right_type and not self.registry.is_dynamic(right_type):
                    right_base = right_type.get_base_name()
                    if right_base not in ("str", "list", "dict", "tuple"):
                        self.error(
                            f"Operator '{op}' requires an iterable container on the right-hand side, "
                            f"but got '{right_type.name}'",
                            node, code="SEM_003",
                        )
            elif op in ("is", "is not"):
                # 身份检测运算符：始终有效，返回 bool。
                # 不调度到公理方法，身份比较是语言内核语义。
                pass
            else:
                res = self.registry.resolve_op(left_type, op, right_type)
                if not res:
                    self.error(f"Comparison operator '{op}' not supported for types '{left_type.name}' and '{right_type.name}'", node, code="SEM_003")
            # 链式比较中，前一轮的右操作数成为下一轮的左操作数
            left_type = right_type
        
        return self._bool_desc

    def visit_IbBoolOp(self, node: ast.IbBoolOp) -> IbSpec:
        for val in node.values:
            self.visit(val)
        return self._bool_desc

    def visit_IbIfExp(self, node: ast.IbIfExp) -> IbSpec:
        """三元条件表达式：condition ? body : orelse"""
        self.visit(node.test)
        body_type = self.visit(node.body)
        orelse_type = self.visit(node.orelse)
        # 返回类型：若两侧类型相同则返回该类型，否则返回 any
        if body_type and orelse_type and body_type.name == orelse_type.name:
            return body_type
        return self._any_desc

    def visit_IbTuple(self, node: ast.IbTuple) -> IbSpec:
        """元组表达式 -> 不可变元组类型"""
        element_type = self._any_desc
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        desc = self.registry.factory.create_tuple(element_type.name if element_type else "any")
        self.registry.register(desc)
        return desc

    def visit_IbListExpr(self, node: ast.IbListExpr) -> IbSpec:
        element_type = self._any_desc
        if node.elts:
            element_type = self.visit(node.elts[0])
            for elt in node.elts[1:]:
                self.visit(elt)
        
        # [Axiom-Driven] 使用 Factory 创建 ListSpec
        # 严格模式：直接使用 Registry 工厂，并进行即时注册以注入公理
        desc = self.registry.factory.create_list(element_type.name if element_type else "any")
        self.registry.register(desc)
        return desc

    def visit_IbDict(self, node: ast.IbDict) -> IbSpec:
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
                
        # [Axiom-Driven] 使用 Factory 创建 DictSpec
        # 严格模式：直接使用 Registry 工厂并注册
        desc = self.registry.factory.create_dict(key_type.name if key_type else "any", val_type.name if val_type else "any")
        self.registry.register(desc)
        return desc

    def visit_IbSubscript(self, node: ast.IbSubscript) -> IbSpec:
        value_type = self.visit(node.value)
        key_type = self.visit(node.slice)

        # 贯彻"一切皆对象"协议：询问类型如何处理下标
        subscript_cap = self.registry.get_subscript_cap(value_type)
        if not subscript_cap:
            self.error(f"Type '{value_type.name}' is not subscriptable", node, code="SEM_003")
            return self._any_desc

        res = self.registry.resolve_subscript(value_type, key_type)
        if not res:
            # 特殊处理：如果是 list 且 key 是 int，返回其 element_type
            if value_type.get_base_name() == "list" and key_type.get_base_name() == "int":
                return self.registry.resolve_iter_element(value_type) or self._any_desc
            # 如果是 list/str 且 key 是 slice，返回自身类型
            if value_type.get_base_name() in ("list", "str") and key_type.get_base_name() == "slice":
                return value_type

        return res or self._any_desc

    def visit_IbSlice(self, node: ast.IbSlice) -> IbSpec:
        """分析切片表达式"""
        if node.lower: self.visit(node.lower)
        if node.upper: self.visit(node.upper)
        if node.step: self.visit(node.step)
        
        # 暂时返回预定义的 slice 描述符
        return self.registry.resolve("slice") or self._any_desc

    def visit_IbCastExpr(self, node: ast.IbCastExpr) -> IbSpec:
        """类型强转语义分析"""
        self.visit(node.value)
        # 支持复杂类型标注 (如 list[int])，消除硬编码名称查找
        target_type = self._resolve_type(node.type_annotation)
        if target_type:
            self.side_table.bind_type(node, target_type)
            return target_type
        return self._any_desc
        
    def _resolve_type_by_name(self, name: str) -> Optional[IbSpec]:
        # Helper for CastExpr which uses string name
        sym = self.symbol_table.resolve(name)
        if sym and sym.is_type:
            return sym.spec
        # Try builtins
        return self.prelude.get_builtin_types().get(name)

    def visit_IbBinOp(self, node: ast.IbBinOp) -> IbSpec:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        
        # 贯彻“一切皆对象”：调用左操作数的自决议方法
        res = self.registry.resolve_op(left_type, node.op, right_type)
        if not res:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type.name}' and '{right_type.name}'", node, code="SEM_003")
            return self._any_desc
        return res

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp) -> IbSpec:
        operand_type = self.visit(node.operand)
        
        # 贯彻“一切皆对象”：调用操作数的自决议方法 (other=None 表示一元运算)
        res = self.registry.resolve_op(operand_type, node.op, None)
        if not res:
            self.error(f"Unary operator '{node.op}' not supported for type '{operand_type.name}'", node, code="SEM_003")
            return self._any_desc
        return res

    def visit_IbConstant(self, node: ast.IbConstant) -> IbSpec:
        val = node.value
        # 委托给注册表根据原生值解析描述符，消除分析器对 Python 类型的硬编码依赖
        desc = self.registry.resolve_from_value(val)
        if desc:
            return desc
        return self.registry.resolve("any")

    def visit_IbName(self, node: ast.IbName) -> IbSpec:
        # 1. 解析符号
        sym = self.symbol_table.resolve(node.id)

        # Bug #4 修复：'none'（全小写）在 Prelude 中被注册为 void 的别名，
        # 编译期可解析，但运行时 'builtin:none' 变量不存在，导致崩溃。
        # 在此处拦截并给出明确的编译错误提示，引导用户使用 'None'（首字母大写）。
        if node.id == "none" and sym and getattr(sym, 'uid', None) == "builtin:none":
            self.error(
                "未定义的标识符 'none'。请使用 'None'（首字母大写）。",
                node, code="SEM_001"
            )
            return self._void_desc
        
        if not sym:
            msg = f"Variable '{node.id}' is not defined"
            if self.in_behavior_expr:
                msg = f"Variable '{node.id}' used in behavior expression is not defined"
            self.error(msg, node, code="SEM_001")
            return self._any_desc

        self.side_table.bind_symbol(node, sym)
        
        # 统一获取类型信息
        res = sym.spec
            
        return res

    def visit_IbAttribute(self, node: ast.IbAttribute) -> IbSpec:
        base_type = self.visit(node.value)

        # 处理属性/方法访问：通过 SpecRegistry 委托，不直接调用 spec 方法
        member_type = self.registry.resolve_member(base_type, node.attr) if base_type else None

        if member_type:
            return member_type

        # [Dynamic Resolution] 如果是动态类型（any/auto），允许访问任意属性并返回 any
        if self.registry.is_dynamic(base_type):
            return self._any_desc

        self.error(f"Type '{base_type.name}' has no member '{node.attr}'", node, code="SEM_001")
        return self._any_desc

    def visit_IbCall(self, node: ast.IbCall) -> IbSpec:
        func_type = self.visit(node.func)
        arg_types = [self.visit(arg) for arg in node.args]
        
        # 0. 特殊处理内置类型的构造函数调用
        # 当 IbSpec 没有 get_call_trait() 但类型名是内置类型时，
        # 允许构造函数调用并返回对应类型
        if func_type and not self.registry.get_call_cap(func_type):
            type_name = func_type.name
            if type_name in ('str', 'int', 'float', 'bool', 'list', 'dict', 'Exception'):
                return func_type
        
        # 0b. 变量持有可调用类实例的特殊处理：
        # 当 fn f = instance_with_call 时，f 的类型是 ClassSpec（如 Adder）。
        # 调用 f(args) 时应通过 __call__ 方法推断返回类型，而非构造器语义（返回 ClassSpec 自身）。
        # 仅在 node.func 是变量引用（非类名引用）且该变量类型是带 __call__ 的 ClassSpec 时生效。
        if isinstance(func_type, ClassSpec) and isinstance(node.func, ast.IbName):
            sym = self.symbol_table.resolve(node.func.id)
            if sym and not sym.is_type and '__call__' in func_type.members:
                from core.kernel.spec import FuncSpec as _FuncSpec
                call_spec = self.registry.resolve_member(func_type, '__call__')
                if call_spec and isinstance(call_spec, _FuncSpec):
                    return self.registry.resolve(call_spec.return_type_name) or self._any_desc
        
        # 1. 检查是否可调用 (使用 Trait 契约)
        call_trait = self.registry.get_call_cap(func_type)
        if not call_trait:
            self.error(f"Type '{func_type.name}' is not callable", node, code="SEM_003")
            return self._any_desc
            
        # 2. 贯彻"一切皆对象"：询问类型对象调用后的返回结果
        res = self.registry.resolve_return(func_type, arg_types)
        
        if not res:
            # 通过 Trait 提取签名信息进行诊断
            if call_trait and hasattr(call_trait, 'param_types'):
                param_types = call_trait.param_types
                if len(arg_types) != len(param_types):
                    self.error(f"Function expected {len(param_types)} arguments, but got {len(arg_types)}", node, code="SEM_005")
                else:
                    for i, (expected, actual) in enumerate(zip(param_types, arg_types)):
                        if not self.registry.is_assignable(actual, expected):
                            hint = self.registry.get_diff_hint(actual, expected)
                            self.error(f"Argument {i+1} type mismatch: expected '{expected.name}', but got '{actual.name}'", node, code="SEM_003", hint=hint)
            else:
                self.error(f"Invalid call to '{func_type.name}'", node, code="SEM_003")
            return self._any_desc
            
        return res

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr) -> IbSpec:
        self.in_behavior_expr = True

        try:
            for seg in node.segments:
                if isinstance(seg, ast.IbASTNode):
                    self.visit(seg)
        finally:
            self.in_behavior_expr = False
        return self._behavior_desc

    def visit_IbLambdaExpr(self, node: ast.IbLambdaExpr) -> IbSpec:
        """
        参数化 lambda/snapshot 表达式（M1；D1/D2 返回类型迁移至表达式侧）的语义分析。

        策略
        ----
        1. 确定 returns_type：来自 ``node.returns``（由解析器在表达式侧 ``-> TYPE``
           处填充，例如 ``fn f = lambda -> int: EXPR``）。D1/D2 落地前使用的
           ``_pending_fn_return_type`` 隐式通道已删除（2026-04-29）。
        2. 为参数列表与函数体打开新的 ``SymbolTable``（局部作用域），保证 body 内
           的 ``IbName`` 决议能将形参指向局部符号而非误捕外层同名变量。
        4. 形参解析为 ``VariableSymbol``，类型来自注解（缺省为 ``any``）。
        5. visit body：触发完整的 Pass 3 类型检查与 ``node_to_symbol`` 绑定。
        6. 若 body 是 ``IbBehaviorExpr`` 且 returns_type 携带具体类型，则将该类型
           绑定到 body 节点的 ``node_to_type`` 侧表——这是 LLM executor 读取
           ``expected_type``（用于 ``__outputhint_prompt__`` 注入和 ``_parse_result``
           返回值解析）的关键入口。
        7. 若 body 是非行为表达式且 returns_type 存在，检查 body 类型与 returns_type
           类型的兼容性（编译期类型校验）。
        8. lambda 表达式自身的 spec：若 returns_type 携带具体类型则返回带 value_type
           的 BehaviorSpec/DeferredSpec（使 ``fn f = lambda -> int: EXPR`` 时
           ``int r = f()`` 能在编译期通过类型决议），否则返回通用 spec。
        """
        # 1. 确定返回类型：来自表达式侧 ``-> TYPE`` 标注（node.returns）。
        #    ``_pending_fn_return_type`` 隐式通道已删除（D1/D2，2026-04-29）。
        returns_type: Optional[IbSpec] = (
            self._resolve_type(node.returns, safe=True) if node.returns is not None else None
        )

        # 3. 为 lambda 局部作用域打开新的符号表
        old_table = self.symbol_table
        local_scope = SymbolTable(parent=old_table, name=f"<lambda:{node.deferred_mode}>")
        self.symbol_table = local_scope

        # 临时清除 current_class，避免把 lambda 形参登记为类成员
        saved_class = self.current_class
        self.current_class = None
        param_sym_uids: set = set()
        try:
            # 4. 注册形参符号，同时收集形参的 sym_uid（供自由变量分析剔除）
            for arg_node in node.params:
                arg_type = self._any_desc
                name_node = arg_node
                if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                    arg_type = self._resolve_type(arg_node.annotation)
                    name_node = arg_node.target

                if isinstance(name_node, ast.IbArg):
                    sym = self._define_var(name_node.arg, arg_type, name_node)
                    if sym is not None and sym.uid:
                        param_sym_uids.add(sym.uid)
                elif isinstance(name_node, ast.IbName):
                    sym = self._define_var(name_node.id, arg_type, name_node)
                    if sym is not None and sym.uid:
                        param_sym_uids.add(sym.uid)

            # 5. 走访 body，触发完整类型决议
            if node.body is not None:
                body_type = self.visit(node.body)
            else:
                body_type = self._void_desc
        finally:
            self.current_class = saved_class
            self.symbol_table = old_table

        # C8/C14：编译期自由变量分析。
        # 在 symbol_table 已恢复为外层作用域后执行，确保 side_table 中所有
        # body 内 IbName 的 sym_uid 均已由 Pass 4 绑定完毕。
        # 结果写入 node.free_vars（序列化到 artifact），并将 lambda 模式捕获的
        # sym_uid 加入 side_table.cell_captured_symbols（供 Pass 5 BDA 使用）。
        free_var_refs = self._collect_free_var_refs_ast(node.body, param_sym_uids)
        node.free_vars = [[name, sym_uid] for name, sym_uid in free_var_refs]
        if node.deferred_mode == "lambda":
            # lambda 模式：自由变量通过共享 IbCell 捕获（SC-4）。
            # 将这些 sym_uid 注册为 cell_captured_symbols，让 Pass 5 把对应
            # 赋值语句中的 behavior 表达式标记为 dispatch_eligible=False。
            for _name, sym_uid in free_var_refs:
                self.side_table.cell_captured_symbols.add(sym_uid)

        # 6. 若 body 是 IbBehaviorExpr 且 returns_type 携带具体类型，
        #    将该类型绑定到 body 节点的 node_to_type 侧表，使 LLM executor
        #    在执行时能正确注入提示词格式要求并解析返回值。
        is_behavior_body = isinstance(node.body, ast.IbBehaviorExpr)
        has_concrete_returns = (
            returns_type is not None
            and not self.registry.is_dynamic(returns_type)
        )

        if is_behavior_body and has_concrete_returns:
            self.side_table.bind_type(node.body, returns_type)

        # 7. 非行为 body：检查 body 类型与 returns_type 的兼容性
        if (not is_behavior_body
                and has_concrete_returns
                and body_type is not None
                and body_type is not self._void_desc
                and not self.registry.is_assignable(body_type, returns_type)
                and not self.registry.is_dynamic(body_type)):
            self.error(
                f"Lambda body type '{body_type.name}' is not compatible with "
                f"declared return type '{returns_type.name}'.",
                node, code="SEM_003",
            )

        # 8. 返回带 value_type 的 Spec（使调用处 resolve_return 能推导出具体类型）
        if is_behavior_body:
            if has_concrete_returns:
                return self.registry.factory.create_behavior(
                    value_type_name=returns_type.name,
                    value_type_module=getattr(returns_type, 'module_path', None),
                    deferred_mode=node.deferred_mode,
                )
            return self._behavior_desc
        else:
            if has_concrete_returns:
                return self.registry.factory.create_deferred(
                    value_type_name=returns_type.name,
                    value_type_module=getattr(returns_type, 'module_path', None),
                    deferred_mode=node.deferred_mode,
                )
            return self._deferred_desc

    def _collect_free_var_refs_ast(
        self, body_node: Optional['ast.IbASTNode'], param_sym_uids: set
    ) -> List:
        """编译期自由变量收集（对 AST 对象树）。

        与 ``ExprHandler._collect_free_refs`` 逻辑对应，但在 Pass 4 完成后于
        AST 对象（Python dataclass 实例）上操作，而非在运行时遍历 artifact dict。

        返回 ``[(name, sym_uid), ...]``，每项表示一个自由变量引用，按首次出现
        去重；调用方按 sym_uid 再次去重（与运行时版本行为一致）。

        **嵌套 lambda 处理**：遇到 ``IbLambdaExpr`` 时，将内层形参 UID 加入
        exclusion set 并递归进入其 body——与运行时版本完全对应：外层 lambda
        需捕获内层 body 引用到的外层变量，以便在定义内层 lambda 时正确 promote_to_cell。

        **全局变量**：分析结果保守，包含全局作用域变量。运行时 ``promote_to_cell``
        对全局变量返回 ``None``（不提升），closure 中不会出现全局变量的 cell。
        """
        if body_node is None:
            return []

        refs: List = []
        seen_sym_uids: set = set()

        def walk(node: Any, excl: set) -> None:
            if not isinstance(node, ast.IbASTNode):
                return
            if isinstance(node, ast.IbName):
                # 只处理 Load 上下文（读取，非赋值目标）
                if getattr(node, "ctx", "Load") in ("Load", ""):
                    sym = self.side_table.node_to_symbol.get(node)
                    if sym is not None and sym.uid and sym.uid not in excl:
                        if sym.uid not in seen_sym_uids:
                            seen_sym_uids.add(sym.uid)
                            refs.append((node.id, sym.uid))
                return
            if isinstance(node, ast.IbLambdaExpr):
                # 嵌套 lambda：将内层形参加入 excl 后递归进入 body
                inner_excl = set(excl)
                for arg_node in (node.params or []):
                    actual = arg_node
                    if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                        actual = arg_node.target
                    sym = self.side_table.node_to_symbol.get(actual)
                    if sym is not None and sym.uid:
                        inner_excl.add(sym.uid)
                if node.body is not None:
                    walk(node.body, inner_excl)
                return
            # 通用展开：递归所有 AST 子节点（列表字段 + 单值字段）
            for field_name, value in vars(node).items():
                if field_name in ("llm_deps", "free_vars"):
                    continue  # 跳过 DDG 元数据和已计算的自由变量列表
                if isinstance(value, ast.IbASTNode):
                    walk(value, excl)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.IbASTNode):
                            walk(item, excl)

        walk(body_node, param_sym_uids)
        return refs

    def _resolve_type(self, node: Optional[ast.IbASTNode], safe: bool = False) -> IbSpec:
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
                    return sym.spec
                return sym.spec
                
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
                
            # 使用 registry.resolve_specialization 实现真正的类型演算（IbSpec 本身无此方法）
            result = self.registry.resolve_specialization(base_type, generic_args)
            return result if result is not None else base_type

        elif isinstance(node, ast.IbAttribute):
            if safe:
                if isinstance(node.value, ast.IbName):
                    base_sym = self.symbol_table.resolve(node.value.id)
                    if base_sym and base_sym.spec:
                        member_type = self.registry.resolve_member(base_sym.spec, node.attr)
                        if member_type:
                            return member_type
                return self._any_desc
                
            base_type = self.visit(node.value)
            member_type = self.registry.resolve_member(base_type, node.attr) if base_type else None
            if member_type:
                return member_type
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

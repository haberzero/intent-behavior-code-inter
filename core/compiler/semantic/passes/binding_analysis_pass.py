"""
Binding Analysis Pass (BindingPhase sub-step 1)

职责：LLMExcept 绑定、Intent 上下文验证、Lambda 捕获分析
输入：Context with type_bindings (via prior_symbol_bindings)
输出：PassOutput with cell_captured_symbols
"""

from typing import Optional, List, Dict, Any, Set

from core.base.diagnostics.codes import (
    SEM_LLMEXCEPT_BINDING,
    SEM_LLMEXCEPT_BODY_WRITE,
    SEM_LLMEXCEPT_SCOPE_BINDING,
    SEM_UNCATEGORIZED,
)
from core.kernel import ast
from core.kernel.symbols import SymbolTable, VariableSymbol, SymbolKind
from core.kernel.spec.registry import SpecRegistry

from ..result import PassResult, PassOutput, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass
from .scoped_visitor import ScopedVisitor


class BindingAnalysisPass(BasePass):
    """绑定分析 Pass（BindingPhase sub-step 1）

    包含三个子分析器：
    1. LLMExceptBindingAnalyzer - llmexcept 绑定分析
    2. IntentContextValidator - intent 上下文验证
    3. LambdaCaptureAnalyzer - Lambda/Snapshot 捕获分析
    """

    def __init__(self):
        super().__init__("BindingAnalysisPass")

    def run(self, context: SemanticContext) -> PassResult:
        all_diagnostics = []

        # 1. LLMExcept 绑定分析
        llmexcept_analyzer = LLMExceptBindingAnalyzer(context)
        llmexcept_analyzer.analyze()
        all_diagnostics.extend(llmexcept_analyzer.diagnostics)

        # 2. Intent 上下文验证
        intent_validator = IntentContextValidator(context)
        intent_validator.validate()
        all_diagnostics.extend(intent_validator.diagnostics)

        # 3. Lambda 捕获分析
        lambda_analyzer = LambdaCaptureAnalyzer(context)
        lambda_analyzer.analyze()
        all_diagnostics.extend(lambda_analyzer.diagnostics)

        # Collect cell_captured_symbols from lambda captures
        cell_captures = set()
        for node, captures in lambda_analyzer.lambda_captures.items():
            for var_name in captures:
                sym = context.symbol_table.resolve(var_name)
                if sym and hasattr(sym, 'uid') and sym.uid:
                    cell_captures.add(sym.uid)
                else:
                    cell_captures.add(var_name)

        output = PassOutput(
            cell_captured_symbols=cell_captures,
            diagnostics=all_diagnostics,
            success=True,
        )
        return PassResult.ok(context, output=output)


class LLMExceptBindingAnalyzer(ScopedVisitor):
    """LLMExcept 绑定分析器

    验证 llmexcept 语句的合法性：
    - llmexcept 必须关联到包含行为表达式的语句
    - 检查 llmexcept target 的合法性
    - read-only 约束：llmexcept body 内禁止对外部作用域变量赋值（SEM_LLMEXCEPT_BODY_WRITE）
    """

    def __init__(self, context: SemanticContext):
        super().__init__(context)
        self.llmexcept_bindings: Dict[str, Any] = {}
        # 当前 llmexcept body 外部作用域变量名集合（非 None 时表示正在分析 body 内部）
        self._llmexcept_outer_scope_names: Optional[frozenset] = None

    def analyze(self):
        """分析 llmexcept 绑定 — 显式做 body 重写（pop + replace）

        两条通道并存：
        - 正则情形：stmt.target = prev_stmt（llmexcept 替换 prev_stmt 成为 body 中唯一条目）
        - 条件 for 循环：prev_stmt.llmexcept_handler = stmt（stmt.target 保持 None）
        """
        self._analyze_node(self.context.ast)

    def _analyze_node(self, node: ast.IbASTNode):
        """递归分析节点"""
        if isinstance(node, ast.IbModule):
            node.body = self._rewrite_body(node.body)
        elif isinstance(node, ast.IbFunctionDef):
            func_sym = self.current_scope.resolve(node.name)
            func_scope = getattr(func_sym, 'owned_scope', None) if func_sym else None
            if func_scope is None:
                func_scope = SymbolTable(parent=self.current_scope, name=node.name)
                LambdaCaptureAnalyzer._register_func_params(node.args, func_scope)
            with self.enter_scope(func_scope):
                node.body = self._rewrite_body(node.body)
        elif isinstance(node, ast.IbLLMFunctionDef):
            # LLM 函数内部不需要 llmexcept（整个函数就是行为）
            pass
        elif isinstance(node, ast.IbClassDef):
            for stmt in node.body:
                self._analyze_node(stmt)
        elif isinstance(node, (ast.IbFor, ast.IbWhile, ast.IbIf)):
            # 递归进入控制流容器
            if hasattr(node, 'body') and node.body:
                node.body = self._rewrite_body(node.body)
            if hasattr(node, 'orelse') and node.orelse:
                node.orelse = self._rewrite_body(node.orelse)
        elif isinstance(node, ast.IbTry):
            node.body = self._rewrite_body(node.body)
            for handler in node.handlers:
                if hasattr(handler, 'body') and handler.body:
                    handler.body = self._rewrite_body(handler.body)
            if node.orelse:
                node.orelse = self._rewrite_body(node.orelse)
            if node.finalbody:
                node.finalbody = self._rewrite_body(node.finalbody)
        elif isinstance(node, ast.IbSwitch):
            for case in node.cases:
                if case.body:
                    case.body = self._rewrite_body(case.body)
        elif isinstance(node, ast.IbLLMExceptionalStmt):
            # 递归处理 llmexcept body
            if node.body:
                node.body = self._rewrite_body(node.body)

    def _rewrite_body(self, body: List[ast.IbASTNode]) -> List[ast.IbASTNode]:
        """重写语句块 — 执行 llmexcept body 重写逻辑"""
        if not body:
            return body

        new_body = []
        i = 0
        while i < len(body):
            stmt = body[i]

            if isinstance(stmt, ast.IbLLMExceptionalStmt):
                if not new_body:
                    self.error(
                        "llmexcept must follow a statement, but no previous statement found.",
                        stmt, code=SEM_LLMEXCEPT_SCOPE_BINDING
                    )
                    i += 1
                    continue

                prev_stmt = new_body[-1]

                # 条件驱动 for 循环的特殊处理
                if isinstance(prev_stmt, ast.IbFor) and prev_stmt.target is None:
                    cond_expr = prev_stmt.iter
                    if not self._contains_behavior_expr(cond_expr):
                        self.error(
                            "llmexcept following a condition-driven 'for' loop requires a behavior expression "
                            "'@~...~' as the loop condition.",
                            stmt, code=SEM_LLMEXCEPT_BINDING
                        )
                    # 条件 for 循环：挂载到 IbFor.llmexcept_handler
                    stmt.target = None
                    prev_stmt.llmexcept_handler = stmt
                    # 递归处理 llmexcept body
                    if stmt.body:
                        stmt.body = self._rewrite_body(stmt.body)
                        # 验证 body 内的 read-only 约束
                        self._validate_readonly_body(stmt.body)
                    i += 1
                    continue
                else:
                    # 正则情形：检查前一个语句是否包含行为描述
                    if not self._contains_behavior_expr(prev_stmt):
                        self.error(
                            f"llmexcept must follow a statement containing a behavior expression '@~...~'. "
                            f"Found: '{prev_stmt.__class__.__name__}' without IbBehaviorExpr.",
                            stmt, code=SEM_LLMEXCEPT_BINDING
                        )
                    # 正则情形：stmt.target = prev_stmt; pop prev_stmt from body
                    stmt.target = prev_stmt
                    new_body.pop()
                    new_body.append(stmt)

                # 递归处理 llmexcept body
                if stmt.body:
                    stmt.body = self._rewrite_body(stmt.body)
                    # 验证 body 内的 read-only 约束
                    self._validate_readonly_body(stmt.body)

                # 记录绑定（使用节点对象作为键）
                self.llmexcept_bindings[stmt] = {
                    'target': stmt.target,
                    'has_behavior': True
                }
            else:
                new_body.append(stmt)
                # 递归处理子节点
                self._analyze_node(stmt)

            i += 1

        return new_body

    def _contains_behavior_expr(self, node: ast.IbASTNode) -> bool:
        """检查节点是否包含行为表达式"""
        if isinstance(node, ast.IbBehaviorExpr):
            return True

        # 递归检查子节点
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        if self._contains_behavior_expr(item):
                            return True
            elif isinstance(child, ast.IbASTNode):
                if self._contains_behavior_expr(child):
                    return True

        return False

    # ===== llmexcept body read-only 约束 =====

    def _validate_readonly_body(self, body: List[ast.IbASTNode]):
        """验证 llmexcept body 内的 read-only 约束（SEM_LLMEXCEPT_BODY_WRITE）。

        - 捕获进入 body 前的外部作用域变量名集合
        - 排除 body 内声明的 body-local 变量（避免误报）
        - body 内任何对外部作用域变量的赋值产生 SEM_LLMEXCEPT_BODY_WRITE 错误
        """
        # 收集所有可见作用域的变量名（当前作用域 + 全部外层父作用域）
        all_scope_names = set()
        scope = self.current_scope
        while scope is not None:
            all_scope_names.update(scope.symbols.keys())
            scope = scope.parent
        all_scope_names = frozenset(all_scope_names)

        # 收集 body 直接层级声明的变量名（body-local）
        body_declared_names = self._collect_body_declared_names(body)

        # 外部作用域变量 = 进入 body 前的所有变量 - body 内新声明的变量
        outer_scope_names = all_scope_names - body_declared_names

        # 检查 body 内的赋值
        self._check_assignments_readonly(body, outer_scope_names)

    def _collect_body_declared_names(self, body: List[ast.IbASTNode]) -> frozenset:
        """收集 llmexcept body 直接层级中真正新声明的变量名。

        仅当赋值有类型标注（IbTypeAnnotatedExpr）时，视为新的 body-local 声明。
        """
        result: set = set()
        for stmt in body:
            if isinstance(stmt, ast.IbAssign):
                for target in stmt.targets:
                    if (isinstance(target, ast.IbTypeAnnotatedExpr)
                            and isinstance(target.target, ast.IbName)):
                        name = target.target.id
                        # 检查该变量是否在外部作用域已定义
                        current_scope = self.current_scope
                        if current_scope:
                            existing = current_scope.symbols.get(name)
                            # 仅当 existing 的 def_node 指向本 stmt 时，才是 body-local 新声明
                            if existing is not None and existing.def_node is stmt:
                                result.add(name)
                            elif existing is None:
                                # 外部未定义 → body-local 新变量
                                result.add(name)
        return frozenset(result)

    def _check_assignments_readonly(self, body: List[ast.IbASTNode], outer_scope_names: frozenset):
        """递归检查 body 内的赋值是否违反 read-only 约束。"""
        for stmt in body:
            if isinstance(stmt, ast.IbAssign):
                for target in stmt.targets:
                    var_name = self._extract_assign_target_name(target)
                    if var_name and var_name in outer_scope_names:
                        self.error(
                            f"Cannot assign to '{var_name}' inside a llmexcept handler body: "
                            f"writes to outer-scope variables break snapshot isolation. "
                            f"Use 'retry \"hint\"' to provide correction guidance instead.",
                            stmt, code=SEM_LLMEXCEPT_BODY_WRITE
                        )
            elif isinstance(stmt, ast.IbAugAssign):
                var_name = self._extract_assign_target_name(stmt.target)
                if var_name and var_name in outer_scope_names:
                    self.error(
                        f"Cannot assign to '{var_name}' inside a llmexcept handler body: "
                        f"writes to outer-scope variables break snapshot isolation. "
                        f"Use 'retry \"hint\"' to provide correction guidance instead.",
                        stmt, code=SEM_LLMEXCEPT_BODY_WRITE
                    )

            # 递归检查嵌套结构
            if hasattr(stmt, 'body') and isinstance(getattr(stmt, 'body'), list):
                self._check_assignments_readonly(stmt.body, outer_scope_names)
            if hasattr(stmt, 'orelse') and isinstance(getattr(stmt, 'orelse'), list):
                self._check_assignments_readonly(stmt.orelse, outer_scope_names)
            if hasattr(stmt, 'handlers') and isinstance(getattr(stmt, 'handlers'), list):
                for handler in stmt.handlers:
                    if hasattr(handler, 'body') and isinstance(handler.body, list):
                        self._check_assignments_readonly(handler.body, outer_scope_names)
            if hasattr(stmt, 'finalbody') and isinstance(getattr(stmt, 'finalbody'), list):
                self._check_assignments_readonly(stmt.finalbody, outer_scope_names)

    def _extract_assign_target_name(self, target: ast.IbASTNode) -> Optional[str]:
        """从赋值目标提取变量名。"""
        if isinstance(target, ast.IbName):
            return target.id
        elif isinstance(target, ast.IbTypeAnnotatedExpr):
            if isinstance(target.target, ast.IbName):
                return target.target.id
        return None


class IntentContextValidator:
    """Intent 上下文验证器

    验证 intent 注解的合法性：
    - @ 或 @! 注解必须紧跟行为表达式
    - @+ 和 @- 可以独立存在
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []
        self.intent_annotations: Dict[Any, Any] = {}

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
        """记录错误诊断"""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def validate(self):
        """验证 intent 上下文"""
        self._validate_node(self.context.ast)

    def _validate_node(self, node: ast.IbASTNode):
        """递归验证节点"""
        if isinstance(node, ast.IbModule):
            self._validate_body(node.body)
        elif isinstance(node, ast.IbFunctionDef):
            self._validate_body(node.body)
        elif isinstance(node, ast.IbLLMFunctionDef):
            pass
        elif isinstance(node, ast.IbClassDef):
            for stmt in node.body:
                self._validate_node(stmt)
        elif isinstance(node, (ast.IbFor, ast.IbWhile, ast.IbIf)):
            if hasattr(node, 'body'):
                self._validate_body(node.body)
            if hasattr(node, 'orelse'):
                self._validate_body(node.orelse)
        elif isinstance(node, ast.IbTry):
            self._validate_body(node.body)
            for handler in node.handlers:
                if hasattr(handler, 'body'):
                    self._validate_body(handler.body)
            self._validate_body(node.orelse)
            self._validate_body(node.finalbody)

    def _validate_body(self, body: List[ast.IbASTNode]):
        """验证语句块中的 intent 注解"""
        if not body:
            return

        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.IbIntentAnnotation):
                # @ 或 @! 注解必须紧跟行为表达式
                intent_mode = stmt.intent.mode if hasattr(stmt, 'intent') else None
                if intent_mode in ("push", "replace"):
                    # 检查下一个语句
                    if i + 1 < len(body):
                        next_stmt = body[i + 1]
                        has_behavior = self._statement_contains_behavior(next_stmt)
                        if not has_behavior:
                            self.error(
                                f"Intent annotation '{intent_mode}' must be followed by a statement with behavior expression",
                                stmt,
                                code=SEM_LLMEXCEPT_BINDING
                            )

                # 记录注解（使用节点对象作为键）
                self.intent_annotations[stmt] = {
                    'mode': intent_mode,
                    'content': stmt.intent.content if hasattr(stmt, 'intent') else None
                }

            # 递归验证
            self._validate_node(stmt)

    def _statement_contains_behavior(self, stmt: ast.IbASTNode) -> bool:
        """检查语句是否包含行为表达式"""
        if isinstance(stmt, ast.IbBehaviorExpr):
            return True

        # 检查赋值语句的值
        if isinstance(stmt, ast.IbAssign):
            return self._contains_behavior_expr(stmt.value)

        # 检查表达式语句
        if isinstance(stmt, ast.IbExpr):
            return self._contains_behavior_expr(stmt.value)

        return False

    def _contains_behavior_expr(self, node: ast.IbASTNode) -> bool:
        """递归检查节点是否包含行为表达式"""
        if isinstance(node, ast.IbBehaviorExpr):
            return True

        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        if self._contains_behavior_expr(item):
                            return True
            elif isinstance(child, ast.IbASTNode):
                if self._contains_behavior_expr(child):
                    return True

        return False


class LambdaCaptureAnalyzer(ScopedVisitor):
    """Lambda 捕获分析器

    分析 Lambda 和 Snapshot 表达式捕获的自由变量
    """

    def __init__(self, context: SemanticContext):
        super().__init__(context)
        self.lambda_captures: Dict[str, Set[str]] = {}

    def analyze(self):
        """分析 Lambda 捕获"""
        self._analyze_node(self.context.ast)

    def _analyze_node(self, node: ast.IbASTNode):
        """递归分析节点"""
        if isinstance(node, ast.IbModule):
            for stmt in node.body:
                self._analyze_node(stmt)

        elif isinstance(node, ast.IbFunctionDef):
            # 进入函数作用域，注册参数以便 lambda 捕获分析能找到它们
            func_scope = SymbolTable(parent=self.current_scope, name=node.name)
            self._register_func_params(node.args, func_scope)
            with self.enter_scope(func_scope):
                # 分析 nonlocal 声明：为包含 nonlocal 的函数填充 free_vars
                self._analyze_function_nonlocal(node)
                for stmt in node.body:
                    self._analyze_node(stmt)

        elif isinstance(node, ast.IbClassDef):
            for stmt in node.body:
                self._analyze_node(stmt)

        elif isinstance(node, ast.IbLambdaExpr):
            # 分析 Lambda 捕获
            self._analyze_lambda(node)

        else:
            # 递归分析子节点
            for attr in vars(node):
                child = getattr(node, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            self._analyze_node(item)
                elif isinstance(child, ast.IbASTNode):
                    self._analyze_node(child)

    def _analyze_lambda(self, node: ast.IbLambdaExpr):
        """分析 Lambda 表达式的捕获，并填充 node.free_vars。

        使用 SymbolResolutionPass 产生的 node_to_symbol 绑定来确定自由变量，
        而非依赖 scope.resolve（后者无法访问外层函数的局部变量）。
        """
        # 收集 lambda body 中所有 IbName 节点
        body_names = self._collect_name_nodes(node.body) if node.body else []

        # 收集 lambda 参数名（这些不是自由变量）
        param_names = set()
        for arg in node.params:
            if isinstance(arg, ast.IbArg):
                param_names.add(arg.arg)
            elif isinstance(arg, ast.IbTypeAnnotatedExpr):
                target = arg.target
                if isinstance(target, ast.IbArg):
                    param_names.add(target.arg)
                elif isinstance(target, ast.IbName):
                    param_names.add(target.id)

        # 通过 prior_symbol_bindings 确定自由变量
        node_to_symbol = self.context.prior_symbol_bindings
        captured_vars = set()
        free_var_refs = []
        seen_names = set()

        for name_node in body_names:
            var_name = name_node.id
            if var_name in param_names or var_name in seen_names:
                continue
            seen_names.add(var_name)

            sym = node_to_symbol.get(name_node)
            if sym and hasattr(sym, 'uid') and sym.uid:
                # 排除 intrinsic（内核原生）和全局符号（不需要闭包捕获）
                if sym.uid.startswith("intrinsic:"):
                    continue
                # 检查是否是外层作用域的变量（非当前 lambda 内部）
                captured_vars.add(var_name)
                free_var_refs.append([var_name, sym.uid])

        # 写入 AST 节点（序列化后进入 artifact node_data["free_vars"]）
        node.free_vars = free_var_refs

        # 记录捕获（使用节点对象作为键，供 cell_captured_symbols 使用）
        if captured_vars:
            self.lambda_captures[node] = captured_vars

    def _collect_name_nodes(self, node: ast.IbASTNode) -> list:
        """收集 AST 子树中所有 IbName 节点。"""
        result = []
        if isinstance(node, ast.IbName):
            result.append(node)
        elif isinstance(node, ast.IbASTNode):
            for attr in vars(node):
                child = getattr(node, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            result.extend(self._collect_name_nodes(item))
                elif isinstance(child, ast.IbASTNode):
                    result.extend(self._collect_name_nodes(child))
        return result

    def _collect_referenced_names(self, node: ast.IbASTNode) -> Set[str]:
        """收集节点中引用的所有名称"""
        names = set()

        if isinstance(node, ast.IbName):
            names.add(node.id)
        else:
            # 递归收集
            for attr in vars(node):
                child = getattr(node, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            names.update(self._collect_referenced_names(item))
                elif isinstance(child, ast.IbASTNode):
                    names.update(self._collect_referenced_names(child))

        return names

    @staticmethod
    def _register_func_params(args: list, scope: SymbolTable):
        """将函数参数注册到作用域中（用于 lambda 捕获分析时能够识别外层参数）。"""

        for arg_node in args:
            name = None
            if isinstance(arg_node, ast.IbArg):
                name = arg_node.arg
            elif isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                target = arg_node.target
                if isinstance(target, ast.IbArg):
                    name = target.arg
                elif isinstance(target, ast.IbName):
                    name = target.id
            if name and name not in scope.symbols:
                sym = VariableSymbol(
                    name=name,
                    kind=SymbolKind.VARIABLE,
                    def_node=arg_node,
                    spec=None,
                )
                scope.define(sym)

    def _analyze_function_nonlocal(self, node: ast.IbFunctionDef):
        """分析函数中的 nonlocal 声明，填充 node.free_vars。

        当函数包含 nonlocal 声明时，需要将 nonlocal 变量作为自由变量
        记录到 free_vars 中，使得运行时 vm_handle_IbFunctionDef 能够
        为这些变量建立 Cell 共享引用（类似 lambda 的闭包捕获机制）。
        """
        # 收集 nonlocal 声明的名称
        nonlocal_names = set()
        for stmt in node.body:
            if isinstance(stmt, ast.IbNonlocalStmt):
                nonlocal_names.update(stmt.names)

        if not nonlocal_names:
            return

        # 使用 prior_symbol_bindings 查找各 nonlocal 名称的符号 UID
        node_to_symbol = self.context.prior_symbol_bindings
        free_var_refs = []
        captured_vars = set()

        # 从函数体中收集所有 IbName 节点，找到引用 nonlocal 变量的节点
        body_names = []
        for stmt in node.body:
            body_names.extend(self._collect_name_nodes(stmt))

        seen_names = set()
        for name_node in body_names:
            var_name = name_node.id
            if var_name not in nonlocal_names or var_name in seen_names:
                continue
            seen_names.add(var_name)

            sym = node_to_symbol.get(name_node)
            if sym and hasattr(sym, 'uid') and sym.uid:
                captured_vars.add(var_name)
                free_var_refs.append([var_name, sym.uid])

        # 如果通过 name node 没有找到所有 nonlocal 变量的绑定（可能在嵌套 if/for 中），
        # 使用父作用域查找兜底
        for name in nonlocal_names:
            if name not in seen_names:
                parent = self.current_scope.parent if self.current_scope else None
                if parent:
                    sym = parent.resolve(name)
                    if sym and hasattr(sym, 'uid') and sym.uid:
                        captured_vars.add(name)
                        free_var_refs.append([name, sym.uid])

        # 写入 AST 节点
        node.free_vars = free_var_refs

        # 记录捕获（用于 cell_captured_symbols 收集）
        if captured_vars:
            self.lambda_captures[node] = captured_vars

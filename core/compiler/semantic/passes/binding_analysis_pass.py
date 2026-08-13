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
    SEM_LLMEXCEPT_MUTATING_CALL,
    SEM_LLMEXCEPT_FILE_WRITE,
    SEM_UNCATEGORIZED,
)
from core.kernel import ast
from core.kernel.symbols import SymbolTable, VariableSymbol, SymbolKind
from core.kernel.spec.registry import SpecRegistry
from core.kernel.spec.base import TypeKind

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
    - read-only 约束：llmexcept body 内禁止对 LLM 参与变量赋值（SEM_LLMEXCEPT_BODY_WRITE）及 mutating 调用（SEM_LLMEXCEPT_MUTATING_CALL）
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

                # 统一挂载：检查前一个语句是否包含行为描述
                if not self._contains_behavior_expr(prev_stmt):
                    self.error(
                        f"llmexcept must follow a statement containing a behavior expression '@~...~'. "
                        f"Found: '{prev_stmt.__class__.__name__}' without IbBehaviorExpr.",
                        stmt, code=SEM_LLMEXCEPT_BINDING
                    )
                    i += 1
                    continue

                # 统一挂载到被保护语句的 llmexcept_handler（消除两种绑定机制）
                prev_stmt.llmexcept_handler = stmt

                # 递归处理 llmexcept body
                if stmt.body:
                    stmt.body = self._rewrite_body(stmt.body)
                    self._validate_readonly_body(stmt.body, protected_stmt=prev_stmt)

                # 记录绑定
                self.llmexcept_bindings[stmt] = {
                    'target': prev_stmt,
                    'has_behavior': True
                }
                # llmexcept 语句从 body 中移除（不 append；prev_stmt 留在 body 中正常执行）
                i += 1
                continue
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

    def _extract_llm_participating_vars(self, target_stmt: Optional[ast.IbASTNode]) -> frozenset:
        """从被保护语句中提取参与 LLM 调用的变量名集合。

        包括：$ 插值变量、意图注解引用变量、赋值目标（接收 LLM 结果）。
        """
        if target_stmt is None:
            return frozenset()
        names: Set[str] = set()
        self._collect_vars_from_node(target_stmt, names)
        return frozenset(names)

    def _collect_vars_from_node(self, node: ast.IbASTNode, names: Set[str]):
        """递归收集节点中的变量引用名。"""
        if isinstance(node, ast.IbBehaviorExpr) or isinstance(node, getattr(ast, 'IbBehaviorInstance', type(None))):
            for seg in getattr(node, 'segments', []):
                if isinstance(seg, ast.IbASTNode):
                    self._collect_root_names(seg, names)
            return
        if isinstance(node, ast.IbIntentAnnotation) or isinstance(node, ast.IbIntentStackOperation):
            intent = getattr(node, 'intent', None)
            if intent and hasattr(intent, 'segments') and intent.segments:
                for seg in intent.segments:
                    if isinstance(seg, ast.IbASTNode):
                        self._collect_root_names(seg, names)
            if intent and hasattr(intent, 'expr') and intent.expr:
                self._collect_root_names(intent.expr, names)
            return
        if isinstance(node, ast.IbAssign):
            for target in node.targets:
                self._collect_root_names(target, names)
            if node.value:
                self._collect_vars_from_node(node.value, names)
            return
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self._collect_vars_from_node(item, names)
            elif isinstance(child, ast.IbASTNode):
                self._collect_vars_from_node(child, names)

    def _collect_root_names(self, node: ast.IbASTNode, names: Set[str]):
        """从表达式中提取根变量名（处理属性链和下标链）。"""
        if isinstance(node, ast.IbName):
            names.add(node.id)
        elif isinstance(node, ast.IbAttribute):
            self._collect_root_names(node.value, names)
        elif isinstance(node, ast.IbSubscript):
            self._collect_root_names(node.value, names)
        elif isinstance(node, ast.IbTypeAnnotatedExpr):
            self._collect_root_names(node.target, names)

    def _validate_readonly_body(self, body: List[ast.IbASTNode], protected_stmt: Optional[ast.IbASTNode] = None):
        """验证 llmexcept body 内的 read-only 约束（SEM_LLMEXCEPT_BODY_WRITE）。

        保护集为参与 LLM 调用的变量（$ 插值 + 意图引用 + 赋值目标）。
        非 LLM 参与变量的修改默认允许（计数器、统计等辅助用途）。

        文件写/删禁令（SEM_LLMEXCEPT_FILE_WRITE）独立于受保护变量集合：
        磁盘型快照是浅路径引用，任何文件写/删都会污染黄金快照，retry body 内一律禁止。
        """
        self._check_file_writes_in_body(body)
        protected_vars = self._extract_llm_participating_vars(protected_stmt)
        if not protected_vars:
            return
        self._check_assignments_readonly(body, protected_vars)

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

    def _check_assignments_readonly(self, body: List[ast.IbASTNode], protected_vars: frozenset):
        """递归检查 body 内的赋值和 mutating 调用是否违反 read-only 约束。"""
        for stmt in body:
            if isinstance(stmt, ast.IbAssign):
                for target in stmt.targets:
                    var_name = self._extract_assign_target_name(target)
                    if var_name and var_name in protected_vars:
                        self.error(
                            f"Cannot assign to '{var_name}' inside a llmexcept handler body: "
                            f"this variable participates in the protected LLM call. "
                            f"Use 'retry \"hint\"' to provide correction guidance instead.",
                            stmt, code=SEM_LLMEXCEPT_BODY_WRITE
                        )
            elif isinstance(stmt, ast.IbAugAssign):
                var_name = self._extract_assign_target_name(stmt.target)
                if var_name and var_name in protected_vars:
                    self.error(
                        f"Cannot assign to '{var_name}' inside a llmexcept handler body: "
                        f"this variable participates in the protected LLM call. "
                        f"Use 'retry \"hint\"' to provide correction guidance instead.",
                        stmt, code=SEM_LLMEXCEPT_BODY_WRITE
                    )

            self._check_mutating_calls(stmt, protected_vars)

            # 递归检查嵌套结构（vars() 遍历统一覆盖 body/orelse/handlers/finalbody 等语句列表）
            for attr in vars(stmt):
                child = getattr(stmt, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            self._check_assignments_readonly([item], protected_vars)

    def _check_mutating_calls(self, node: ast.IbASTNode, protected_vars: frozenset):
        """检查节点中的方法调用是否对受保护变量执行 mutating 操作。"""
        if isinstance(node, ast.IbCall):
            self._check_single_call(node, protected_vars)
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self._check_mutating_calls(item, protected_vars)
            elif isinstance(child, ast.IbASTNode):
                self._check_mutating_calls(child, protected_vars)

    def _check_single_call(self, call_node: ast.IbCall, protected_vars: frozenset):
        """检查单个调用：若接收者为受保护变量且方法为 mutating，报错。"""
        func = call_node.func
        if not isinstance(func, ast.IbAttribute):
            if isinstance(func, ast.IbName):
                self._check_user_func_call(func, call_node, protected_vars)
            return
        receiver_name = self._extract_assign_target_name(func.value)
        if not receiver_name or receiver_name not in protected_vars:
            return
        method_name = func.attr
        spec_reg = self.context.registry
        receiver_sym = self.current_scope.resolve(receiver_name) if self.current_scope else None
        if not receiver_sym or not receiver_sym.spec:
            return
        axiom = spec_reg.get_axiom(receiver_sym.spec) if hasattr(spec_reg, 'get_axiom') else None
        if not axiom:
            return
        method_specs = axiom.get_method_specs()
        method_spec = method_specs.get(method_name)
        if not method_spec:
            return
        if getattr(method_spec, 'llmexcept_safe', False):
            return
        if getattr(method_spec, 'mutating', False):
            self.error(
                f"Cannot call mutating method '{method_name}' on '{receiver_name}' "
                f"inside a llmexcept handler body: this variable participates in "
                f"the protected LLM call.",
                call_node, code=SEM_LLMEXCEPT_MUTATING_CALL
            )

    def _check_user_func_call(self, func_name_node: ast.IbName, call_node: ast.IbCall, protected_vars: frozenset):
        """检查用户函数调用：若参数包含受保护变量且函数为 mutating，报错。"""
        arg_names = set()
        for arg in (call_node.args or []):
            name = self._extract_assign_target_name(arg)
            if name:
                arg_names.add(name)
        if not arg_names & protected_vars:
            return
        func_sym = self.current_scope.resolve(func_name_node.id) if self.current_scope else None
        if not func_sym or not getattr(func_sym, 'def_node', None):
            return
        if self._is_user_func_mutating(func_sym.def_node, set()):
            violated = arg_names & protected_vars
            self.error(
                f"Cannot call mutating function '{func_name_node.id}' with "
                f"protected variable(s) {sorted(violated)} inside a llmexcept "
                f"handler body.",
                call_node, code=SEM_LLMEXCEPT_MUTATING_CALL
            )

    def _is_user_func_mutating(self, func_def_node: ast.IbASTNode, visited: set) -> bool:
        """推断用户函数是否为 mutating（体内是否对参数调用 mutating 方法）。"""
        node_id = id(func_def_node)
        if node_id in visited:
            return False
        visited.add(node_id)
        body = getattr(func_def_node, 'body', None)
        if not body:
            return False
        return self._body_contains_mutating_call(body, visited)

    def _body_contains_mutating_call(self, stmts, visited: set) -> bool:
        """扫描语句列表，检查是否存在 mutating 方法调用。"""
        for stmt in stmts:
            if isinstance(stmt, ast.IbCall):
                func = stmt.func
                if isinstance(func, ast.IbAttribute):
                    method_name = func.attr
                    receiver_name = self._extract_assign_target_name(func.value)
                    if receiver_name and self._is_known_mutating_method(method_name):
                        return True
            for attr in vars(stmt):
                child = getattr(stmt, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            if isinstance(item, ast.IbCall):
                                func = item.func
                                if isinstance(func, ast.IbAttribute):
                                    if self._is_known_mutating_method(func.attr):
                                        return True
                            if hasattr(item, 'body') and isinstance(getattr(item, 'body'), list):
                                if self._body_contains_mutating_call(item.body, visited):
                                    return True
                elif isinstance(child, ast.IbASTNode):
                    if hasattr(child, 'body') and isinstance(getattr(child, 'body'), list):
                        if self._body_contains_mutating_call(child.body, visited):
                            return True
        return False

    _KNOWN_MUTATING_METHODS = frozenset({
        "append", "insert", "remove", "pop", "sort", "reverse", "clear",
        "__setitem__", "update", "push", "merge", "combine",
        "clear_inherited", "use",
    })

    def _is_known_mutating_method(self, method_name: str) -> bool:
        return method_name in self._KNOWN_MUTATING_METHODS

    # ===== llmexcept body 文件写/删禁令（SEM_LLMEXCEPT_FILE_WRITE）=====

    def _check_file_writes_in_body(self, body: List[ast.IbASTNode]):
        """无条件扫描 llmexcept body，禁止任何文件写/删调用（直接或经用户函数间接）。

        与受保护变量集合无关：磁盘型快照是浅路径引用，任何文件写/删都会污染黄金快照。
        判定纯 spec 驱动（读 module spec 成员的 mutating 标记），正确处理别名与 shadowing。
        """
        for stmt in body:
            self._check_file_writes_in_node(stmt)

    def _check_file_writes_in_node(self, node: ast.IbASTNode):
        if isinstance(node, ast.IbFunctionDef):
            return  # 嵌套函数定义体不直接扫；被调用时经 _func_writes_files 递归覆盖
        if isinstance(node, ast.IbCall):
            self._check_single_file_write_call(node)
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self._check_file_writes_in_node(item)
            elif isinstance(child, ast.IbASTNode):
                self._check_file_writes_in_node(child)

    def _check_single_file_write_call(self, call_node: ast.IbCall):
        func = call_node.func
        # 直接：file.<写/删>(...)
        if isinstance(func, ast.IbAttribute) and self._is_file_write_call(call_node):
            self.error(
                f"Cannot call file.{func.attr} inside a llmexcept handler body: "
                f"file writes/removes corrupt the shallow path-reference snapshot. "
                f"Use 'retry \"hint\"' for correction guidance, or perform file I/O outside the handler.",
                call_node, code=SEM_LLMEXCEPT_FILE_WRITE
            )
            return
        # 间接：用户函数调用，其体内（经任意层间接）含文件写/删
        if isinstance(func, ast.IbName):
            func_sym = self.current_scope.resolve(func.id) if self.current_scope else None
            if func_sym is not None and getattr(func_sym, 'def_node', None) is not None:
                if self._func_writes_files(func_sym, set()):
                    self.error(
                        f"Cannot call '{func.id}' inside a llmexcept handler body: "
                        f"its body performs a file write/remove, which is forbidden in retry bodies.",
                        call_node, code=SEM_LLMEXCEPT_FILE_WRITE
                    )

    def _is_file_write_call(self, call_node: ast.IbCall) -> bool:
        """纯 spec 驱动判定：调用是否为某模块的 mutating 写/删成员调用。

        解析 receiver 符号 -> 若为 module spec 且其 members[attr] 标记 mutating=True 则命中。
        正确处理 ``import file as f`` 别名（resolve 别名符号读到同一 module spec），
        且不误报局部变量同名 shadowing（非 module spec 直接返回 False）。无名称兜底。
        """
        func = call_node.func
        if not isinstance(func, ast.IbAttribute):
            return False
        receiver = func.value
        if not isinstance(receiver, ast.IbName):
            return False
        attr = func.attr
        sym = self.current_scope.resolve(receiver.id) if self.current_scope else None
        spec = getattr(sym, 'spec', None) if sym is not None else None
        if spec is None:
            return False  # 未解析（未 import 等）-> 由其它检查处理，非 file 模块调用
        if getattr(spec, 'kind', None) != TypeKind.MODULE.value:
            return False  # receiver 解析为非模块（如局部变量）-> 不是 file 模块调用
        members = getattr(spec, 'members', None)
        member = members.get(attr) if members else None
        return member is not None and getattr(member, 'mutating', False)

    def _func_writes_files(self, func_sym, visited: set) -> bool:
        """递归判断用户函数体内（经任意层间接调用）是否含文件写/删。

        spec 驱动 + 作用域感知：push 该函数的 owned_scope，在其作用域内用
        _is_file_write_call 判定。visited 按 id(func_sym) 防调用图环路。
        owned_scope 缺失（异常情况）时编译期不判定，由运行时守卫兜底。
        """
        if id(func_sym) in visited:
            return False
        visited.add(id(func_sym))
        func_scope = getattr(func_sym, 'owned_scope', None)
        def_node = getattr(func_sym, 'def_node', None)
        body = getattr(def_node, 'body', None) if def_node is not None else None
        if func_scope is None or not body:
            return False
        with self.enter_scope(func_scope):
            return any(self._node_contains_file_write(stmt, visited) for stmt in body)

    def _node_contains_file_write(self, node: ast.IbASTNode, visited: set) -> bool:
        if isinstance(node, ast.IbFunctionDef):
            return False  # 跳过嵌套函数定义体
        if isinstance(node, ast.IbCall) and self._call_writes_files(node, visited):
            return True
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode) and self._node_contains_file_write(item, visited):
                        return True
            elif isinstance(child, ast.IbASTNode) and self._node_contains_file_write(child, visited):
                return True
        return False

    def _call_writes_files(self, call_node: ast.IbCall, visited: set) -> bool:
        """判断单个调用是否（直接或经用户函数间接）写文件。"""
        if self._is_file_write_call(call_node):
            return True
        func = call_node.func
        if isinstance(func, ast.IbName):
            func_sym = self.current_scope.resolve(func.id) if self.current_scope else None
            if func_sym is not None and getattr(func_sym, 'def_node', None) is not None:
                return self._func_writes_files(func_sym, visited)
        return False



    def _extract_assign_target_name(self, target: ast.IbASTNode) -> Optional[str]:
        """从赋值目标提取根变量名（覆盖简单名、属性链、下标链）。"""
        if isinstance(target, ast.IbName):
            return target.id
        elif isinstance(target, ast.IbTypeAnnotatedExpr):
            return self._extract_assign_target_name(target.target)
        elif isinstance(target, ast.IbAttribute):
            return self._extract_assign_target_name(target.value)
        elif isinstance(target, ast.IbSubscript):
            return self._extract_assign_target_name(target.value)
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
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code
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
        # 泛型方法体内类型参数收集状态（Box[T] 表达式位置的 T）。
        self._func_node_stack: List[ast.IbFunctionDef] = []
        self._type_param_refs: Set[tuple] = set()

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
                self._analyze_function_captures(node)
                # 泛型方法体内引用的类型参数收集（Box[T] 的 T 表达式位置）。
                self._func_node_stack.append(node)
                try:
                    for stmt in node.body:
                        self._analyze_node(stmt)
                finally:
                    self._func_node_stack.pop()
                # 回收类型参数 [name, uid] 对到函数节点（序列化→运行时注册）。
                if self._type_param_refs:
                    node.type_param_uids = sorted(
                        list(self._type_param_refs), key=lambda x: x[0]
                    )
                    self._type_param_refs = set()

        elif isinstance(node, ast.IbClassDef):
            # 进入类作用域（含类型参数符号），使方法体内 T 可 resolve 到
            # TYPE_PARAM 符号（Box[T] 表达式位置收集）。
            class_scope = None
            class_sym = self.current_scope.resolve(node.name) if self.current_scope else None
            if class_sym is not None and getattr(class_sym, "owned_scope", None):
                class_scope = class_sym.owned_scope
            if class_scope is not None:
                with self.enter_scope(class_scope):
                    for stmt in node.body:
                        self._analyze_node(stmt)
            else:
                for stmt in node.body:
                    self._analyze_node(stmt)

        elif isinstance(node, ast.IbLambdaExpr):
            # 分析 Lambda 捕获
            self._analyze_lambda(node)

        elif isinstance(node, ast.IbName):
            # 泛型方法体内类型参数引用收集：T（TYPE_PARAM 符号）在表达式位置
            # 需运行时值（Box[T] slice），编译期收集 [name, sym_uid] 对供
            # 方法帧按 UID 注册特化实参的类型标识。
            if self._func_node_stack:
                sym = self.current_scope.resolve(node.id)
                if (sym is not None
                        and getattr(sym, "kind", None) == SymbolKind.TYPE_PARAM
                        and getattr(sym, "uid", None)):
                    self._type_param_refs.add((node.id, sym.uid))

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
        """收集 AST 子树中所有 IbName 节点。

        不进入嵌套函数/类/LLM 函数**定义体**（其内部引用属于嵌套作用域，
        由各自的分析独立捕获——否则外层会把内层引用的变量误捕获）。
        """
        result = []
        if isinstance(node, ast.IbName):
            result.append(node)
        elif isinstance(node, (ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbClassDef)):
            # 嵌套定义体：不递归（内层引用由内层函数自己的捕获分析处理）
            return result
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

    def _analyze_function_captures(self, node: ast.IbFunctionDef):
        """分析函数外层引用，自动捕获只读自由变量（R6）。

        函数体引用的外层名称（非本函数参数/局部、非 intrinsic、非全局）自动
        纳入 ``free_vars``，使运行时 ``vm_handle_IbFunctionDef`` 为其建立 Cell
        共享引用（与 lambda 捕获机制同构）。``nonlocal`` 声明仅标记"写访问"，
        其名称必是外层引用，同样经本分析捕获（写路径运行时经 Cell 写回）。

        行为变更：原"引用外层局部未声明 nonlocal → 运行时 not defined"现变为
        "自动捕获可用"（对齐 Python 心智模型：读捕获自动、写需 nonlocal）。
        """
        # 收集 nonlocal 声明的名称（写访问标记；名称本身仍是外层引用）
        nonlocal_names = set()
        for stmt in node.body:
            if isinstance(stmt, ast.IbNonlocalStmt):
                nonlocal_names.update(stmt.names)

        # 使用 prior_symbol_bindings 查找各引用名称的符号 UID
        node_to_symbol = self.context.prior_symbol_bindings
        free_var_refs = []
        captured_vars = set()

        # 从函数体中收集所有 IbName 节点
        body_names = []
        for stmt in node.body:
            body_names.extend(self._collect_name_nodes(stmt))

        # 当前函数作用域 UID（判断"本函数内定义"的符号）；null 时退化只排 intrinsic
        func_scope_uid = self.current_scope.uid if self.current_scope is not None else None

        seen_names = set()
        for name_node in body_names:
            var_name = name_node.id
            if var_name in seen_names:
                continue
            seen_names.add(var_name)

            sym = node_to_symbol.get(name_node)
            if not sym or not getattr(sym, 'uid', None):
                continue
            sym_uid = sym.uid
            # 排除 intrinsic（内核原生符号）
            if sym_uid.startswith("intrinsic:"):
                continue
            # 排除本函数内定义的符号（参数/局部变量）：uid 以本函数作用域为前缀
            if func_scope_uid and sym_uid.startswith(func_scope_uid + ":"):
                continue
            # 排除全局作用域符号（root scope uid 无 "/" 分层，如 "scope_global:name"；
            # 本函数及外层函数 uid 形如 "scope_global/outer:x" 含 "/"）。全局始终
            # 可达，无需 Cell 捕获。
            if "/" not in sym_uid:
                continue
            captured_vars.add(var_name)
            free_var_refs.append([var_name, sym_uid])

        # 兜底：主通道（node_to_symbol 遍历函数体）未覆盖的 nonlocal 名，再经父
        # 作用域按名解析。注意：_collect_name_nodes 会递归进入嵌套 if/for 等块，
        # 因此"嵌套块中绑定缺失"情形下名称必在 seen_names 中，不会进入本兜底——
        # 本兜底只覆盖"函数体完全未出现该名"的退化情形（SymbolResolver 缺口下
        # 存在漏捕获风险，当前无实际触发路径）。
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

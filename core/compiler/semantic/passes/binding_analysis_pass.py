"""
Pass 4: Binding Analysis Pass

职责：各种绑定分析（LLMExcept、Intent、Lambda 捕获）
输入：Context with type_bindings
输出：Context with binding metadata
"""

from dataclasses import replace
from typing import Optional, List, Dict, Any, Set

from core.kernel import ast
from core.kernel.symbols import SymbolTable

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class BindingAnalysisPass(BasePass):
    """绑定分析 Pass（Pass 4）

    包含三个子分析器：
    1. LLMExceptBindingAnalyzer - llmexcept 绑定分析
    2. IntentContextValidator - intent 上下文验证
    3. LambdaCaptureAnalyzer - Lambda/Snapshot 捕获分析
    """

    def __init__(self):
        super().__init__("BindingAnalysisPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行绑定分析 Pass"""
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

        # 合并元数据
        new_metadata = context.metadata
        # LLMExcept 绑定
        for node_uid, binding in llmexcept_analyzer.llmexcept_bindings.items():
            new_metadata.llmexcept_bindings[node_uid] = binding
        # Intent 注解
        for node_uid, annotation in intent_validator.intent_annotations.items():
            new_metadata.intent_annotations[node_uid] = annotation
        # Lambda 捕获
        for node_uid, captures in lambda_analyzer.lambda_captures.items():
            if 'lambda_captures' not in new_metadata.behavior_metadata:
                new_metadata.behavior_metadata['lambda_captures'] = {}
            new_metadata.behavior_metadata['lambda_captures'][node_uid] = captures

        new_context = replace(context, metadata=new_metadata)

        return PassResult.ok(new_context, diagnostics=all_diagnostics)


class LLMExceptBindingAnalyzer:
    """LLMExcept 绑定分析器

    验证 llmexcept 语句的合法性：
    - llmexcept 必须关联到包含行为表达式的语句
    - 检查 llmexcept target 的合法性
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []
        self.llmexcept_bindings: Dict[str, Any] = {}

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000"):
        """记录错误诊断"""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def analyze(self):
        """分析 llmexcept 绑定"""
        self._analyze_node(self.context.ast)

    def _analyze_node(self, node: ast.IbASTNode):
        """递归分析节点"""
        if isinstance(node, ast.IbModule):
            self._analyze_body(node.body)
        elif isinstance(node, ast.IbFunctionDef):
            self._analyze_body(node.body)
        elif isinstance(node, ast.IbLLMFunctionDef):
            # LLM 函数内部不需要 llmexcept（整个函数就是行为）
            pass
        elif isinstance(node, ast.IbClassDef):
            for stmt in node.body:
                self._analyze_node(stmt)
        elif isinstance(node, (ast.IbFor, ast.IbWhile, ast.IbIf)):
            # 递归进入控制流容器
            if hasattr(node, 'body'):
                self._analyze_body(node.body)
            if hasattr(node, 'orelse'):
                self._analyze_body(node.orelse)
        elif isinstance(node, ast.IbTry):
            self._analyze_body(node.body)
            for handler in node.handlers:
                if hasattr(handler, 'body'):
                    self._analyze_body(handler.body)
            self._analyze_body(node.orelse)
            self._analyze_body(node.finalbody)

    def _analyze_body(self, body: List[ast.IbASTNode]):
        """分析语句块中的 llmexcept"""
        if not body:
            return

        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.IbLLMExceptionalStmt):
                # 验证 llmexcept 的 target
                if stmt.target:
                    # 检查 target 是否包含行为表达式
                    has_behavior = self._contains_behavior_expr(stmt.target)
                    if not has_behavior:
                        self.error(
                            "llmexcept must be associated with a statement containing behavior expression (@~...~)",
                            stmt,
                            code="SEM_040"
                        )

                    # 记录绑定
                    node_uid = getattr(stmt, 'uid', None)
                    if node_uid:
                        self.llmexcept_bindings[node_uid] = {
                            'target_uid': getattr(stmt.target, 'uid', None),
                            'has_behavior': has_behavior
                        }
                else:
                    self.error(
                        "llmexcept statement has no target",
                        stmt,
                        code="SEM_040"
                    )

            # 递归分析嵌套节点
            self._analyze_node(stmt)

    def _contains_behavior_expr(self, node: ast.IbASTNode) -> bool:
        """检查节点是否包含行为表达式"""
        if isinstance(node, ast.IbBehaviorExpr):
            return True

        # 递归检查子节点
        for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
            if attr.startswith('_'):
                continue
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        if self._contains_behavior_expr(item):
                            return True
            elif isinstance(child, ast.IbASTNode):
                if self._contains_behavior_expr(child):
                    return True

        return False


class IntentContextValidator:
    """Intent 上下文验证器

    验证 intent 注解的合法性：
    - @ 或 @! 注解必须紧跟行为表达式
    - @+ 和 @- 可以独立存在
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []
        self.intent_annotations: Dict[str, Any] = {}

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000"):
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
                if stmt.op in ("push", "replace"):
                    # 检查下一个语句
                    if i + 1 < len(body):
                        next_stmt = body[i + 1]
                        has_behavior = self._statement_contains_behavior(next_stmt)
                        if not has_behavior:
                            self.error(
                                f"Intent annotation '{stmt.op}' must be followed by a statement with behavior expression",
                                stmt,
                                code="SEM_050"
                            )

                # 记录注解
                node_uid = getattr(stmt, 'uid', None)
                if node_uid:
                    self.intent_annotations[node_uid] = {
                        'op': stmt.op,
                        'text': stmt.text if hasattr(stmt, 'text') else None
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

        for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
            if attr.startswith('_'):
                continue
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        if self._contains_behavior_expr(item):
                            return True
            elif isinstance(child, ast.IbASTNode):
                if self._contains_behavior_expr(child):
                    return True

        return False


class LambdaCaptureAnalyzer:
    """Lambda 捕获分析器

    分析 Lambda 和 Snapshot 表达式捕获的自由变量
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.diagnostics: List[Diagnostic] = []
        self.lambda_captures: Dict[str, Set[str]] = {}

        # 作用域栈
        self.scope_stack: List[SymbolTable] = [self.symbol_table]

    @property
    def current_scope(self) -> SymbolTable:
        """当前作用域"""
        return self.scope_stack[-1]

    def push_scope(self, scope: SymbolTable):
        """进入新作用域"""
        self.scope_stack.append(scope)

    def pop_scope(self):
        """退出作用域"""
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()

    def analyze(self):
        """分析 Lambda 捕获"""
        self._analyze_node(self.context.ast)

    def _analyze_node(self, node: ast.IbASTNode):
        """递归分析节点"""
        if isinstance(node, ast.IbModule):
            for stmt in node.body:
                self._analyze_node(stmt)

        elif isinstance(node, ast.IbFunctionDef):
            # 进入函数作用域
            func_scope = SymbolTable(parent=self.current_scope, name=node.name)
            self.push_scope(func_scope)
            try:
                for stmt in node.body:
                    self._analyze_node(stmt)
            finally:
                self.pop_scope()

        elif isinstance(node, ast.IbClassDef):
            for stmt in node.body:
                self._analyze_node(stmt)

        elif isinstance(node, ast.IbLambdaExpr):
            # 分析 Lambda 捕获
            self._analyze_lambda(node)

        else:
            # 递归分析子节点
            for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
                if attr.startswith('_'):
                    continue
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            self._analyze_node(item)
                elif isinstance(child, ast.IbASTNode):
                    self._analyze_node(child)

    def _analyze_lambda(self, node: ast.IbLambdaExpr):
        """分析 Lambda 表达式的捕获"""
        # 收集 lambda 内部引用的所有名称
        referenced_names = self._collect_referenced_names(node)

        # 收集 lambda 参数名
        param_names = set()
        for arg in node.args:
            if isinstance(arg, ast.IbArg):
                param_names.add(arg.arg)

        # 自由变量 = 引用的名称 - 参数名
        free_vars = referenced_names - param_names

        # 验证自由变量在外部作用域中存在
        captured_vars = set()
        for var_name in free_vars:
            sym = self.current_scope.symbols.get(var_name)
            if sym:
                captured_vars.add(var_name)

        # 记录捕获
        node_uid = getattr(node, 'uid', None)
        if node_uid:
            self.lambda_captures[node_uid] = captured_vars

    def _collect_referenced_names(self, node: ast.IbASTNode) -> Set[str]:
        """收集节点中引用的所有名称"""
        names = set()

        if isinstance(node, ast.IbName):
            names.add(node.id)
        else:
            # 递归收集
            for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
                if attr.startswith('_'):
                    continue
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            names.update(self._collect_referenced_names(item))
                elif isinstance(child, ast.IbASTNode):
                    names.update(self._collect_referenced_names(child))

        return names

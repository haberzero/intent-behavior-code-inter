"""
Behavior Dependency Pass (BindingPhase sub-step 2)

职责：分析 Behavior 表达式的 LLM 依赖关系，并计算 dispatch_eligible
输入：Context with all bindings
输出：AST 节点的 llm_deps 和 dispatch_eligible 字段
"""

from typing import Optional, List, Set

from core.base.diagnostics.codes import SEM_UNCATEGORIZED
from core.kernel import ast

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class BehaviorDependencyPass(BasePass):
    """行为依赖分析 Pass（BindingPhase sub-step 2）

    分析 Behavior 表达式之间的依赖关系：
    - 构建 LLM 依赖图（写入 node.llm_deps）
    - 检测循环依赖
    - 计算是否可并行调度（写入 node.dispatch_eligible）
    """

    def __init__(self):
        super().__init__("BehaviorDependencyPass")

    def run(self, context: SemanticContext) -> PassResult:
        """分析结果直接写入 AST 节点的 llm_deps 和 dispatch_eligible 字段。"""
        analyzer = BehaviorDependencyAnalyzer(context)
        analyzer.analyze()
        return PassResult.ok(context, diagnostics=analyzer.diagnostics)


class BehaviorDependencyAnalyzer:
    """Behavior 依赖分析器

    分析每个 IbBehaviorExpr 的依赖：
    - 扫描 segments 中的插值变量
    - 追溯变量定义来源
    - 如果来源是另一个 IbBehaviorExpr，记录依赖（写入 node.llm_deps）
    - 依可调度规则计算 dispatch_eligible（默认 True，命中规则则 False）
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []

        # 变量到行为表达式节点的映射（用于追溯）
        # symbol_name -> IbBehaviorExpr node
        self.symbol_to_behavior: dict[str, ast.IbBehaviorExpr] = {}

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
        """记录错误诊断"""
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code
        ))

    def analyze(self):
        """分析行为依赖 + 计算 dispatch_eligible"""
        self._analyze_node(self.context.ast, in_loop=False, in_llmexcept=False, in_function=False)
        # 第二轮：检测循环依赖并强制不可调度（保底；循环必然含插值依赖已置 False）
        self._detect_cycles(self.context.ast)

    # ------------------------------------------------------------------
    # 遍历（携带可调度上下文标志）
    # ------------------------------------------------------------------

    def _analyze_node(self, node: ast.IbASTNode, in_loop: bool, in_llmexcept: bool, in_function: bool):
        """递归分析节点。上下文标志（可调度规则）随遍历传播：
        - ``in_loop``：处于循环体
        - ``in_llmexcept``：处于 llmexcept 保护语句子树
        - ``in_function``：处于函数 / lambda 体
        """
        if node is None:
            return

        if isinstance(node, ast.IbBehaviorExpr):
            self._analyze_behavior_expr(node, in_loop, in_llmexcept, in_function)
            return

        if isinstance(node, ast.IbAssign):
            protected = node.llmexcept_handler is not None
            # 先分析右侧
            self._analyze_node(node.value, in_loop, in_llmexcept or protected, in_function)
            # 注册赋值：如果右侧是 Behavior 表达式，记录映射
            if isinstance(node.value, ast.IbBehaviorExpr):
                for target in node.targets:
                    var_name = self._get_var_name(target)
                    if var_name:
                        self.symbol_to_behavior[var_name] = node.value
            return

        if isinstance(node, ast.IbFunctionDef):
            # 函数体：可重复执行上下文，体内行为一律不可调度
            for stmt in getattr(node, "body", None) or []:
                self._analyze_node(stmt, in_loop=False, in_llmexcept=False, in_function=True)
            return

        if isinstance(node, ast.IbLambdaExpr):
            # lambda 体是单个表达式节点（非列表）；同函数体不可调度
            body = node.body
            if body is None:
                return
            if isinstance(body, list):
                for stmt in body:
                    self._analyze_node(stmt, in_loop=False, in_llmexcept=False, in_function=True)
            else:
                self._analyze_node(body, in_loop=False, in_llmexcept=False, in_function=True)
            return

        if isinstance(node, (ast.IbWhile, ast.IbFor)):
            # 循环体：同 node_uid 多次 dispatch 会覆写 _pending_futures 条目
            protected = node.llmexcept_handler is not None
            for stmt in getattr(node, "body", None) or []:
                self._analyze_node(stmt, in_loop=True, in_llmexcept=in_llmexcept or protected, in_function=in_function)
            for stmt in getattr(node, "orelse", None) or []:
                self._analyze_node(stmt, in_loop=True, in_llmexcept=in_llmexcept or protected, in_function=in_function)
            return

        # 其它语句 / 表达式：统一递归，传播受保护标志
        protected = getattr(node, "llmexcept_handler", None) is not None
        next_llmexcept = in_llmexcept or protected
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self._analyze_node(item, in_loop, next_llmexcept, in_function)
            elif isinstance(child, ast.IbASTNode):
                self._analyze_node(child, in_loop, next_llmexcept, in_function)

    def _analyze_behavior_expr(self, node: ast.IbBehaviorExpr, in_loop: bool, in_llmexcept: bool, in_function: bool):
        """分析单个 Behavior 表达式的依赖与可调度性，直接写入 AST 节点"""
        # 收集依赖的行为表达式节点
        deps: List[ast.IbBehaviorExpr] = []
        seen: Set[int] = set()  # 使用 id() 去重

        # 扫描 segments 中的插值表达式
        for segment in node.segments:
            if isinstance(segment, ast.IbASTNode):
                # 收集引用的变量
                referenced_vars = self._collect_referenced_vars(segment)
                for var_name in referenced_vars:
                    # 如果变量来自另一个行为表达式，记录依赖
                    if var_name in self.symbol_to_behavior:
                        dep_node = self.symbol_to_behavior[var_name]
                        if id(dep_node) not in seen:
                            deps.append(dep_node)
                            seen.add(id(dep_node))

        node.llm_deps = deps
        node.dispatch_eligible = self._is_dispatch_eligible(deps, in_loop, in_llmexcept, in_function)

    @staticmethod
    def _is_dispatch_eligible(deps: List[ast.IbBehaviorExpr], in_loop: bool, in_llmexcept: bool, in_function: bool) -> bool:
        """可调度判定：依赖图为 DAG 且不命中任何强制 False 规则。

        规则：
        1. 插值依赖：前序 behavior 的输出是当前 behavior 的 $var 输入
        2. llmexcept 保护（snapshot 隔离约束；运行时另有帧守卫）
        3. 可重复执行上下文：循环体 / 函数体——同 node_uid 多次 dispatch
           会覆写 `_pending_futures` 条目导致旧 Future 泄漏与读点解析错乱
           （Cell 目标规则被"函数体"规则吸收：cell 只能在函数内形成，
           而函数体内行为一律不可调度）
        """
        if deps:
            return False
        if in_loop:
            return False
        if in_llmexcept:
            return False
        if in_function:
            return False
        return True

    def _collect_referenced_vars(self, node: ast.IbASTNode) -> Set[str]:
        """收集节点中引用的所有变量"""
        vars_set = set()

        if isinstance(node, ast.IbName):
            vars_set.add(node.id)
        else:
            for attr in vars(node):
                child = getattr(node, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            vars_set.update(self._collect_referenced_vars(item))
                elif isinstance(child, ast.IbASTNode):
                    vars_set.update(self._collect_referenced_vars(child))

        return vars_set

    def _get_var_name(self, target: ast.IbASTNode) -> Optional[str]:
        """从赋值目标获取变量名"""
        if isinstance(target, ast.IbName):
            return target.id
        elif isinstance(target, ast.IbTypeAnnotatedExpr):
            if isinstance(target.target, ast.IbName):
                return target.target.id
        return None

    def _detect_cycles(self, root: ast.IbASTNode):
        """检测循环依赖并标记不可并行调度"""
        # 遍历所有 Behavior 表达式节点
        behavior_nodes = self._collect_behavior_nodes(root)

        for node in behavior_nodes:
            if self._has_cycle(node, set()):
                node.dispatch_eligible = False

    def _collect_behavior_nodes(self, node: ast.IbASTNode) -> List[ast.IbBehaviorExpr]:
        """收集所有 Behavior 表达式节点"""
        nodes = []

        if isinstance(node, ast.IbBehaviorExpr):
            nodes.append(node)

        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        nodes.extend(self._collect_behavior_nodes(item))
            elif isinstance(child, ast.IbASTNode):
                nodes.extend(self._collect_behavior_nodes(child))

        return nodes

    def _has_cycle(self, node: ast.IbBehaviorExpr, visited: Set[int]) -> bool:
        """检测从 node 开始是否存在循环（使用节点对象 id）"""
        node_id = id(node)

        if node_id in visited:
            return True

        visited.add(node_id)

        # 检查所有依赖
        for dep in node.llm_deps:
            if self._has_cycle(dep, visited.copy()):
                return True

        return False

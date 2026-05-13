"""
Pass 5: Behavior Dependency Pass

职责：分析 Behavior 表达式的 LLM 依赖关系
输入：Context with all bindings
输出：AST nodes with llm_deps and dispatch_eligible fields updated

设计原则：
- 依赖信息是程序结构的一部分，直接写入 AST 节点（遵循 V1 设计）
- llm_deps 和 dispatch_eligible 是 AST 固有属性，会被序列化器持久化
- 不使用 MetadataStore 存储这些信息（避免重复和同步问题）
"""

from typing import Optional, List, Set

from core.kernel import ast

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class BehaviorDependencyPass(BasePass):
    """行为依赖分析 Pass（Pass 5）

    分析 Behavior 表达式之间的依赖关系：
    - 构建 LLM 依赖图（写入 node.llm_deps）
    - 检测循环依赖
    - 标记是否可并行调度（写入 node.dispatch_eligible）
    """

    def __init__(self):
        super().__init__("BehaviorDependencyPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行行为依赖分析 Pass

        分析结果直接写入 AST 节点的 llm_deps 和 dispatch_eligible 字段。
        这遵循 V1 的正确设计：依赖信息是程序结构的一部分，应该持久化到 AST。
        """
        analyzer = BehaviorDependencyAnalyzer(context)
        analyzer.analyze()

        # 分析器已经将结果写入 AST 节点
        # 无需修改 metadata，因为 llm_deps 和 dispatch_eligible 是 AST 固有属性

        return PassResult.ok(context, diagnostics=analyzer.diagnostics)


class BehaviorDependencyAnalyzer:
    """Behavior 依赖分析器

    分析每个 IbBehaviorExpr 的依赖：
    - 扫描 segments 中的插值变量
    - 追溯变量定义来源
    - 如果来源是另一个 IbBehaviorExpr，记录依赖（写入 node.llm_deps）
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []

        # 变量到行为表达式节点的映射（用于追溯）
        # symbol_name -> IbBehaviorExpr node
        self.symbol_to_behavior: dict[str, ast.IbBehaviorExpr] = {}

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
        """分析行为依赖"""
        self._analyze_node(self.context.ast)
        # 第二轮：检测循环依赖并标记 dispatch_eligible
        self._detect_cycles(self.context.ast)

    def _analyze_node(self, node: ast.IbASTNode):
        """递归分析节点，建立依赖关系"""
        if isinstance(node, ast.IbAssign):
            # 先分析右侧（可能为None，如类字段声明）
            if node.value is not None:
                self._analyze_node(node.value)
            # 注册赋值：如果右侧是 Behavior 表达式，记录映射
            if isinstance(node, ast.IbBehaviorExpr):
                # 记录变量到行为表达式的映射
                for target in node.targets:
                    var_name = self._get_var_name(target)
                    if var_name:
                        self.symbol_to_behavior[var_name] = node.value

        elif isinstance(node, ast.IbBehaviorExpr):
            self._analyze_behavior_expr(node)

        else:
            # 递归分析子节点（使用安全迭代）
            if node is not None and hasattr(node, '__dict__'):
                for attr, child in vars(node).items():
                    if attr.startswith('_'):
                        continue
                    if isinstance(child, list):
                        for item in child:
                            if isinstance(item, ast.IbASTNode):
                                self._analyze_node(item)
                    elif isinstance(child, ast.IbASTNode):
                        self._analyze_node(child)

    def _analyze_behavior_expr(self, node: ast.IbBehaviorExpr):
        """分析单个 Behavior 表达式的依赖，直接写入 node.llm_deps"""
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

        # ✅ 直接写入 AST 节点（V1 的正确设计）
        node.llm_deps = deps
        # 默认可调度，循环检测时会修改
        node.dispatch_eligible = True

    def _collect_referenced_vars(self, node: ast.IbASTNode) -> Set[str]:
        """收集节点中引用的所有变量"""
        vars_set = set()

        if isinstance(node, ast.IbName):
            vars_set.add(node.id)
        else:
            for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
                if attr.startswith('_'):
                    continue
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
                # ✅ 直接修改 AST 节点
                node.dispatch_eligible = False

    def _collect_behavior_nodes(self, node: ast.IbASTNode) -> List[ast.IbBehaviorExpr]:
        """收集所有 Behavior 表达式节点"""
        nodes = []

        if isinstance(node, ast.IbBehaviorExpr):
            nodes.append(node)

        for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
            if attr.startswith('_'):
                continue
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

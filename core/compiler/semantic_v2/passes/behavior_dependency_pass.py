"""
Pass 5: Behavior Dependency Pass

职责：分析 Behavior 表达式的 LLM 依赖关系
输入：Context with all bindings
输出：Context with dependency metadata
"""

from dataclasses import replace
from typing import Optional, List, Dict, Any, Set

from core.kernel import ast

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class BehaviorDependencyPass(BasePass):
    """行为依赖分析 Pass（Pass 5）

    分析 Behavior 表达式之间的依赖关系：
    - 构建 LLM 依赖图
    - 检测循环依赖
    - 标记是否可并行调度
    """

    def __init__(self):
        super().__init__("BehaviorDependencyPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行行为依赖分析 Pass"""
        analyzer = BehaviorDependencyAnalyzer(context)
        analyzer.analyze()

        # 更新元数据
        new_metadata = context.metadata
        for node_uid, deps in analyzer.behavior_dependencies.items():
            if 'behavior_dependencies' not in new_metadata.behavior_metadata:
                new_metadata.behavior_metadata['behavior_dependencies'] = {}
            new_metadata.behavior_metadata['behavior_dependencies'][node_uid] = deps

        new_context = replace(context, metadata=new_metadata)

        return PassResult.ok(new_context, diagnostics=analyzer.diagnostics)


class BehaviorDependencyAnalyzer:
    """Behavior 依赖分析器

    分析每个 IbBehaviorExpr 的依赖：
    - 扫描 segments 中的插值变量
    - 追溯变量定义来源
    - 如果来源是另一个 IbBehaviorExpr，记录依赖
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.diagnostics: List[Diagnostic] = []

        # 行为依赖：node_uid -> {'deps': [uid], 'dispatch_eligible': bool}
        self.behavior_dependencies: Dict[str, Dict[str, Any]] = {}

        # 变量到行为表达式的映射（用于追溯）
        # symbol_name -> behavior_node_uid
        self.symbol_to_behavior: Dict[str, str] = {}

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
        # 第二轮：检测循环依赖
        self._detect_cycles()

    def _analyze_node(self, node: ast.IbASTNode):
        """递归分析节点"""
        if isinstance(node, ast.IbAssign):
            # 先分析右侧
            self._analyze_node(node.value)
            # 注册赋值
            if isinstance(node.value, ast.IbBehaviorExpr):
                behavior_uid = getattr(node.value, 'uid', None)
                if behavior_uid:
                    # 记录变量到行为表达式的映射
                    for target in node.targets:
                        var_name = self._get_var_name(target)
                        if var_name:
                            self.symbol_to_behavior[var_name] = behavior_uid

        elif isinstance(node, ast.IbBehaviorExpr):
            self._analyze_behavior_expr(node)

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

    def _analyze_behavior_expr(self, node: ast.IbBehaviorExpr):
        """分析单个 Behavior 表达式的依赖"""
        node_uid = getattr(node, 'uid', None)
        if not node_uid:
            return

        # 收集依赖的行为表达式
        deps = set()

        # 扫描 segments 中的插值表达式
        for segment in node.segments:
            if isinstance(segment, ast.IbASTNode):
                # 收集引用的变量
                referenced_vars = self._collect_referenced_vars(segment)
                for var_name in referenced_vars:
                    # 如果变量来自另一个行为表达式，记录依赖
                    if var_name in self.symbol_to_behavior:
                        dep_uid = self.symbol_to_behavior[var_name]
                        deps.add(dep_uid)

        # 记录依赖
        self.behavior_dependencies[node_uid] = {
            'deps': list(deps),
            'dispatch_eligible': True  # 默认可调度，后续检测循环时修改
        }

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

    def _detect_cycles(self):
        """检测循环依赖并标记不可并行调度"""
        # 对每个行为表达式检测是否存在循环
        for node_uid in self.behavior_dependencies:
            if self._has_cycle(node_uid, set()):
                self.behavior_dependencies[node_uid]['dispatch_eligible'] = False

    def _has_cycle(self, node_uid: str, visited: Set[str]) -> bool:
        """检测从 node_uid 开始是否存在循环"""
        if node_uid in visited:
            return True

        if node_uid not in self.behavior_dependencies:
            return False

        visited.add(node_uid)

        deps = self.behavior_dependencies[node_uid]['deps']
        for dep_uid in deps:
            if self._has_cycle(dep_uid, visited.copy()):
                return True

        return False

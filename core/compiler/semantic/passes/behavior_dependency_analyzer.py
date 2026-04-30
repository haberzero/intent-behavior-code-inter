"""
core.compiler.semantic.passes.behavior_dependency_analyzer — M5a DDG 分析。

设计目标
--------
对每个 ``IbBehaviorExpr`` 节点扫描其模板插值变量（``segments`` 中的
``IbExpr``），向上追溯每个变量定义的来源；如果某个变量是另一个
``IbBehaviorExpr`` 的求值结果，则把那个上游 behavior 记入当前节点的
``llm_deps`` 列表中。

公开行为
--------
* 写入字段 ``IbBehaviorExpr.llm_deps : List[IbBehaviorExpr]``：
  按 AST 出现顺序、去重后的上游依赖
* 写入字段 ``IbBehaviorExpr.dispatch_eligible : bool``：
  - True ：本节点 ``llm_deps`` 中所有依赖也是 ``dispatch_eligible``（
            即图无环），可独立调度
  - False：本节点存在循环依赖（直接或间接）；运行时必须串行求值

实现注意
--------
* M5a 不构建跨函数的全局依赖图——只在 **同一个函数体 / 模块顶层**
  范围内追溯；跨函数调用产生的 behavior 依赖目前保守视为 None
  （未来可扩展）。
* 仅在语义分析整个流水线 **最后一步** 运行，依赖前序 Pass 已经在
  ``side_table.node_to_symbol`` 中绑定好每个 ``IbName`` 的 Symbol。
* 直接修改 AST 节点字段；序列化器自动把 ``List[IbBehaviorExpr]``
  转为 UID 列表（见 ``_collect_node`` 的 ``_process_value``），无需
  额外侧表。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from core.kernel import ast

if TYPE_CHECKING:
    from .side_table import SideTableManager


class BehaviorDependencyAnalyzer:
    """语义阶段 Pass 5：扫描 ``IbBehaviorExpr`` 的 LLM 依赖图。

    使用方法::

        analyzer = BehaviorDependencyAnalyzer(side_table)
        analyzer.analyze(module_ast)
    """

    def __init__(self, side_table: "SideTableManager"):
        self.side_table = side_table
        # symbol id() → 最近一次定义它的 ``IbBehaviorExpr``（如果是 LLM 来源）。
        # 使用 id(sym) 作为键：Symbol 对象本身可能 unhashable / mutable。
        # 注意：id() 仅在同一 Python 对象生命周期内稳定；若 Symbol 被重建
        # （如反序列化），id() 键失效，需改用 UID。本分析器在语义阶段一次性
        # 遍历同一棵 AST，所有 Symbol 实例在该阶段都活跃，无此问题。
        self._symbol_to_behavior_def: Dict[int, ast.IbBehaviorExpr] = {}

    # ------------------------------------------------------------------
    # 公开入口
    # ------------------------------------------------------------------

    def analyze(self, root: ast.IbASTNode) -> None:
        """对整个 AST 树运行依赖分析（写入每个 IbBehaviorExpr 的字段）。"""
        self._symbol_to_behavior_def = {}
        self._walk(root)
        # 第二轮：根据 llm_deps 推导 dispatch_eligible
        # （第一轮中默认 dispatch_eligible=True；只在检测到环时改为 False）
        self._resolve_dispatch_eligible(root)

    # ------------------------------------------------------------------
    # AST 遍历（按 AST 顺序，先访问子节点；遇到赋值时维护 symbol→behavior 映射）
    # ------------------------------------------------------------------

    def _walk(self, node: Any) -> None:
        if isinstance(node, ast.IbAssign):
            # 先求值 RHS，再注册 symbol→IbBehaviorExpr 映射；这样赋值表达式自身
            # 内部对其他 symbol 的引用会正常被解析为前序定义，而不是被覆盖。
            self._walk(node.value)
            self._register_assign_targets(node)
            return

        if isinstance(node, ast.IbBehaviorExpr):
            self._analyze_behavior_expr(node)
            return

        # 其他节点：递归子节点
        for child in self._iter_children(node):
            self._walk(child)

    def _register_assign_targets(self, assign: ast.IbAssign) -> None:
        """如果 RHS 是 IbBehaviorExpr（含 IbCastExpr 包装），把 LHS 的所有
        Symbol 标记为依赖该 IbBehaviorExpr。

        C14：若任一目标 Symbol UID 在 ``cell_captured_symbols`` 中（即该变量被
        至少一个 lambda 捕获为共享 cell），则把 behavior expr 标记为
        ``dispatch_eligible=False``。IbCell 只能持有合法 IbObject，LLMFuture
        占位符不允许写入 cell，因此必须退回同步路径。"""
        rhs = assign.value
        # 递归剥离 IbCastExpr / IbTypeAnnotatedExpr
        while isinstance(rhs, (ast.IbCastExpr, ast.IbTypeAnnotatedExpr)):
            rhs = rhs.value
        if not isinstance(rhs, ast.IbBehaviorExpr):
            return

        for tgt in assign.targets:
            for sym in self._iter_target_symbols(tgt):
                if sym is not None:
                    self._symbol_to_behavior_def[id(sym)] = rhs
                    # cell 捕获变量 → 禁止 dispatch-before-use
                    if (
                        sym.uid
                        and sym.uid in self.side_table.cell_captured_symbols
                    ):
                        rhs.dispatch_eligible = False

    def _iter_target_symbols(self, target: Any):
        """从赋值目标 AST 节点抽取所有 Symbol。"""
        sym = self.side_table.get_symbol(target)
        if sym is not None:
            yield sym
            return
        # IbTypeAnnotatedExpr → 内部值
        if isinstance(target, ast.IbTypeAnnotatedExpr):
            yield from self._iter_target_symbols(target.value)
            return
        # IbTuple → 元组解包
        if isinstance(target, ast.IbTuple):
            for elt in target.elts:
                yield from self._iter_target_symbols(elt)

    def _analyze_behavior_expr(self, node: ast.IbBehaviorExpr) -> None:
        """扫描 segments 中的 IbExpr 段，追溯其变量来源。"""
        deps: List[ast.IbBehaviorExpr] = []
        seen: Set[int] = set()
        for seg in node.segments:
            if not isinstance(seg, ast.IbASTNode):
                continue
            for sub in self._iter_descendants(seg, include_self=True):
                if not isinstance(sub, ast.IbName):
                    continue
                sym = self.side_table.get_symbol(sub)
                if sym is None:
                    continue
                upstream = self._symbol_to_behavior_def.get(id(sym))
                if upstream is None:
                    continue
                if id(upstream) in seen:
                    continue
                seen.add(id(upstream))
                deps.append(upstream)
            # 子表达式内部如果含 IbBehaviorExpr 也应继续遍历（嵌套行为表达式）
            for sub in self._iter_descendants(seg, include_self=True):
                if isinstance(sub, ast.IbBehaviorExpr) and sub is not node:
                    self._analyze_behavior_expr(sub)
        node.llm_deps = deps

    def _resolve_dispatch_eligible(self, root: ast.IbASTNode) -> None:
        """设置 ``dispatch_eligible``。

        规则（保守、O(n)）：
        * 节点 N 的 dispatch_eligible == True 当且仅当 N 不参与任何依赖环。
        * 在静态语义层，IbBehaviorExpr 是不可变 AST 节点；llm_deps 形成 DAG
          的可能性远高于环，环出现仅在病态场景（互递归 lambda 中嵌套同一
          behavior 表达式）。
        采用基于 SCC（Tarjan）的简单实现，对环参与节点把 dispatch_eligible
        置为 False。
        """
        all_behaviors: List[ast.IbBehaviorExpr] = []
        for sub in self._iter_descendants(root, include_self=True):
            if isinstance(sub, ast.IbBehaviorExpr):
                all_behaviors.append(sub)
                # 默认值已是 True；分析不修改即视作可调度
                if not hasattr(sub, "dispatch_eligible"):
                    sub.dispatch_eligible = True

        # 建图：node → list[node]（llm_deps）
        # 用 id() 作为节点键避免 dataclass eq=False 的潜在 hash 问题
        nodes_by_id: Dict[int, ast.IbBehaviorExpr] = {id(n): n for n in all_behaviors}

        # Tarjan SCC
        index_counter = [0]
        stack: List[int] = []
        on_stack: Dict[int, bool] = {}
        index: Dict[int, int] = {}
        lowlink: Dict[int, int] = {}
        in_cycle: Set[int] = set()

        def strongconnect(v_id: int) -> None:
            index[v_id] = index_counter[0]
            lowlink[v_id] = index_counter[0]
            index_counter[0] += 1
            stack.append(v_id)
            on_stack[v_id] = True

            for dep in nodes_by_id[v_id].llm_deps:
                w_id = id(dep)
                if w_id not in nodes_by_id:
                    # 跨范围依赖：忽略
                    continue
                if w_id not in index:
                    strongconnect(w_id)
                    lowlink[v_id] = min(lowlink[v_id], lowlink[w_id])
                elif on_stack.get(w_id):
                    lowlink[v_id] = min(lowlink[v_id], index[w_id])

            if lowlink[v_id] == index[v_id]:
                component: List[int] = []
                while True:
                    w_id = stack.pop()
                    on_stack[w_id] = False
                    component.append(w_id)
                    if w_id == v_id:
                        break
                # 含多于 1 个节点 → 一定是环；含 1 个节点但有自环也是环
                if len(component) > 1:
                    in_cycle.update(component)
                else:
                    only = component[0]
                    if any(id(d) == only for d in nodes_by_id[only].llm_deps):
                        in_cycle.add(only)

        for v_id in list(nodes_by_id):
            if v_id not in index:
                strongconnect(v_id)

        for v_id, node in nodes_by_id.items():
            node.dispatch_eligible = v_id not in in_cycle

    # ------------------------------------------------------------------
    # 通用工具
    # ------------------------------------------------------------------

    def _iter_children(self, node: Any):
        """yield AST 子节点（不展开 list / tuple 内非 AST 元素）。

        **不**追踪 ``IbBehaviorExpr.llm_deps`` —— 那是 M5a 自己写入的元数据，
        递归到它会造成自循环。
        """
        if not isinstance(node, ast.IbASTNode):
            return
        for _name, value in vars(node).items():
            if _name == "llm_deps":
                continue
            if isinstance(value, ast.IbASTNode):
                yield value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.IbASTNode):
                        yield item

    def _iter_descendants(self, node: Any, include_self: bool = False):
        """前序遍历所有 AST 后代节点。"""
        if include_self and isinstance(node, ast.IbASTNode):
            yield node
        for child in self._iter_children(node):
            yield child
            yield from self._iter_descendants(child, include_self=False)

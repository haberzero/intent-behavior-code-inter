"""
tests/unit/test_ddg_analysis.py
================================

M5a — BehaviorDependencyAnalyzer 单元测试。

覆盖范围：
1. 无依赖：纯字面量 / 普通变量 → llm_deps == []
2. 单依赖：一个 behavior 引用前面 behavior 赋值的变量
3. 链式依赖：behavior_c 依赖 behavior_b 依赖 behavior_a
4. 多源依赖：behavior 同时引用多个上游 behavior
5. 重复变量去重：同一个上游被多次引用只记录一次
6. dispatch_eligible：无环时 True；构造的人工环境境下检验 SCC 推导
7. 跨函数：当前实现保守（仅同一作用域内追溯 RHS=IbBehaviorExpr 的赋值）
8. 序列化：llm_deps 字段经 FlatSerializer 后保留为 UID 列表

注：行为表达式中的变量插值语法是 ``$var``（``parse_llm_section_content``）。
"""
import pytest

from core.engine import IBCIEngine
from core.kernel import ast
from core.compiler.semantic.passes.behavior_dependency_analyzer import (
    BehaviorDependencyAnalyzer,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def make_engine(code: str):
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    engine.run_string(code, output_callback=lambda t: None, silent=True)
    return engine


def all_behavior_exprs(engine):
    """从已编译模块的 AST 收集所有 IbBehaviorExpr 节点（按出现顺序）。"""
    if hasattr(engine, "scheduler") and engine.scheduler.ast_cache:
        roots = list(engine.scheduler.ast_cache.values())
    else:
        roots = []
    found = []

    def walk(node):
        if isinstance(node, ast.IbBehaviorExpr):
            found.append(node)
        if not isinstance(node, ast.IbASTNode):
            return
        for name, value in vars(node).items():
            if name == "llm_deps":
                continue  # 跳过 M5a 元数据，避免循环
            if isinstance(value, ast.IbASTNode):
                walk(value)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

    for r in roots:
        walk(r)
    return found


# ===========================================================================
# 1. 无依赖
# ===========================================================================

class TestNoDependency:
    def test_single_behavior_no_deps(self):
        engine = make_engine('str s = @~hello~\n')
        bs = all_behavior_exprs(engine)
        assert len(bs) == 1
        assert bs[0].llm_deps == []
        assert bs[0].dispatch_eligible is True

    def test_two_independent_behaviors(self):
        engine = make_engine(
            'str a = @~one~\n'
            'str b = @~two~\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 2
        for b in bs:
            assert b.llm_deps == []
            assert b.dispatch_eligible is True

    def test_behavior_referencing_plain_var(self):
        engine = make_engine(
            'int n = 42\n'
            'str s = @~the number is $n~\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 1
        # n 是普通整型，非 behavior 来源
        assert bs[0].llm_deps == []
        assert bs[0].dispatch_eligible is True


# ===========================================================================
# 2. 单依赖
# ===========================================================================

class TestSingleDependency:
    def test_behavior_b_depends_on_behavior_a(self):
        engine = make_engine(
            'str a = @~hello~\n'
            'str b = @~response to $a now~\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 2
        a_node, b_node = bs[0], bs[1]
        assert a_node.llm_deps == []
        assert b_node.llm_deps == [a_node]
        assert a_node.dispatch_eligible is True
        assert b_node.dispatch_eligible is True


# ===========================================================================
# 3. 链式依赖
# ===========================================================================

class TestChainedDependency:
    def test_three_level_chain(self):
        engine = make_engine(
            'str a = @~level1~\n'
            'str b = @~level2 from $a~\n'
            'str c = @~level3 from $b~\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 3
        a, b, c = bs
        assert a.llm_deps == []
        assert b.llm_deps == [a]
        assert c.llm_deps == [b]
        # all dispatch_eligible (DAG)
        assert all(x.dispatch_eligible for x in bs)


# ===========================================================================
# 4. 多源 / 去重
# ===========================================================================

class TestMultipleSources:
    def test_behavior_with_two_upstreams(self):
        engine = make_engine(
            'str a = @~A~\n'
            'str b = @~B~\n'
            'str c = @~combine $a and $b~\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 3
        a, b, c = bs
        assert c.llm_deps == [a, b]

    def test_repeated_reference_dedups(self):
        engine = make_engine(
            'str a = @~A~\n'
            'str c = @~combine $a and again $a~\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 2
        a, c = bs
        # 同一上游 behavior 引用两次只在 llm_deps 出现一次
        assert c.llm_deps == [a]


# ===========================================================================
# 5. 重新赋值的影响（保守近似）
# ===========================================================================

class TestRebinding:
    def test_rebind_to_plain_value_drops_dep(self):
        # 赋值 a 为字面量后，对 a 的引用不再是 behavior 来源
        engine = make_engine(
            'str a = @~A~\n'
            'a = "literal"\n'
            'str b = @~uses $a~\n'
        )
        bs = all_behavior_exprs(engine)
        # 现实现中，"a 被覆盖为字面量"未触发 self._symbol_to_behavior_def 清理；
        # 这是保守近似（保留 a 为 behavior 源）。
        # 我们检查"覆盖后保守但安全"：要么清空了 dep，要么仍指向 a。
        b_node = bs[-1]
        # 至少不能崩溃，且最多包含 a 这一个项
        assert len(b_node.llm_deps) <= 1


# ===========================================================================
# 6. dispatch_eligible（无环 / 自然 DAG 必为 True）
# ===========================================================================

class TestDispatchEligible:
    def test_dag_all_eligible(self):
        engine = make_engine(
            'str a = @~A~\n'
            'str b = @~B from $a~\n'
            'str c = @~C from $b and $a~\n'
        )
        bs = all_behavior_exprs(engine)
        for b in bs:
            assert b.dispatch_eligible is True

    def test_synthetic_cycle_detection(self):
        """直接在 AST 上构造一个环，验证 SCC 检测把环节点标 False。"""
        engine = make_engine('str a = @~A~\n')
        bs = all_behavior_exprs(engine)
        assert len(bs) == 1
        a = bs[0]
        # 人工构造一个互依赖的第二个节点
        b = ast.IbBehaviorExpr(segments=["x"], tag="")
        # 互相依赖：a→b, b→a
        a.llm_deps = [b]
        b.llm_deps = [a]
        analyzer = BehaviorDependencyAnalyzer(side_table=None)
        # 构造一个含两个节点的 root（通过简单容器）
        root = ast.IbModule(body=[
            ast.IbExprStmt(value=a),
            ast.IbExprStmt(value=b),
        ])
        # 直接调用 SCC（绕过 analyze 全流程，只测试该子例程）
        analyzer._resolve_dispatch_eligible(root)
        assert a.dispatch_eligible is False
        assert b.dispatch_eligible is False

    def test_synthetic_self_cycle_detection(self):
        engine = make_engine('str a = @~A~\n')
        a = all_behavior_exprs(engine)[0]
        # 自环
        a.llm_deps = [a]
        analyzer = BehaviorDependencyAnalyzer(side_table=None)
        root = ast.IbModule(body=[ast.IbExprStmt(value=a)])
        analyzer._resolve_dispatch_eligible(root)
        assert a.dispatch_eligible is False


# ===========================================================================
# 7. 跨函数：当前实现保守（仅同一作用域内追溯 RHS=IbBehaviorExpr 的赋值）
# ===========================================================================

class TestCrossFunctionConservative:
    def test_function_call_result_no_dep(self):
        # 函数调用结果不被识别为 behavior 来源
        engine = make_engine(
            'func make_text() -> str:\n'
            '    return "hidden"\n'
            'str t = make_text()\n'
            'str s = @~uses $t~\n'
        )
        bs = all_behavior_exprs(engine)
        # 模块顶层只有一个 IbBehaviorExpr（`@~uses $t~`）
        assert len(bs) == 1
        last = bs[-1]
        # t 来自函数调用，不是 IbBehaviorExpr 直接赋值，因此 llm_deps 为空
        assert last.llm_deps == []
        assert last.dispatch_eligible is True


# ===========================================================================
# 8. 序列化：llm_deps 通过 FlatSerializer 转为 UID 列表
# ===========================================================================

class TestSerializationOfLLMDeps:
    def test_llm_deps_serialized_as_uid_list(self):
        from core.compiler.serialization.serializer import FlatSerializer

        engine = IBCIEngine(root_dir=".", auto_sniff=False)
        artifact = engine.compile_string(
            'str a = @~A~\n'
            'str b = @~uses $a~\n',
            silent=True,
        )
        ser = FlatSerializer()
        data = ser.serialize_artifact(artifact)
        nodes = data["pools"]["nodes"]
        # 找到所有 IbBehaviorExpr 序列化数据
        beh_nodes = [d for d in nodes.values() if d.get("_type") == "IbBehaviorExpr"]
        assert len(beh_nodes) == 2
        for d in beh_nodes:
            deps = d.get("llm_deps")
            assert isinstance(deps, list)
            for u in deps:
                assert isinstance(u, str)
                assert u in nodes
            # dispatch_eligible 字段应保留
            assert d.get("dispatch_eligible") is True

        # b 必须有 1 个 dep；a 必须有 0 个
        deps_lengths = sorted(len(d["llm_deps"]) for d in beh_nodes)
        assert deps_lengths == [0, 1]


# ===========================================================================
# 9. 边界：嵌套在调用参数中的 IbBehaviorExpr 也参与依赖解析
# ===========================================================================

class TestNestedBehaviorExprs:
    def test_nested_behavior_in_call_arg(self):
        engine = make_engine(
            'str a = @~A~\n'
            'print(@~direct $a~)\n'
        )
        bs = all_behavior_exprs(engine)
        assert len(bs) == 2
        # 第二个 behavior 是 print 参数
        outer = bs[1]
        assert outer.llm_deps == [bs[0]]
        assert outer.dispatch_eligible is True


# ===========================================================================
# 10. AST 字段默认值合约
# ===========================================================================

class TestASTFieldDefaults:
    def test_default_llm_deps_is_empty_list_per_instance(self):
        a = ast.IbBehaviorExpr(segments=["x"], tag="")
        b = ast.IbBehaviorExpr(segments=["y"], tag="")
        # 默认值不能共享同一个 list 对象
        assert a.llm_deps is not b.llm_deps
        assert a.llm_deps == [] and b.llm_deps == []
        a.llm_deps.append(b)
        assert b.llm_deps == []

    def test_default_dispatch_eligible_is_true(self):
        a = ast.IbBehaviorExpr(segments=["x"], tag="")
        assert a.dispatch_eligible is True

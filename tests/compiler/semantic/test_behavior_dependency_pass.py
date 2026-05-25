"""
Regression tests for BehaviorDependencyPass (Pass 5).

Covers fix: isinstance(node.value, IbBehaviorExpr) instead of isinstance(node, IbBehaviorExpr)
inside the IbAssign branch.
"""

import pytest
from core.kernel import ast
from core.compiler.semantic.passes.behavior_dependency_pass import BehaviorDependencyPass
from .conftest import make_context


def test_behavior_dep_assigns_behavior_expr_to_symbol(spec_registry):
    """Behavior expr assigned to variable should register in symbol_to_behavior map."""
    # str result = @~ 做某事 ~
    behavior = ast.IbBehaviorExpr(segments=["做某事"])
    name_target = ast.IbName(id="result", ctx="store")
    assign = ast.IbAssign(targets=[name_target], value=behavior)
    module = ast.IbModule(body=[assign])

    context = make_context(module, spec_registry)
    result = BehaviorDependencyPass().run(context)

    assert result.success
    # The behavior node should have llm_deps and dispatch_eligible set
    assert hasattr(behavior, 'llm_deps')
    assert behavior.dispatch_eligible is True


def test_behavior_dep_non_behavior_assign_no_crash(spec_registry):
    """Non-behavior assignment should not crash (regression for the isinstance bug)."""
    # int x = 42
    const = ast.IbConstant(value=42)
    name_target = ast.IbName(id="x", ctx="store")
    assign = ast.IbAssign(targets=[name_target], value=const)
    module = ast.IbModule(body=[assign])

    context = make_context(module, spec_registry)
    result = BehaviorDependencyPass().run(context)

    assert result.success
    assert len(result.diagnostics) == 0


def test_behavior_dep_dependency_tracking(spec_registry):
    """Behavior expr that references a var assigned from another behavior should track dep."""
    # str a = @~ first ~
    behavior_a = ast.IbBehaviorExpr(segments=["first"])
    assign_a = ast.IbAssign(
        targets=[ast.IbName(id="a", ctx="store")],
        value=behavior_a
    )
    # str b = @~ use $a ~
    ref_a = ast.IbName(id="a", ctx="load")
    behavior_b = ast.IbBehaviorExpr(segments=["use ", ref_a])
    assign_b = ast.IbAssign(
        targets=[ast.IbName(id="b", ctx="store")],
        value=behavior_b
    )
    module = ast.IbModule(body=[assign_a, assign_b])

    context = make_context(module, spec_registry)
    result = BehaviorDependencyPass().run(context)

    assert result.success
    # behavior_b should depend on behavior_a
    assert behavior_a in behavior_b.llm_deps

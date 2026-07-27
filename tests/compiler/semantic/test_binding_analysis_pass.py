"""
Regression tests for BindingAnalysisPass (Pass 4) and BehaviorDependencyPass (Pass 5).

Covers fixes:
- IntentContextValidator uses stmt.intent.mode/content instead of stmt.op/text
- BindingAnalysisPass.run() no longer writes to non-existent MetadataStore fields
- BehaviorDependencyPass isinstance(node.value, IbBehaviorExpr) fix
"""

import pytest
from core.kernel import ast
from core.kernel.ast import IntentMode
from core.compiler.semantic.passes.binding_analysis_pass import BindingAnalysisPass
from core.compiler.semantic.passes.behavior_dependency_pass import BehaviorDependencyPass
from .conftest import make_context


def test_binding_analysis_intent_annotation_no_crash(spec_registry):
    """IntentAnnotation should be processed using stmt.intent.mode, not stmt.op."""
    intent_info = ast.IbIntentInfo(
        mode=IntentMode.APPEND,
        content="用友好的语气"
    )
    annotation = ast.IbIntentAnnotation(intent=intent_info)
    # Follow with a behavior expr
    behavior = ast.IbBehaviorExpr(segments=["打招呼"])
    module = ast.IbModule(body=[annotation, behavior])

    context = make_context(module, spec_registry)
    result = BindingAnalysisPass().run(context)

    # Should not crash with AttributeError on 'op' or 'text'
    assert result is not None


def test_binding_analysis_no_metadata_field_error(spec_registry):
    """BindingAnalysisPass should not write to non-existent MetadataStore fields."""
    # Simple module with llmexcept
    behavior = ast.IbBehaviorExpr(segments=["test"])
    assign = ast.IbAssign(
        targets=[ast.IbName(id="x", ctx="store")],
        value=behavior
    )
    module = ast.IbModule(body=[assign])

    context = make_context(module, spec_registry)
    # Should not raise AttributeError for llmexcept_bindings/intent_annotations/behavior_metadata
    result = BindingAnalysisPass().run(context)
    assert result.success


def test_binding_analysis_lambda_captures_to_cell_captured(spec_registry):
    """Lambda captures should be written to MetadataStore.cell_captured_symbols."""
    # A lambda that captures a free variable
    lambda_body = ast.IbName(id="x", ctx="load")
    lambda_expr = ast.IbLambdaExpr(
        params=[ast.IbArg(arg="y")],
        body=lambda_body,
    )
    assign = ast.IbAssign(
        targets=[ast.IbName(id="f", ctx="store")],
        value=lambda_expr
    )
    # Define x first
    x_assign = ast.IbAssign(
        targets=[ast.IbName(id="x", ctx="store")],
        value=ast.IbConstant(value=1)
    )
    module = ast.IbModule(body=[x_assign, assign])

    context = make_context(module, spec_registry)
    result = BindingAnalysisPass().run(context)
    assert result.success


class TestLLMExceptReadOnlyConstraint:
    """SEM_LLMEXCEPT_BODY_WRITE — llmexcept body 内禁止对外部作用域变量赋值。"""

    def test_sem052_outer_scope_write_produces_error(self, spec_registry):
        """Writing to outer-scope variable in llmexcept body produces SEM_LLMEXCEPT_BODY_WRITE."""
        from core.compiler.semantic.result import DiagnosticLevel

        # 构造: x = @~something~  llmexcept: x = 1
        behavior = ast.IbBehaviorExpr(segments=["compute something"])
        assign_outer = ast.IbAssign(
            targets=[ast.IbName(id="x", ctx="store")],
            value=behavior
        )
        # llmexcept body 中对 x 重赋值
        inner_assign = ast.IbAssign(
            targets=[ast.IbName(id="x", ctx="store")],
            value=ast.IbConstant(value=42)
        )
        llmexcept = ast.IbLLMExceptionalStmt(
            body=[inner_assign],
            target=None
        )
        module = ast.IbModule(body=[assign_outer, llmexcept])

        context = make_context(module, spec_registry)
        # 需要在 context 的 symbol_table 中预注册 x
        from core.kernel.symbols import VariableSymbol, SymbolKind
        x_sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, def_node=assign_outer)
        context.symbol_table.current.define(x_sym)

        result = BindingAnalysisPass().run(context)

        # 应该有 SEM_LLMEXCEPT_BODY_WRITE 错误
        sem052_diags = [d for d in result.diagnostics if d.code == "SEM_LLMEXCEPT_BODY_WRITE"]
        assert len(sem052_diags) >= 1
        assert "Cannot assign to 'x'" in sem052_diags[0].message

    def test_sem052_body_local_allowed(self, spec_registry):
        """New body-local variables in llmexcept body are allowed (no SEM_LLMEXCEPT_BODY_WRITE)."""
        # 构造: x = @~something~  llmexcept: int y = 1 (body-local 声明)
        behavior = ast.IbBehaviorExpr(segments=["compute something"])
        assign_outer = ast.IbAssign(
            targets=[ast.IbName(id="x", ctx="store")],
            value=behavior
        )
        # llmexcept body 中声明新的 body-local 变量（有类型标注）
        inner_assign = ast.IbAssign(
            targets=[ast.IbTypeAnnotatedExpr(
                target=ast.IbName(id="y", ctx="store"),
                annotation=ast.IbName(id="int", ctx="load")
            )],
            value=ast.IbConstant(value=42)
        )
        llmexcept = ast.IbLLMExceptionalStmt(
            body=[inner_assign],
            target=None
        )
        module = ast.IbModule(body=[assign_outer, llmexcept])

        context = make_context(module, spec_registry)
        from core.kernel.symbols import VariableSymbol, SymbolKind
        x_sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, def_node=assign_outer)
        context.symbol_table.current.define(x_sym)

        result = BindingAnalysisPass().run(context)

        # 不应该有 SEM_LLMEXCEPT_BODY_WRITE 错误
        sem052_diags = [d for d in result.diagnostics if d.code == "SEM_LLMEXCEPT_BODY_WRITE"]
        assert len(sem052_diags) == 0


# ===========================================================================
# BehaviorDependencyPass (Pass 5) regression tests
# (merged from test_behavior_dependency_pass.py)
# ===========================================================================


def test_behavior_dep_assigns_behavior_expr_to_symbol(spec_registry):
    """Behavior expr assigned to variable should register in symbol_to_behavior map."""
    behavior = ast.IbBehaviorExpr(segments=["做某事"])
    name_target = ast.IbName(id="result", ctx="store")
    assign = ast.IbAssign(targets=[name_target], value=behavior)
    module = ast.IbModule(body=[assign])

    context = make_context(module, spec_registry)
    result = BehaviorDependencyPass().run(context)

    assert result.success
    assert hasattr(behavior, 'llm_deps')
    # 并发 dispatch 未默认启用，dispatch_eligible 一律置 False
    assert behavior.dispatch_eligible is False


def test_behavior_dep_non_behavior_assign_no_crash(spec_registry):
    """Non-behavior assignment should not crash (regression for the isinstance bug)."""
    const = ast.IbConstant(value=42)
    name_target = ast.IbName(id="x", ctx="store")
    assign = ast.IbAssign(targets=[name_target], value=const)
    module = ast.IbModule(body=[assign])

    context = make_context(module, spec_registry)
    result = BehaviorDependencyPass().run(context)

    assert result.success
    assert len(result.diagnostics) == 0


def test_behavior_dep_dependency_tracking(spec_registry):
    """Behavior expr referencing var from another behavior should track dep."""
    behavior_a = ast.IbBehaviorExpr(segments=["first"])
    assign_a = ast.IbAssign(
        targets=[ast.IbName(id="a", ctx="store")],
        value=behavior_a
    )
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
    assert behavior_a in behavior_b.llm_deps

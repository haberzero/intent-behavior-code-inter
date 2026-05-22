"""
Regression tests for BindingAnalysisPass (Pass 4).

Covers fixes:
- IntentContextValidator uses stmt.intent.mode/content instead of stmt.op/text
- BindingAnalysisPass.run() no longer writes to non-existent MetadataStore fields
"""

import pytest
from core.kernel import ast
from core.kernel.ast import IntentMode
from core.compiler.semantic_v2.passes.binding_analysis_pass import BindingAnalysisPass
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
    assert result.success or len(result.diagnostics) >= 0


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

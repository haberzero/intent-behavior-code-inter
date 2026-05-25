"""
Pipeline → CompilationResult Adapter

将 PipelineResult 转换为 scheduler 期望的 CompilationResult。
"""

from typing import Optional, Any, List

from core.kernel import ast as ibci_ast
from core.kernel.blueprint import CompilationResult

from .pipeline import PipelineResult
from .result import DiagnosticLevel


def pipeline_result_to_compilation_result(
    result: PipelineResult,
    issue_tracker: Optional[Any] = None
) -> CompilationResult:
    """将 PipelineResult 转换为 CompilationResult。"""
    context = result.context
    metadata = result.metadata

    module_ast = context.ast if isinstance(context.ast, ibci_ast.IbModule) else None
    symbol_table = context.symbol_table.current

    if issue_tracker and result.diagnostics:
        _inject_diagnostics(result.diagnostics, issue_tracker)

    return CompilationResult(
        module_ast=module_ast,
        symbol_table=symbol_table,
        node_to_symbol=metadata.node_to_symbol,
        node_to_type=metadata.node_to_type,
        node_to_loc=metadata.node_to_loc,
    )


# Keep legacy name as alias for backward compatibility within this module
pass_result_to_compilation_result = pipeline_result_to_compilation_result


def _inject_diagnostics(diagnostics: List, issue_tracker: Any) -> None:
    """将 Diagnostic 列表注入到 IssueTracker。"""
    from core.kernel.issue import Severity
    from core.base.source_atomic import Location

    for diag in diagnostics:
        loc = Location(
            line=diag.line or 0,
            column=diag.column or 0,
        )
        if diag.level == DiagnosticLevel.ERROR:
            issue_tracker.report(
                severity=Severity.ERROR,
                code=diag.code,
                message=diag.message,
                location=loc,
            )
        elif diag.level == DiagnosticLevel.WARNING:
            issue_tracker.report(
                severity=Severity.WARNING,
                code=diag.code,
                message=diag.message,
                location=loc,
            )

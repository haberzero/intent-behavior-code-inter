"""
Pipeline → CompilationResult Adapter

将 semantic pipeline 的 PassResult 转换为 scheduler 期望的 CompilationResult。

设计原则：
- 不引入任何 fallback 或兼容层——直接映射产物到 CompilationResult 接口
- MetadataStore 使用 node object 作为键
- 序列化器无需改动（FlatSerializer 已处理 object→UID 转换）
"""

from typing import Optional, Any, List

from core.kernel import ast as ibci_ast
from core.kernel.blueprint import CompilationResult
from core.kernel.symbols import SymbolTable

from .context import SemanticContext
from .result import PassResult, DiagnosticLevel


def pass_result_to_compilation_result(
    result: PassResult,
    issue_tracker: Optional[Any] = None
) -> CompilationResult:
    """
    将 pipeline 的 PassResult 转换为 CompilationResult。

    Args:
        result: pipeline 的最终输出
        issue_tracker: 诊断收集器（可选），用于将 diagnostics 注入到错误报告系统

    Returns:
        CompilationResult
    """
    context = result.context
    metadata = context.metadata

    # 提取 module AST
    module_ast = context.ast if isinstance(context.ast, ibci_ast.IbModule) else None

    # 提取 symbol table
    symbol_table = context.symbol_table.current

    # MetadataStore 中的 node_to_* 字典已经是 node object keyed
    # 与 CompilationResult 的接口完全一致
    node_to_symbol = metadata.node_to_symbol
    node_to_type = metadata.node_to_type
    node_to_loc = metadata.node_to_loc

    # 如果提供了 issue_tracker，将诊断信息注入
    if issue_tracker and result.diagnostics:
        _inject_diagnostics(result.diagnostics, issue_tracker)

    return CompilationResult(
        module_ast=module_ast,
        symbol_table=symbol_table,
        node_to_symbol=node_to_symbol,
        node_to_type=node_to_type,
        node_to_loc=node_to_loc,
    )


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

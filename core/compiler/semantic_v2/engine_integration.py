"""
semantic_v2 Engine Integration Module

This module provides integration between IBCIEngine and the semantic_v2 pipeline,
allowing the engine to optionally use V2 instead of V1 for semantic analysis.
"""

from typing import Optional
from core.kernel import ast
from core.kernel.symbols import SymbolTable
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.semantic_v2.pipeline import create_semantic_pipeline
from core.compiler.semantic_v2.context import SemanticContext
from core.compiler.semantic_v2.metadata import MetadataStore, SymbolTableContext, TypeEnvironment
from core.compiler.semantic_v2.result import DiagnosticLevel
from core.kernel.issue import Diagnostic, Severity, CompilerError
from core.kernel.blueprint import CompilationResult


def run_semantic_v2(
    ast_node: ast.IbModule,
    registry: 'KernelRegistry',
    module_name: str,
    issue_tracker: IssueTracker,
    predefined_symbols: Optional[dict] = None
) -> CompilationResult:
    """
    Run semantic_v2 pipeline on an AST node

    Args:
        ast_node: The AST module to analyze
        registry: The kernel registry
        module_name: Name of the module being analyzed
        issue_tracker: Issue tracker for reporting errors
        predefined_symbols: Optional predefined symbols to inject

    Returns:
        CompilationResult: Result with symbol table and side table data
    """
    # Create initial symbol table and inject predefined symbols
    symbol_table = SymbolTable()
    if predefined_symbols:
        for name, symbol in predefined_symbols.items():
            symbol_table.define(symbol)

    # Create semantic context
    context = SemanticContext(
        ast=ast_node,
        registry=registry,
        module_name=module_name,
        symbol_table=SymbolTableContext(symbol_table),
        type_environment=TypeEnvironment(),
        metadata=MetadataStore()
    )

    # Run pipeline
    pipeline = create_semantic_pipeline()
    result = pipeline.run(context)

    # Convert V2 diagnostics to V1 format and add to issue tracker
    for diagnostic in result.diagnostics:
        severity = _convert_diagnostic_level(diagnostic.level)
        issue_tracker.add(
            Diagnostic(
                message=diagnostic.message,
                location=None,  # TODO: Map node_uid to location if needed
                severity=severity,
                code=diagnostic.code
            )
        )

    # Create compilation result compatible with V1 interface
    compilation_result = CompilationResult(
        success=result.success,
        errors=[d for d in result.diagnostics if d.level == DiagnosticLevel.ERROR],
        warnings=[d for d in result.diagnostics if d.level == DiagnosticLevel.WARNING],
        symbol_table=result.context.symbol_table.current,
        metadata=result.metadata
    )

    return compilation_result


def _convert_diagnostic_level(level: DiagnosticLevel) -> Severity:
    """Convert semantic_v2 diagnostic level to V1 severity"""
    if level == DiagnosticLevel.ERROR:
        return Severity.ERROR
    elif level == DiagnosticLevel.WARNING:
        return Severity.WARNING
    elif level == DiagnosticLevel.INFO:
        return Severity.INFO
    else:
        return Severity.INFO


class SemanticV2Adapter:
    """
    Adapter to make semantic_v2 pipeline compatible with V1 SemanticAnalyzer interface

    This allows drop-in replacement of V1 analyzer with V2 pipeline
    """

    def __init__(self, issue_tracker: IssueTracker, debugger=None, registry=None, module_name: str = ""):
        self.issue_tracker = issue_tracker
        self.debugger = debugger
        self.registry = registry
        self.module_name = module_name
        self.symbol_table = SymbolTable()

    def analyze(self, node: ast.IbASTNode, raise_on_error: bool = True) -> CompilationResult:
        """
        Analyze AST using semantic_v2 pipeline

        Args:
            node: AST node to analyze
            raise_on_error: Whether to raise CompilerError on errors

        Returns:
            CompilationResult: Analysis result
        """
        # Run V2 pipeline
        result = run_semantic_v2(
            node,
            self.registry,
            self.module_name,
            self.issue_tracker,
            predefined_symbols={name: sym for name, sym in self.symbol_table._symbols.items()}
        )

        # Update symbol table from result
        self.symbol_table = result.symbol_table

        # Raise error if requested
        if raise_on_error and not result.success:
            diagnostics = [
                Diagnostic(
                    message=err.message,
                    location=None,
                    severity=Severity.ERROR,
                    code=err.code
                )
                for err in result.errors
            ]
            raise CompilerError(diagnostics)

        return result

"""
semantic_v2 Engine Integration Module

Direct V2 integration - outputs UID-based CompilationResult without conversion layers.
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
    Run semantic_v2 pipeline on an AST node - direct UID-based output

    Args:
        ast_node: The AST module to analyze
        registry: The kernel registry
        module_name: Name of the module being analyzed
        issue_tracker: Issue tracker for reporting errors
        predefined_symbols: Optional predefined symbols to inject

    Returns:
        CompilationResult: UID-based result, directly usable and serializable
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

    # Convert V2 diagnostics to issue tracker format
    for diagnostic in result.diagnostics:
        severity = _convert_diagnostic_level(diagnostic.level)
        issue_tracker.add(
            Diagnostic(
                message=diagnostic.message,
                location=None,
                severity=severity,
                code=diagnostic.code
            )
        )

    # Create UID-based CompilationResult - NO CONVERSION NEEDED!
    # V2 metadata is already UID-based, use it directly
    compilation_result = CompilationResult(
        module_ast=ast_node,
        symbol_table=result.context.symbol_table.current,
        node_to_symbol=dict(result.context.metadata.symbol_bindings),  # Already UID-based
        node_to_type=dict(result.context.metadata.type_bindings),  # Already UID-based
        node_is_callable_instance={},  # TODO: Add to V2 metadata if needed
        node_capture_mode={},  # TODO: Add to V2 metadata if needed
        node_to_loc={}  # TODO: Add to V2 metadata if needed
    )

    # Raise error if needed
    if not result.success:
        errors = [
            Diagnostic(
                message=err.message,
                location=None,
                severity=Severity.ERROR,
                code=err.code
            )
            for err in result.diagnostics if err.level == DiagnosticLevel.ERROR
        ]
        if errors:
            raise CompilerError(errors)

    return compilation_result


def _convert_diagnostic_level(level: DiagnosticLevel) -> Severity:
    """Convert semantic_v2 diagnostic level to Severity"""
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
    Minimal adapter for V2 semantic analyzer

    Provides the same interface as V1 SemanticAnalyzer for drop-in replacement
    """

    def __init__(self, issue_tracker: IssueTracker, debugger=None, registry=None, module_name: str = ""):
        self.issue_tracker = issue_tracker
        self.debugger = debugger
        self.registry = registry
        self.module_name = module_name
        self.symbol_table = SymbolTable()
        self.side_table = None  # Will be populated after analysis

    def analyze(self, node: ast.IbASTNode, raise_on_error: bool = True) -> CompilationResult:
        """
        Analyze AST using semantic_v2 pipeline

        Args:
            node: AST node to analyze
            raise_on_error: Whether to raise CompilerError on errors

        Returns:
            CompilationResult: UID-based analysis result
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

        # Create side_table object for compatibility (though it's now UID-based)
        self.side_table = type('SideTable', (), {
            'node_to_symbol': result.node_to_symbol,
            'node_to_type': result.node_to_type,
            'node_is_callable_instance': result.node_is_callable_instance,
            'node_capture_mode': result.node_capture_mode,
            'node_to_loc': result.node_to_loc
        })()

        return result

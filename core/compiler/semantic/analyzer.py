"""
Semantic Analyzer — 编译器调度器入口

对外接口：analyze() → CompilationResult
内部使用 4-Phase pipeline 实现。

用法:
    from core.compiler.semantic.analyzer import SemanticAnalyzer
    analyzer = SemanticAnalyzer(issue_tracker, debugger=..., registry=..., module_name=...)
    result = analyzer.analyze(ast_node)
"""

from typing import Optional, Any

from core.kernel import ast as ibci_ast
from core.kernel.blueprint import CompilationResult
from core.kernel.symbols import SymbolTable
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

from .pipeline import create_semantic_pipeline
from .context import ContextBuilder, SemanticContext
from .result import DiagnosticLevel
from .adapter import pipeline_result_to_compilation_result


class SemanticAnalyzer:
    """语义分析器 — scheduler 兼容入口。

    对外接口：
    - __init__(issue_tracker, debugger, registry, module_name)
    - analyze(node) → CompilationResult
    - symbol_table: SymbolTable（供 scheduler 注入导入符号）
    """

    def __init__(
        self,
        issue_tracker: Any,
        debugger: Optional[Any] = None,
        registry: Optional[Any] = None,
        module_name: str = "<main>",
    ):
        self.issue_tracker = issue_tracker
        self.debugger = debugger or core_debugger
        self.registry = registry
        self.module_name = module_name

        # scheduler 通过此属性注入导入符号
        self.symbol_table = SymbolTable(parent=None, name=module_name)

    def analyze(self, node: ibci_ast.IbASTNode, raise_on_error: bool = True) -> CompilationResult:
        """执行完整的语义分析，返回 CompilationResult。"""
        self.debugger.enter_scope(CoreModule.SEMANTIC, "Starting semantic analysis...")
        try:
            context = self._build_context(node)

            pipeline = create_semantic_pipeline()
            result = pipeline.run(context)

            compilation_result = pipeline_result_to_compilation_result(
                result, issue_tracker=self.issue_tracker
            )

            if raise_on_error and result.has_errors:
                self.issue_tracker.check_errors()

            self.debugger.trace(
                CoreModule.SEMANTIC, DebugLevel.BASIC,
                "Semantic analysis complete."
            )

            return compilation_result
        finally:
            self.debugger.exit_scope(CoreModule.SEMANTIC)

    def _build_context(self, node: ibci_ast.IbASTNode) -> SemanticContext:
        """构建 pipeline 的初始 SemanticContext。"""
        context = (
            ContextBuilder()
            .with_ast(node)
            .with_registry(self.registry)
            .with_module_name(self.module_name)
            .build()
        )

        # 将 scheduler 预注入的符号同步到上下文的 symbol_table
        for name, sym in self.symbol_table.symbols.items():
            existing = context.symbol_table.resolve(name)
            if not existing:
                context.symbol_table.current.define(sym)

        return context

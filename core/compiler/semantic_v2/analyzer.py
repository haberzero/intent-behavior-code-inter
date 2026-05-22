"""
Semantic Analyzer V2 — 编译器调度器入口

提供与 v1 SemanticAnalyzer 相同的外部接口（analyze() → CompilationResult），
内部使用 v2 的 7-pass pipeline 实现。

这是 v2 全量替换 v1 的入口模块。scheduler 通过本类替换原有的:
    from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer

用法:
    from core.compiler.semantic_v2.analyzer import SemanticAnalyzerV2
    analyzer = SemanticAnalyzerV2(issue_tracker, debugger=..., registry=..., module_name=...)
    # inject symbols into analyzer.symbol_table ...
    result = analyzer.analyze(ast_node)
"""

from typing import Optional, Any, Dict

from core.kernel import ast as ibci_ast
from core.kernel.blueprint import CompilationResult
from core.kernel.symbols import SymbolTable
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

from .pipeline import create_semantic_pipeline
from .context import ContextBuilder, SemanticContext
from .result import PassResult, DiagnosticLevel
from .adapter import pass_result_to_compilation_result


class SemanticAnalyzerV2:
    """
    V2 语义分析器 — scheduler 兼容入口。

    对外接口与 v1 SemanticAnalyzer 完全一致：
    - __init__(issue_tracker, debugger, registry, module_name)
    - analyze(node) → CompilationResult
    - symbol_table: SymbolTable（供 scheduler 注入导入符号）

    内部使用 7-pass pipeline:
    1. SymbolCollectionPass
    2. SymbolResolutionPass
    3. TypeResolutionPass
    4. TypeCheckingPass
    5. BindingAnalysisPass
    6. BehaviorDependencyPass
    7. IntegrityCheckPass
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

        # 与 v1 一致的公开接口：scheduler 通过此属性注入导入符号
        self.symbol_table = SymbolTable(parent=None, name=module_name)

    def analyze(self, node: ibci_ast.IbASTNode, raise_on_error: bool = True) -> CompilationResult:
        """
        执行完整的语义分析，返回 CompilationResult。

        接口与 v1 SemanticAnalyzer.analyze() 完全一致。

        Args:
            node: 待分析的 AST 根节点（通常是 IbModule）
            raise_on_error: 为 True 时在检测到错误后触发 issue_tracker 的异常路径

        Returns:
            CompilationResult: 包含 module_ast, symbol_table, node_to_symbol,
                               node_to_type, node_to_loc
        """
        self.debugger.enter_scope(CoreModule.SEMANTIC, "Starting semantic analysis (V2 pipeline)...")
        try:
            # 构建初始上下文
            context = self._build_context(node)

            # 创建并运行 pipeline
            pipeline = create_semantic_pipeline()
            result = pipeline.run(context)

            # 转换为 CompilationResult
            compilation_result = pass_result_to_compilation_result(
                result, issue_tracker=self.issue_tracker
            )

            # 如有错误且 raise_on_error，触发异常
            if raise_on_error and result.diagnostics:
                has_errors = any(
                    d.level == DiagnosticLevel.ERROR for d in result.diagnostics
                )
                if has_errors:
                    self.issue_tracker.check_errors()

            self.debugger.trace(
                CoreModule.SEMANTIC, DebugLevel.BASIC,
                "Semantic analysis (V2) complete."
            )

            return compilation_result
        finally:
            self.debugger.exit_scope(CoreModule.SEMANTIC)

    def _build_context(self, node: ibci_ast.IbASTNode) -> SemanticContext:
        """
        构建 v2 pipeline 的初始 SemanticContext。

        将 scheduler 注入到 self.symbol_table 的符号全部迁移到 v2 上下文。
        """
        context = (
            ContextBuilder()
            .with_ast(node)
            .with_registry(self.registry)
            .with_module_name(self.module_name)
            .build()
        )

        # 将 scheduler 预注入的符号（predefined + imports）同步到 v2 上下文的 symbol_table
        # v2 ContextBuilder.build() 已注入 builtin prelude；
        # 这里额外注入 scheduler 级别的符号（模块导入等）
        for name, sym in self.symbol_table.symbols.items():
            existing = context.symbol_table.resolve(name)
            if not existing:
                context.symbol_table.current.define(sym)

        return context

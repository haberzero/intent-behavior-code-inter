"""
Semantic Analyzer — 编译器调度器入口

对外接口：analyze() → CompilationResult
内部使用 4-Phase pipeline 实现。

用法:
    from core.compiler.semantic.analyzer import SemanticAnalyzer
    analyzer = SemanticAnalyzer(issue_tracker, registry=..., module_name=...)
    result = analyzer.analyze(ast_node)
"""

from typing import Optional, Any

from core.kernel import ast as ibci_ast
from core.kernel.blueprint import CompilationResult
from core.kernel.symbols import SymbolTable

from .pipeline import create_semantic_pipeline
from .context import ContextBuilder, SemanticContext
from .result import DiagnosticLevel
from .adapter import pipeline_result_to_compilation_result


class SemanticAnalyzer:
    """语义分析器 — scheduler 兼容入口。

    对外接口：
    - __init__(issue_tracker, registry, module_name)
    - analyze(node) → CompilationResult
    - symbol_table: SymbolTable（供 scheduler 注入导入符号）
    """

    def __init__(
        self,
        issue_tracker: Any,
        registry: Optional[Any] = None,
        module_name: str = "<main>",
        module_file_path: str = "",
    ):
        self.issue_tracker = issue_tracker
        self.registry = registry
        self.module_name = module_name
        self.module_file_path = module_file_path
        # 类身份统一：所有模块（含入口）用户类 spec 均带 module 限定
        # （module_path=模块名）——入口与导入对称，跨模块同名类彻底隔离。

        # scheduler 通过此属性注入导入符号
        self.symbol_table = SymbolTable(parent=None, name=module_name)

    def analyze(self, node: ibci_ast.IbASTNode, raise_on_error: bool = True) -> CompilationResult:
        """执行完整的语义分析，返回 CompilationResult。"""
        # 设置当前编译模块（类身份统一）：所有模块编译期间裸名解析 module 优先，
        # 使模块内对自身类的裸名引用解析到带 module 的 spec。编译结束后重置
        # （finally），避免残留污染运行期裸名解析。
        if self.registry is not None:
            set_current = getattr(self.registry, "set_current_module", None)
            if set_current is not None:
                set_current(self.module_name)
        try:
            context = self._build_context(node)

            pipeline = create_semantic_pipeline()
            result = pipeline.run(context)

            compilation_result = pipeline_result_to_compilation_result(
                result, issue_tracker=self.issue_tracker
            )

            if raise_on_error and result.has_errors:
                self.issue_tracker.check_errors()

            return compilation_result
        finally:
            # 重置当前模块（编译期上下文结束；运行期裸名解析不受残留影响）。
            if self.registry is not None:
                set_current = getattr(self.registry, "set_current_module", None)
                if set_current is not None:
                    set_current(None)

    def _build_context(self, node: ibci_ast.IbASTNode) -> SemanticContext:
        """构建 pipeline 的初始 SemanticContext。"""
        context = (
            ContextBuilder()
            .with_ast(node)
            .with_registry(self.registry)
            .with_module_name(self.module_name)
            .with_module_file_path(self.module_file_path)
            .build()
        )

        # 将 scheduler 预注入的符号同步到上下文的 symbol_table
        for name, sym in self.symbol_table.symbols.items():
            existing = context.symbol_table.resolve(name)
            if not existing:
                context.symbol_table.current.define(sym)

        return context

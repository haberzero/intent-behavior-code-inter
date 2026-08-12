"""
Semantic Analyzer — IBCI 语义分析系统

Architecture
------------
- 4-Phase Pipeline: 四阶段顺序执行（每阶段内部组合原子 Pass）
- Node-Object-Keyed Metadata: 使用 Python 对象身份作为字典键，与序列化器对齐
- Errors as Data: 诊断信息作为数据收集，不中断分析流程
- Scheduler 兼容: 通过 SemanticAnalyzer.analyze() 产出 CompilationResult

Phase Pipeline
--------------
1. SymbolPhase    — 符号收集 + 符号解析
2. TypePhase      — 类型标注解析 + 类型检查/推断
3. BindingPhase   — llmexcept 绑定 + intent 验证 + lambda 捕获 + 行为依赖分析
4. IntegrityPhase — 完整性校验

Usage
-----
    from core.compiler.semantic.analyzer import SemanticAnalyzer
    analyzer = SemanticAnalyzer(tracker, registry=registry, module_name='main')
    result = analyzer.analyze(ast_node)  # → CompilationResult
"""

from .context import SemanticContext, ContextBuilder
from .result import PassResult, PassOutput, Diagnostic, DiagnosticLevel
from .pipeline import SemanticPipeline, PipelineResult, create_semantic_pipeline
from .analyzer import SemanticAnalyzer

__all__ = [
    'SemanticContext',
    'ContextBuilder',
    'PassResult',
    'PassOutput',
    'Diagnostic',
    'DiagnosticLevel',
    'SemanticPipeline',
    'PipelineResult',
    'create_semantic_pipeline',
    'SemanticAnalyzer',
]

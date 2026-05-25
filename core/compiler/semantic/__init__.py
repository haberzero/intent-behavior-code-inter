"""
Semantic Analyzer — IBCI 语义分析系统

Architecture
------------
- Pipeline-Filter: 7 个独立 Pass 顺序执行
- Node-Object-Keyed Metadata: 使用 Python 对象身份作为字典键，与序列化器对齐
- Errors as Data: 诊断信息作为数据收集，不中断分析流程
- Scheduler 兼容: 通过 SemanticAnalyzer.analyze() 产出 CompilationResult

Pass Pipeline
-------------
1. SymbolCollectionPass — 收集符号定义
2. SymbolResolutionPass — 解析符号引用
3. TypeResolutionPass   — 解析类型标注
4. TypeCheckingPass     — 类型检查与推断
5. BindingAnalysisPass  — llmexcept 绑定 + intent 验证 + lambda 捕获
6. BehaviorDependencyPass — Behavior 表达式依赖图
7. IntegrityCheckPass   — 完整性校验

Usage
-----
    from core.compiler.semantic.analyzer import SemanticAnalyzer
    analyzer = SemanticAnalyzer(tracker, registry=registry, module_name='main')
    result = analyzer.analyze(ast_node)  # → CompilationResult
"""

from .context import SemanticContext, ContextBuilder
from .result import PassResult, Diagnostic, DiagnosticLevel
from .pipeline import SemanticPipeline, create_semantic_pipeline
from .analyzer import SemanticAnalyzer

__all__ = [
    'SemanticContext',
    'ContextBuilder',
    'PassResult',
    'Diagnostic',
    'DiagnosticLevel',
    'SemanticPipeline',
    'create_semantic_pipeline',
    'SemanticAnalyzer',
]

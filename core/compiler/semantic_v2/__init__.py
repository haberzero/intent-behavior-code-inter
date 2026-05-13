"""
Semantic Analyzer V2 - Radical Decoupled Refactoring

This is a complete reimplementation of the semantic analysis system using
a clean pipeline-filter architecture. It runs in parallel with the existing
semantic analyzer to enable comparison and validation.

Architecture
------------
- Pipeline-Filter: Each analysis pass is independent and composable
- Immutable Data Flow: Context is immutable, passes return new contexts
- Errors as Data: All errors are collected, analysis continues when possible
- UID-based Metadata: Metadata keyed by node UID, not Python object identity
- Observable: Rich diagnostics and tracing throughout

Design Goals
------------
1. Identify limitations and hidden issues in the current design
2. Enable better testability (each pass can be tested independently)
3. Support extensibility (easy to add new analysis passes)
4. Improve maintainability (clear separation of concerns)
5. Enable optimization (immutable design supports parallelization)

Comparison with Semantic V1
---------------------------
| Aspect | V1 (Current) | V2 (New) |
|--------|--------------|----------|
| Architecture | God Class + Visitor | Pipeline + Visitor |
| State Management | Mutable instance vars | Immutable context |
| Error Handling | Exceptions + partial results | Result type, all errors collected |
| Metadata Storage | Object-id based side tables | UID-based metadata store |
| Pass Coordination | Monolithic analyze() | Explicit pipeline |
| Testability | Hard (tightly coupled) | Easy (independent passes) |
| Extensibility | Hard (modify one large file) | Easy (add new pass) |
"""

from .context import SemanticContext, ContextBuilder
from .result import PassResult, Diagnostic, DiagnosticLevel
from .pipeline import SemanticPipeline, create_semantic_pipeline

__all__ = [
    'SemanticContext',
    'ContextBuilder',
    'PassResult',
    'Diagnostic',
    'DiagnosticLevel',
    'SemanticPipeline',
    'create_semantic_pipeline',
]

"""
Semantic Analysis Context

The context is an immutable container for all state needed during semantic
analysis. Passes return new contexts rather than mutating state.

Key insight from V1 limitations:
- V1 uses 13+ mutable instance variables, leading to hard-to-track state
- V2 uses immutable context, making data flow explicit
- Enables parallel analysis and easier debugging
"""

from dataclasses import dataclass, replace, field
from typing import Optional, Any, Dict
from core.kernel import ast as ibci_ast


@dataclass(frozen=True)
class SemanticContext:
    """
    Immutable semantic analysis context.

    Design principle: All analysis state is explicit and immutable.
    To "modify" context, create a new one with desired changes.

    Comparison with V1:
    | V1 State Variable | V2 Location | Notes |
    |-------------------|-------------|-------|
    | self.symbol_table | context.symbol_table | Now explicit in context |
    | self.current_return_type | context.function_context.return_type | Nested context |
    | self.current_class | context.class_context.class_def | Nested context |
    | self.in_behavior_expr | context.flags['in_behavior_expr'] | Flag dictionary |
    | self._auto_return_types | context.type_inference_state | Separate state object |
    | self.side_table | context.metadata | Unified metadata store |
    """
    # Core references (never change during analysis)
    ast: ibci_ast.IbASTNode  # Root AST node being analyzed
    registry: Any  # Type registry (from core.kernel.spec)
    module_name: str

    # Mutable analysis state (passed through pipeline)
    symbol_table: 'SymbolTableContext'  # Current symbol table
    type_environment: 'TypeEnvironment'  # Type bindings
    metadata: 'MetadataStore'  # UID-based metadata

    # Context stack for nested structures
    function_context: Optional['FunctionContext'] = None
    class_context: Optional['ClassContext'] = None
    loop_context: Optional['LoopContext'] = None

    # Analysis flags (using dict for extensibility)
    flags: Dict[str, bool] = field(default_factory=dict)

    # Parent context (for nested scopes)
    parent_context: Optional['SemanticContext'] = None

    def with_symbol_table(self, new_table: 'SymbolTableContext') -> 'SemanticContext':
        """Create new context with updated symbol table"""
        return replace(self, symbol_table=new_table)

    def with_type_environment(self, new_env: 'TypeEnvironment') -> 'SemanticContext':
        """Create new context with updated type environment"""
        return replace(self, type_environment=new_env)

    def with_metadata(self, new_metadata: 'MetadataStore') -> 'SemanticContext':
        """Create new context with updated metadata"""
        return replace(self, metadata=new_metadata)

    def with_function_context(self, func_ctx: Optional['FunctionContext']) -> 'SemanticContext':
        """Create new context entering/exiting a function"""
        return replace(self, function_context=func_ctx)

    def with_class_context(self, class_ctx: Optional['ClassContext']) -> 'SemanticContext':
        """Create new context entering/exiting a class"""
        return replace(self, class_context=class_ctx)

    def with_loop_context(self, loop_ctx: Optional['LoopContext']) -> 'SemanticContext':
        """Create new context entering/exiting a loop"""
        return replace(self, loop_context=loop_ctx)

    def with_flag(self, flag_name: str, value: bool) -> 'SemanticContext':
        """Create new context with updated flag"""
        new_flags = {**self.flags, flag_name: value}
        return replace(self, flags=new_flags)

    def get_flag(self, flag_name: str, default: bool = False) -> bool:
        """Get a flag value"""
        return self.flags.get(flag_name, default)

    def enter_scope(self, scope_name: str) -> 'SemanticContext':
        """Create new context with nested scope"""
        new_table = self.symbol_table.push_scope(scope_name)
        return self.with_symbol_table(new_table).replace_context(parent_context=self)

    def exit_scope(self) -> 'SemanticContext':
        """Return to parent context"""
        if self.parent_context:
            # Merge metadata from child scope back to parent
            merged_metadata = self.parent_context.metadata.merge(self.metadata)
            return self.parent_context.with_metadata(merged_metadata)
        return self

    def replace_context(self, **kwargs) -> 'SemanticContext':
        """Generic context replacement (use with caution)"""
        return replace(self, **kwargs)


@dataclass(frozen=True)
class FunctionContext:
    """Context for function analysis"""
    function_name: str
    return_type: Any  # IbSpec - expected return type
    is_llm_function: bool = False
    is_method: bool = False
    auto_return_types: list = field(default_factory=list)  # For `-> auto` inference


@dataclass(frozen=True)
class ClassContext:
    """Context for class analysis"""
    class_name: str
    class_def: Any  # TypeDef
    parent_class: Optional[Any] = None  # TypeDef


@dataclass(frozen=True)
class LoopContext:
    """Context for loop analysis (for break/continue validation)"""
    loop_type: str  # 'for', 'while'
    has_llmexcept: bool = False


class ContextBuilder:
    """
    Builder for creating initial semantic contexts.

    Design pattern: Builder pattern for complex object construction.
    """

    def __init__(self):
        self.ast: Optional[ibci_ast.IbASTNode] = None
        self.registry: Optional[Any] = None
        self.module_name: str = "<unknown>"

    def with_ast(self, ast: ibci_ast.IbASTNode) -> 'ContextBuilder':
        self.ast = ast
        return self

    def with_registry(self, registry: Any) -> 'ContextBuilder':
        self.registry = registry
        return self

    def with_module_name(self, module_name: str) -> 'ContextBuilder':
        self.module_name = module_name
        return self

    def build(self) -> SemanticContext:
        """Build the initial semantic context"""
        if not self.ast:
            raise ValueError("AST is required")
        if not self.registry:
            raise ValueError("Registry is required")

        # Import here to avoid circular dependency
        from .metadata.symbol_table import SymbolTableContext
        from .metadata.type_environment import TypeEnvironment
        from .metadata.metadata_store import MetadataStore

        # Initialize empty state
        symbol_table = SymbolTableContext.create_root(self.module_name)
        type_environment = TypeEnvironment.create_empty()
        metadata = MetadataStore.create_empty()

        return SemanticContext(
            ast=self.ast,
            registry=self.registry,
            module_name=self.module_name,
            symbol_table=symbol_table,
            type_environment=type_environment,
            metadata=metadata,
        )

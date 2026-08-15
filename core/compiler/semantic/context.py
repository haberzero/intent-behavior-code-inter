"""
Semantic Analysis Context

Immutable container for all state needed during semantic analysis.
Passes receive context as read-only input; bindings are returned via PassOutput.
"""

from dataclasses import dataclass, replace, field
from typing import Optional, Any, Dict
from core.kernel import ast as ibci_ast
from core.kernel.symbols import VariableSymbol, FunctionSymbol, TypeSymbol, SymbolKind
from core.base.enums import Provenance, Visibility
from core.base.uid import intrinsic_uid
from core.compiler.semantic.metadata.symbol_table import SymbolTableContext
from core.compiler.semantic.metadata.type_environment import TypeInferenceState


@dataclass(frozen=True)
class SemanticContext:
    """Immutable semantic analysis context.

    Carries references needed by passes (AST, registry, symbol_table).
    Bindings flow out through PassOutput. Accumulated bindings from prior
    phases are available via `prior_bindings` for cross-phase queries.
    """
    ast: ibci_ast.IbASTNode
    registry: Any
    module_name: str
    symbol_table: 'SymbolTableContext'
    type_environment: 'TypeInferenceState'

    # Accumulated bindings from prior phases (read-only for current phase)
    prior_symbol_bindings: Dict[Any, Any] = field(default_factory=dict)
    prior_type_bindings: Dict[Any, Any] = field(default_factory=dict)

    # Nested structure context
    function_context: Optional['FunctionContext'] = None
    class_context: Optional['ClassContext'] = None
    loop_context: Optional['LoopContext'] = None

    flags: Dict[str, bool] = field(default_factory=dict)

    def with_symbol_table(self, new_table: 'SymbolTableContext') -> 'SemanticContext':
        return replace(self, symbol_table=new_table)

    def with_type_environment(self, new_env: 'TypeInferenceState') -> 'SemanticContext':
        return replace(self, type_environment=new_env)

    def with_function_context(self, func_ctx: Optional['FunctionContext']) -> 'SemanticContext':
        return replace(self, function_context=func_ctx)

    def with_class_context(self, class_ctx: Optional['ClassContext']) -> 'SemanticContext':
        return replace(self, class_context=class_ctx)

    def with_loop_context(self, loop_ctx: Optional['LoopContext']) -> 'SemanticContext':
        return replace(self, loop_context=loop_ctx)

    def with_flag(self, flag_name: str, value: bool) -> 'SemanticContext':
        new_flags = {**self.flags, flag_name: value}
        return replace(self, flags=new_flags)

    def get_flag(self, flag_name: str, default: bool = False) -> bool:
        return self.flags.get(flag_name, default)


@dataclass(frozen=True)
class FunctionContext:
    """Context for function analysis"""
    function_name: str
    return_type: Any
    is_method: bool = False
    auto_return_types: list = field(default_factory=list)


@dataclass(frozen=True)
class ClassContext:
    """Context for class analysis"""
    class_name: str
    class_def: Any
    parent_class: Optional[Any] = None


@dataclass(frozen=True)
class LoopContext:
    """Context for loop analysis"""
    loop_type: str
    has_llmexcept: bool = False


class ContextBuilder:
    """Builder for creating initial semantic contexts."""

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
        """Build the initial semantic context."""
        if not self.ast:
            raise ValueError("AST is required")
        if not self.registry:
            raise ValueError("Registry is required")

        # Local import to avoid circular: context → passes → base_pass → context
        from core.compiler.semantic.passes.prelude import Prelude

        symbol_table = SymbolTableContext.create_root(self.module_name)
        type_environment = TypeInferenceState.create_empty()

        # Inject prelude symbols
        prelude = Prelude(registry=self.registry)
        for name, spec in prelude.get_types().items():
            if getattr(spec, 'visibility', Visibility.PRELUDE_VISIBLE) != Visibility.PRELUDE_VISIBLE:
                continue
            sym = TypeSymbol(name=name, kind=SymbolKind.CLASS, spec=spec, uid=intrinsic_uid(name), provenance=Provenance.KERNEL_NATIVE)
            symbol_table.current.define(sym)
        for name, spec in prelude.get_functions().items():
            sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, spec=spec, uid=intrinsic_uid(name), provenance=Provenance.KERNEL_NATIVE)
            symbol_table.current.define(sym)
        for name, spec in prelude.get_modules().items():
            sym = VariableSymbol(name=name, kind=SymbolKind.MODULE, spec=spec, uid=intrinsic_uid(name), provenance=Provenance.KERNEL_NATIVE)
            symbol_table.current.define(sym)
        for name, spec in prelude.get_variables().items():
            sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=spec, uid=intrinsic_uid(name), is_const=True, provenance=Provenance.KERNEL_NATIVE)
            symbol_table.current.define(sym)

        return SemanticContext(
            ast=self.ast,
            registry=self.registry,
            module_name=self.module_name,
            symbol_table=symbol_table,
            type_environment=type_environment,
            flags={},
        )

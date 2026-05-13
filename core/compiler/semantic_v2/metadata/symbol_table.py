"""
Symbol Table Context

Redesigned symbol table with better immutability and scope management.

Key insights from V1:
- V1 mixes SymbolTable (from kernel.symbols) with analyzer state
- V2 wraps SymbolTable in an immutable context
- Provides clearer scope stack semantics
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from core.kernel.symbols import SymbolTable, Symbol


@dataclass(frozen=True)
class SymbolTableContext:
    """
    Immutable wrapper around SymbolTable with explicit scope stack.

    Design principle: Symbol tables form a stack, each mutation creates
    a new context with updated stack.

    Comparison with V1:
    - V1: self.symbol_table is mutated directly
    - V2: SymbolTableContext is immutable, push/pop create new contexts
    """
    current: SymbolTable
    scope_stack: tuple = field(default_factory=tuple)  # Stack of scope names
    module_name: str = "<unknown>"

    @classmethod
    def create_root(cls, module_name: str) -> 'SymbolTableContext':
        """Create root symbol table context"""
        root_table = SymbolTable(parent=None, name=module_name)
        return cls(current=root_table, scope_stack=(), module_name=module_name)

    def push_scope(self, scope_name: str) -> 'SymbolTableContext':
        """
        Push a new scope (returns new context).

        Creates a child symbol table and updates the scope stack.
        """
        child_table = SymbolTable(parent=self.current, name=scope_name)
        new_stack = self.scope_stack + (scope_name,)
        from dataclasses import replace
        return replace(self, current=child_table, scope_stack=new_stack)

    def pop_scope(self) -> 'SymbolTableContext':
        """
        Pop current scope (returns new context).

        Returns to parent symbol table and pops scope stack.
        """
        if not self.current.parent:
            raise ValueError("Cannot pop root scope")
        new_stack = self.scope_stack[:-1] if self.scope_stack else ()
        from dataclasses import replace
        return replace(self, current=self.current.parent, scope_stack=new_stack)

    def define(self, symbol: Symbol) -> 'SymbolTableContext':
        """
        Define a symbol in current scope (returns new context).

        Note: This mutates the underlying SymbolTable (V1 behavior preserved).
        For true immutability, would need to copy the entire table tree.

        TODO: Consider implementing copy-on-write for full immutability.
        """
        self.current.define(symbol)
        # Return self since SymbolTable is mutated in place
        # This is a pragmatic compromise for V1 compatibility
        return self

    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol by name (walks up scope chain)"""
        return self.current.resolve(name)

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol only in current scope"""
        return self.current.lookup(name)

    def get_scope_depth(self) -> int:
        """Get current scope depth"""
        return len(self.scope_stack)

    def get_scope_path(self) -> str:
        """Get full scope path (e.g., 'module::Class::method')"""
        return "::".join(self.scope_stack) if self.scope_stack else self.module_name

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for diagnostics"""
        return {
            'module_name': self.module_name,
            'scope_depth': self.get_scope_depth(),
            'scope_path': self.get_scope_path(),
            'symbols_in_scope': len(self.current.symbols) if hasattr(self.current, 'symbols') else 0
        }

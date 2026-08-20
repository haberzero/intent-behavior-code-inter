"""
Symbol Table Context

Immutable wrapper around SymbolTable with explicit scope stack.
"""

from dataclasses import dataclass, field, replace
from typing import Optional, Dict, List, Any
from core.kernel.symbols import SymbolTable, Symbol


@dataclass(frozen=True)
class SymbolTableContext:
    """
    Immutable wrapper around SymbolTable with explicit scope stack.

    Design principle: Symbol tables form a stack, each mutation creates
    a new context with updated stack.
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
        return replace(self, current=child_table, scope_stack=new_stack)

    def pop_scope(self) -> 'SymbolTableContext':
        """
        Pop current scope (returns new context).

        Returns to parent symbol table and pops scope stack.
        """
        if not self.current.parent:
            raise ValueError("Cannot pop root scope")
        new_stack = self.scope_stack[:-1] if self.scope_stack else ()
        return replace(self, current=self.current.parent, scope_stack=new_stack)

    def define(self, symbol: Symbol) -> 'SymbolTableContext':
        """
        Define a symbol in current scope (returns new context).

        Note: This mutates the underlying SymbolTable for pragmatic reasons.
        """
        self.current.define(symbol)
        # Return self since SymbolTable is mutated in place
        return self

    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol by name (walks up scope chain)"""
        return self.current.resolve(name)

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol only in current scope"""
        return self.current.symbols.get(name)

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
            'symbols_in_scope': len(self.current.symbols)
        }

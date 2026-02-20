from typing import Dict, List, Optional, Any
from typedef.symbol_types import Symbol, SymbolType
from typedef.builtin_symbols import BUILTIN_TYPES
from typedef.scope_types import ScopeType, ScopeNode

class ScopeManager:
    """
    Manages the current scope pointer during parsing.
    """
    def __init__(self):
        self.global_scope = ScopeNode(ScopeType.GLOBAL)
        self.current_scope = self.global_scope
        self._init_builtins()

    def _init_builtins(self):
        """Register builtin types in the global scope."""
        for name in BUILTIN_TYPES:
            self.global_scope.define(name, SymbolType.BUILTIN_TYPE)

    def enter_scope(self, scope_type: ScopeType) -> ScopeNode:
        """Create a new child scope and enter it."""
        new_scope = ScopeNode(scope_type, parent=self.current_scope)
        self.current_scope = new_scope
        return new_scope

    def exit_scope(self):
        """Return to parent scope."""
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent
        else:
            raise RuntimeError("Cannot exit global scope")

    def define(self, name: str, type: SymbolType) -> Symbol:
        return self.current_scope.define(name, type)

    def resolve(self, name: str) -> Optional[Symbol]:
        return self.current_scope.resolve(name)

    def is_type(self, name: str) -> bool:
        return self.current_scope.is_type(name)

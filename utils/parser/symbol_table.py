from typing import Dict, List, Optional, Any
from typedef.symbol_types import Symbol, SymbolType
from typedef.builtin_symbols import BUILTIN_TYPES
from enum import Enum, auto

class ScopeType(Enum):
    GLOBAL = auto()
    FUNCTION = auto()
    CLASS = auto()
    BLOCK = auto() # If needed for if/for/while blocks

class ScopeNode:
    """
    Persistent Scope Node.
    Forms a tree structure mirroring the AST scope structure.
    """
    def __init__(self, scope_type: ScopeType, parent: Optional['ScopeNode'] = None):
        self.scope_type = scope_type
        self.parent = parent
        self.children: List['ScopeNode'] = []
        self.symbols: Dict[str, Symbol] = {}
        self.depth = 0
        
        if parent:
            parent.children.append(self)
            self.depth = parent.depth + 1

    def define(self, name: str, type: SymbolType) -> Symbol:
        symbol = Symbol(name, type, scope_level=self.depth)
        self.symbols[name] = symbol
        return symbol

    def resolve(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.resolve(name)
        return None
        
    def is_type(self, name: str) -> bool:
        sym = self.resolve(name)
        return sym is not None and (sym.type == SymbolType.BUILTIN_TYPE or sym.type == SymbolType.USER_TYPE)

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

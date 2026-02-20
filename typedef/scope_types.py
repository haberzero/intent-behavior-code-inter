
from enum import Enum, auto
from typing import Dict, List, Optional
from typedef.symbol_types import Symbol, SymbolType

class ScopeType(Enum):
    GLOBAL = auto()
    FUNCTION = auto()
    CLASS = auto()
    BLOCK = auto()

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

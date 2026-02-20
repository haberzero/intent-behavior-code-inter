from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Any

class SymbolType(Enum):
    BUILTIN_TYPE = auto()  # int, str, list...
    USER_TYPE = auto()     # class MyClass (future)
    FUNCTION = auto()      # func my_func
    VARIABLE = auto()      # var x
    MODULE = auto()        # import utils

@dataclass
class Symbol:
    name: str
    type: SymbolType
    scope_level: int = 0
    type_info: Optional[Any] = None # Will hold utils.semantic.types.Type instance
    exported_scope: Optional[Any] = None # For MODULE symbols: points to the module's Global ScopeNode

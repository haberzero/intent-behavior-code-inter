from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

class SymbolType(Enum):
    BUILTIN_TYPE = auto()  # int, str, list...
    USER_TYPE = auto()     # class MyClass (future)
    FUNCTION = auto()      # func my_func
    VARIABLE = auto()      # var x

@dataclass
class Symbol:
    name: str
    type: SymbolType
    scope_level: int = 0
    # Future: type_info, declaration_node, etc.

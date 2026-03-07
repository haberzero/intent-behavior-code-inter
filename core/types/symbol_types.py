from core.compiler.semantic.symbols import Symbol, SymbolKind, StaticType

# 为了向后兼容，保留 SymbolType 枚举并映射到 SymbolKind
from enum import Enum, auto

class SymbolType(Enum):
    BUILTIN_TYPE = SymbolKind.BUILTIN_TYPE
    USER_TYPE = SymbolKind.CLASS
    FUNCTION = SymbolKind.FUNCTION
    VARIABLE = SymbolKind.VARIABLE
    MODULE = SymbolKind.MODULE
    INTENT = SymbolKind.INTENT

# 这里的 Symbol 实际上就是 core.compiler.semantic.symbols.Symbol

from enum import Enum, auto
from typing import Dict, Optional, Any
from .types import Type, AnyType

class SymbolKind(Enum):
    VARIABLE = auto()
    FUNCTION = auto()
    TYPE = auto()
    MODULE = auto()

class Symbol:
    def __init__(self, name: str, kind: SymbolKind, type_info: Type, is_builtin: bool = False):
        self.name = name
        self.kind = kind
        self.type_info = type_info
        self.is_builtin = is_builtin
        
    def __repr__(self):
        return f"Symbol({self.name}, {self.kind}, {self.type_info})"

class Scope:
    def __init__(self, parent: Optional['Scope'] = None, name: str = "global"):
        self.symbols: Dict[str, Symbol] = {}
        self.parent = parent
        self.name = name

    def define(self, symbol: Symbol):
        self.symbols[symbol.name] = symbol

    def resolve(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.resolve(name)
        return None
    
    def resolve_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

class SymbolTable:
    def __init__(self):
        self.global_scope = Scope(name="global")
        self.current_scope = self.global_scope
        self._init_builtins()

    def enter_scope(self, name: str = "local"):
        self.current_scope = Scope(parent=self.current_scope, name=name)

    def exit_scope(self):
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent
        else:
            raise RuntimeError("Cannot exit global scope")

    def _init_builtins(self):
        from .types import PrimitiveType, VoidType, FunctionType, ListType, DictType
        
        # 1. Register Built-in Types (as TYPE symbols)
        # Note: 'int', 'float' etc are types.
        type_names = ['int', 'float', 'str', 'bool', 'void', 'Any']
        for name in type_names:
            if name == 'void':
                t = VoidType()
            elif name == 'Any':
                t = AnyType()
            else:
                t = PrimitiveType(name)
            
            # The symbol 'int' refers to the TYPE 'int'.
            # Its "type_info" is the type itself? Or a TypeType?
            # For simplicity, if kind is TYPE, type_info is the type it represents.
            self.global_scope.define(Symbol(name, SymbolKind.TYPE, t, is_builtin=True))
            
        # 2. Register Built-in Functions
        # print(Any...) -> void
        print_sym = Symbol('print', SymbolKind.FUNCTION, 
                           FunctionType([AnyType()], VoidType()), 
                           is_builtin=True)
        self.global_scope.define(print_sym)
        
        # len(Any) -> int (Simplified)
        len_sym = Symbol('len', SymbolKind.FUNCTION,
                         FunctionType([AnyType()], PrimitiveType('int')),
                         is_builtin=True)
        self.global_scope.define(len_sym)
        
        # input(str) -> str
        input_sym = Symbol('input', SymbolKind.FUNCTION,
                           FunctionType([PrimitiveType('str')], PrimitiveType('str')),
                           is_builtin=True)
        self.global_scope.define(input_sym)

        # 3. Register Constructors/Casts as Functions?
        # If user writes `int("123")`, they are calling the `int` function.
        # But `int` is already defined as a TYPE.
        # Approach: The Semantic Analyzer handles `Call` nodes.
        # If the called symbol is a TYPE, it treats it as a constructor call.
        # So we don't need to double-register `int` as a function.

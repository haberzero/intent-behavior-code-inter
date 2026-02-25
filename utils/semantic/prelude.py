
from typing import Dict
from utils.semantic.types import (
    Type, PrimitiveType, AnyType, ListType, DictType, FunctionType, ModuleType,
    INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE, VOID_TYPE, ANY_TYPE
)
from typedef.scope_types import ScopeNode, ScopeType
from typedef.symbol_types import SymbolType

class Prelude:
    """
    Manages builtin types and functions for the IBC-Inter language.
    """
    def __init__(self):
        self.builtin_functions: Dict[str, FunctionType] = {}
        self.builtin_modules: Dict[str, ModuleType] = {}
        self._init_defaults()
        
    def _init_defaults(self):
        # print(...) -> void
        self.register("print", FunctionType([ANY_TYPE], VOID_TYPE))
        
        # len(list/str) -> int
        self.register("len", FunctionType([ANY_TYPE], INT_TYPE))
        
        # range(int) -> list[int]
        self.register("range", FunctionType([INT_TYPE], ListType(INT_TYPE)))
        
        # str(any) -> str
        self.register("str", FunctionType([ANY_TYPE], STR_TYPE))
        
        # int(any) -> int
        self.register("int", FunctionType([ANY_TYPE], INT_TYPE))

        # -- Builtin Modules --
        # ai module
        ai_scope = ScopeNode(ScopeType.GLOBAL)
        ai_scope.define("set_config", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE, STR_TYPE, STR_TYPE], VOID_TYPE)
        self.builtin_modules["ai"] = ModuleType(ai_scope)

        # json module
        json_scope = ScopeNode(ScopeType.GLOBAL)
        json_scope.define("parse", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], ANY_TYPE)
        json_scope.define("stringify", SymbolType.FUNCTION).type_info = FunctionType([ANY_TYPE], STR_TYPE)
        self.builtin_modules["json"] = ModuleType(json_scope)

        # file module
        file_scope = ScopeNode(ScopeType.GLOBAL)
        file_scope.define("read", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], STR_TYPE)
        file_scope.define("write", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE, STR_TYPE], VOID_TYPE)
        file_scope.define("exists", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], BOOL_TYPE)
        self.builtin_modules["file"] = ModuleType(file_scope)
        
    def register(self, name: str, func_type: FunctionType):
        self.builtin_functions[name] = func_type
        
    def get_builtins(self) -> Dict[str, FunctionType]:
        return self.builtin_functions.copy()

    def get_builtin_modules(self) -> Dict[str, ModuleType]:
        return self.builtin_modules.copy()

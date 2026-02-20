
from typing import Dict
from utils.semantic.types import (
    Type, PrimitiveType, AnyType, ListType, DictType, FunctionType,
    INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE, VOID_TYPE, ANY_TYPE
)

class Prelude:
    """
    Manages builtin types and functions for the IBC-Inter language.
    """
    def __init__(self):
        self.builtin_functions: Dict[str, FunctionType] = {}
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
        
    def register(self, name: str, func_type: FunctionType):
        self.builtin_functions[name] = func_type
        
    def get_builtins(self) -> Dict[str, FunctionType]:
        return self.builtin_functions.copy()

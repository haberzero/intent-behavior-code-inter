
from typing import Dict, Optional
from core.compiler.semantic.types import (
    Type, PrimitiveType, AnyType, ListType, DictType, FunctionType, ModuleType,
    INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE, VOID_TYPE, ANY_TYPE
)
from core.types.scope_types import ScopeNode, ScopeType
from core.types.symbol_types import SymbolType
from core.support.host_interface import HostInterface

class Prelude:
    """
    Manages builtin types and functions for the IBC-Inter language.
    """
    def __init__(self, host_interface: Optional[HostInterface] = None):
        self.builtin_functions: Dict[str, FunctionType] = {}
        self.builtin_modules: Dict[str, ModuleType] = {}
        self.host_interface = host_interface
        self._init_defaults()
        
    def _init_defaults(self):
        # 1. 注册核心内置函数
        self.register("print", FunctionType([ANY_TYPE], VOID_TYPE))
        self.register("len", FunctionType([ANY_TYPE], INT_TYPE))
        self.register("range", FunctionType([INT_TYPE], ListType(INT_TYPE)))
        self.register("str", FunctionType([ANY_TYPE], STR_TYPE))
        self.register("int", FunctionType([ANY_TYPE], INT_TYPE))

        # 2. 从 HostInterface 动态加载模块和函数
        if self.host_interface:
            # 模块
            for mod_name in self.host_interface.get_all_module_names():
                mod_type = self.host_interface.get_module_type(mod_name)
                if mod_type:
                    self.builtin_modules[mod_name] = mod_type
            
            # 全局函数
            for func_name, func_type in self.host_interface.get_global_functions().items():
                self.builtin_functions[func_name] = func_type
        
    def register(self, name: str, func_type: FunctionType):
        self.builtin_functions[name] = func_type
        
    def get_builtins(self) -> Dict[str, FunctionType]:
        return self.builtin_functions.copy()

    def get_builtin_modules(self) -> Dict[str, ModuleType]:
        return self.builtin_modules.copy()

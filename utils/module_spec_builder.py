from typing import List, Dict, Any, Optional, Union
from typedef.scope_types import ScopeNode, ScopeType
from typedef.symbol_types import SymbolType
from utils.semantic.types import (
    FunctionType, ModuleType, Type,
    INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE, VOID_TYPE, ANY_TYPE,
    get_builtin_type
)

class SpecBuilder:
    """
    IBC-Inter 模块声明构建器。
    用于以简洁的方式定义模块的静态接口（元数据）。
    """
    def __init__(self, name: str):
        self.name = name
        self.scope = ScopeNode(ScopeType.GLOBAL)
        self._type_map = {
            "int": INT_TYPE,
            "float": FLOAT_TYPE,
            "str": STR_TYPE,
            "bool": BOOL_TYPE,
            "void": VOID_TYPE,
            "any": ANY_TYPE,
            "var": ANY_TYPE
        }

    def _resolve_type(self, t: Union[str, Type]) -> Type:
        if isinstance(t, Type):
            return t
        return self._type_map.get(t.lower(), ANY_TYPE)

    def func(self, name: str, params: List[Union[str, Type]] = None, returns: Union[str, Type] = "void") -> 'SpecBuilder':
        """声明一个函数"""
        param_types = [self._resolve_type(p) for p in (params or [])]
        return_type = self._resolve_type(returns)
        
        self.scope.define(name, SymbolType.FUNCTION).type_info = FunctionType(param_types, return_type)
        return self

    def var(self, name: str, type: Union[str, Type] = "any") -> 'SpecBuilder':
        """声明一个变量"""
        self.scope.define(name, SymbolType.VARIABLE).type_info = self._resolve_type(type)
        return self

    def build(self) -> ModuleType:
        """构建并返回 ModuleType"""
        return ModuleType(self.scope)

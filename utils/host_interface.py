from typing import Dict, Any, Optional, List
from utils.semantic.types import ModuleType, FunctionType, ANY_TYPE, VOID_TYPE, get_builtin_type
from typedef.scope_types import ScopeNode, ScopeType
from typedef.symbol_types import SymbolType

class HostInterface:
    """
    统一的宿主环境接口注册器。
    它不仅持有运行时的 Python 实现，还持有静态分析所需的类型信息。
    """
    def __init__(self):
        self._modules: Dict[str, Any] = {}
        self._module_types: Dict[str, ModuleType] = {}
        self._global_functions: Dict[str, FunctionType] = {}

    def register_module(self, name: str, implementation: Any, type_metadata: Optional[ModuleType] = None):
        """
        注册一个外部模块。
        
        Args:
            name: 模块名称 (如 'ai')
            implementation: Python 实现对象 (如类或模块)
            type_metadata: 静态类型信息。如果不提供，将通过反射或默认 Any 映射。
        """
        self._modules[name] = implementation
        if type_metadata:
            self._module_types[name] = type_metadata
        else:
            # 默认创建一个全为 Any 的影子作用域
            scope = ScopeNode(ScopeType.GLOBAL)
            self._module_types[name] = ModuleType(scope)

    def register_global_function(self, name: str, implementation: Any, func_type: FunctionType):
        """注册全局可见的内置函数"""
        self._modules[name] = implementation
        self._global_functions[name] = func_type

    def is_external_module(self, name: str) -> bool:
        """检查是否为外部注册的模块"""
        return name in self._modules and name in self._module_types

    def get_module_type(self, name: str) -> Optional[ModuleType]:
        """获取模块的静态类型信息"""
        return self._module_types.get(name)

    def get_module_implementation(self, name: str) -> Optional[Any]:
        """获取模块的运行时实现"""
        return self._modules.get(name)

    def get_all_module_names(self) -> List[str]:
        """获取所有已注册的外部模块名称"""
        return list(self._module_types.keys())

    def get_global_functions(self) -> Dict[str, FunctionType]:
        """获取所有已注册的全局函数类型"""
        return self._global_functions.copy()

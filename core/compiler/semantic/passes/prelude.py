from typing import Dict, Optional, List
from core.domain.symbols import (
    StaticType, BuiltinType, ListType, FunctionType, ClassType,
    STATIC_ANY, STATIC_INT, STATIC_FLOAT, STATIC_STR, STATIC_BOOL, STATIC_VOID
)

class Prelude:
    """
    静态预设：管理编译器前端使用的内置静态符号和类型。
    """
    def __init__(self, host_interface: Optional[any] = None):
        self.builtin_functions: Dict[str, FunctionType] = {}
        self.builtin_modules: Dict[str, StaticType] = {} # 模块目前简单视为一种类型
        self.builtin_types: Dict[str, StaticType] = {}
        self._init_defaults()
        
    def _init_defaults(self):
        # 核心内置函数
        self.register_func("print", [STATIC_ANY], STATIC_VOID)
        self.register_func("len", [STATIC_ANY], STATIC_INT)
        self.register_func("range", [STATIC_INT], ListType(STATIC_INT))

        # 核心内置类 (静态描述)
        self.builtin_types["Exception"] = ClassType("Exception")
        self.builtin_types["int"] = STATIC_INT
        self.builtin_types["str"] = STATIC_STR
        self.builtin_types["float"] = STATIC_FLOAT
        self.builtin_types["bool"] = STATIC_BOOL
        self.builtin_types["void"] = STATIC_VOID
        self.builtin_types["none"] = STATIC_VOID # 映射到 STATIC_VOID
        self.builtin_types["Any"] = STATIC_ANY
        self.builtin_types["var"] = STATIC_ANY
        self.builtin_types["list"] = ListType(STATIC_ANY)
        self.builtin_types["dict"] = BuiltinType("dict")
        
    def register_func(self, name: str, param_types: List[StaticType], return_type: StaticType):
        self.builtin_functions[name] = FunctionType(name=name, param_types=param_types, return_type=return_type)
        
    def get_builtins(self) -> Dict[str, FunctionType]:
        return self.builtin_functions.copy()

    def get_builtin_types(self) -> Dict[str, StaticType]:
        return self.builtin_types.copy()

    def get_builtin_modules(self) -> Dict[str, StaticType]:
        return self.builtin_modules.copy()

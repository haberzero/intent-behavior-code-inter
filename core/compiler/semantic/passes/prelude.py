from typing import Dict, Optional, List, Any
from core.domain.symbols import (
    StaticType, BuiltinType, ListType, FunctionType, ClassType,
    STATIC_ANY, STATIC_INT, STATIC_FLOAT, STATIC_STR, STATIC_BOOL, STATIC_VOID
)

class Prelude:
    """
    静态预设：管理编译器前端使用的内置静态符号和类型。
    """
    def __init__(self, host_interface: Optional[any] = None, registry: Optional[Any] = None):
        self.builtin_functions: Dict[str, FunctionType] = {}
        self.builtin_modules: Dict[str, StaticType] = {} # 模块目前简单视为一种类型
        self.builtin_types: Dict[str, StaticType] = {}
        self.registry = registry
        self._init_defaults()
        
    def _init_defaults(self):
        # 0. 准备类型上下文 (优先从引擎注册表中获取隔离的静态类型)
        from core.domain.symbols import StaticTypeFactory, STATIC_ANY, STATIC_VOID, STATIC_INT
        
        def _get_type(name: str, fallback: Any) -> Any:
            if self.registry and self.registry._metadata_registry:
                desc = self.registry._metadata_registry.resolve(name)
                if desc:
                    return StaticTypeFactory.create_from_descriptor(desc)
            return fallback

        st_any = _get_type("Any", STATIC_ANY)
        st_void = _get_type("void", STATIC_VOID)
        st_int = _get_type("int", STATIC_INT)
        st_float = _get_type("float", STATIC_FLOAT)
        st_str = _get_type("str", STATIC_STR)
        st_bool = _get_type("bool", STATIC_BOOL)

        # 核心内置函数
        self.register_func("print", [st_any], st_void)
        self.register_func("len", [st_any], st_int)
        self.register_func("range", [st_int], ListType(st_int))

        # 核心内置类 (静态描述)
        self.builtin_types["Exception"] = ClassType("Exception")
        self.builtin_types["int"] = st_int
        self.builtin_types["str"] = st_str
        self.builtin_types["float"] = st_float
        self.builtin_types["bool"] = st_bool
        self.builtin_types["void"] = st_void
        self.builtin_types["none"] = st_void
        self.builtin_types["Any"] = st_any
        self.builtin_types["var"] = st_any
        
        if self.registry and self.registry._metadata_registry:
            list_desc = self.registry._metadata_registry.resolve("list")
            if list_desc:
                self.builtin_types["list"] = StaticTypeFactory.create_from_descriptor(list_desc)
            dict_desc = self.registry._metadata_registry.resolve("dict")
            if dict_desc:
                self.builtin_types["dict"] = StaticTypeFactory.create_from_descriptor(dict_desc)
        else:
            self.builtin_types["list"] = ListType(st_any)
            self.builtin_types["dict"] = BuiltinType("dict")
        
        # 可调用对象类型 (Lambda 化的行为描述行)
        self.builtin_types["callable"] = FunctionType([], STATIC_ANY, name="callable")
        
    def register_func(self, name: str, param_types: List[StaticType], return_type: StaticType):
        self.builtin_functions[name] = FunctionType(name=name, param_types=param_types, return_type=return_type)
        
    def get_builtins(self) -> Dict[str, FunctionType]:
        return self.builtin_functions.copy()

    def get_builtin_types(self) -> Dict[str, StaticType]:
        return self.builtin_types.copy()

    def get_builtin_modules(self) -> Dict[str, StaticType]:
        return self.builtin_modules.copy()

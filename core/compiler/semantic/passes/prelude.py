from typing import Dict, Optional, List, Any
from core.domain.symbols import (
    StaticType, BuiltinType, ListType, FunctionType, ClassType,
    STATIC_ANY, STATIC_INT, STATIC_FLOAT, STATIC_STR, STATIC_BOOL, STATIC_VOID
)
from core.domain import types as uts
from core.compiler.semantic.bridge import TypeBridge # 引入语义网关

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
        # 0. 准备类型上下文 (完全通过语义网关动态拉取)
        if not self.registry or not self.registry._metadata_registry:
            # 降级处理：如果没有注册表上下文，则只使用最基础的硬编码原型
            from core.domain.symbols import get_builtin_type
            for name in ["int", "str", "float", "bool", "void", "Any", "var"]:
                self.builtin_types[name] = get_builtin_type(name)
            return

        # 1. 委托 TypeBridge 进行批量语义同步
        # [IES 2.0 ARCH] Prelude 职责降级为：将网关同步来的符号分类存入对应表
        all_symbols = TypeBridge.import_all_from_registry(self.registry)
        
        from core.domain.symbols import ModuleType # 局部导入以避免循环依赖
        
        for name, sm_type in all_symbols.items():
            if isinstance(sm_type, FunctionType):
                self.builtin_functions[name] = sm_type
            elif isinstance(sm_type, ModuleType):
                self.builtin_modules[name] = sm_type
            else:
                self.builtin_types[name] = sm_type
                
        # 2. 补全特殊映射
        if "Any" in self.builtin_types:
            self.builtin_types["var"] = self.builtin_types["Any"]
        if "void" in self.builtin_types:
            self.builtin_types["none"] = self.builtin_types["void"]
            
        # 3. 兜底 Exception (如果 Registry 没注册)
        if "Exception" not in self.builtin_types:
            self.builtin_types["Exception"] = ClassType("Exception")
        
    def register_func(self, name: str, param_types: List[StaticType], return_type: StaticType):
        self.builtin_functions[name] = FunctionType(name=name, param_types=param_types, return_type=return_type)
        
    def get_builtins(self) -> Dict[str, FunctionType]:
        return self.builtin_functions.copy()

    def get_builtin_types(self) -> Dict[str, StaticType]:
        return self.builtin_types.copy()

    def get_builtin_modules(self) -> Dict[str, StaticType]:
        return self.builtin_modules.copy()

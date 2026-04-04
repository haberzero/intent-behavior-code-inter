from typing import Dict, Optional, List, Any
from core.kernel import types as uts
from core.kernel.types.descriptors import (
    TypeDescriptor, FunctionMetadata, ModuleMetadata,
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR,
    VAR_DESCRIPTOR, LIST_DESCRIPTOR, DICT_DESCRIPTOR,
    CALLABLE_DESCRIPTOR, BEHAVIOR_DESCRIPTOR, EXCEPTION_DESCRIPTOR
)
from core.kernel.factory import create_default_registry

class Prelude:
    """
    静态预设：管理编译器前端使用的内置静态符号和类型。
    """
    def __init__(self, host_interface: Optional[Any] = None, registry: Optional[Any] = None):
        self.builtin_functions: Dict[str, FunctionMetadata] = {}
        self.builtin_modules: Dict[str, TypeDescriptor] = {} # 模块也是一种 TypeDescriptor (ModuleMetadata)
        self.builtin_types: Dict[str, TypeDescriptor] = {}
        self.builtin_variables: Dict[str, TypeDescriptor] = {}
        self.registry = registry
        self.host_interface = host_interface
        self._init_defaults()
        
    def _init_defaults(self):
        # [Axiom Hook] 优先从公理注册表加载内置类型
        
        # [Strict Registry] 必须直接传入有效的 MetadataRegistry
        if not self.registry:
             # 如果没有 registry，SemanticAnalyzer 应该已经抛出错误，但这里作为防御
             raise ValueError("Prelude requires a valid MetadataRegistry.")
             
        metadata_reg = self.registry
        
        # 1. 自动加载公理化类型
        # 直接从 MetadataRegistry 导入所有顶层描述符
        for name, desc in metadata_reg.all_descriptors.items():
            if "." in name: continue
            
            # 使用能力探测替代 isinstance 检查
            if desc.get_call_trait() and not desc.is_class():
                self.builtin_functions[name] = desc
            elif desc.is_module():
                self.builtin_modules[name] = desc
            else:
                self.builtin_types[name] = desc

        # 2. 内置常量 (原用于注册标准内置常量 __file__ / __dir__，现已移至 sys 模块封装)
        # 保持 builtin_variables 机制不变，以防未来有其他安全的环境变量需要注入
        str_desc = metadata_reg.resolve("str") or STR_DESCRIPTOR

        # TODO: 此处似乎是代码异味？ 目前看起来MVP可以运行，暂缓，后续再进行严格审核
        # 3. 从 HostInterface 导入外部发现的模块
        # Prelude 不再自动加载所有 Host 模块。
        # 只有那些显式标记为 "auto_import" 或特殊地位的模块才放入 builtin_modules。
        # 目前 IBCI 要求大多数插件通过 import 显式引入。
        if self.host_interface:
            # 只有 'ai' 这种核心协议级别的模块才可能需要自动注入（如果用户这么设计的话）
            # 但目前我们倾向于让用户显式 import，除了那些编译器强制要求的。
            pass

        # 3. 补全特殊映射
        if "Any" in self.builtin_types and "var" not in self.builtin_types:
            self.builtin_types["var"] = self.builtin_types["Any"]
        if "void" in self.builtin_types and "none" not in self.builtin_types:
            self.builtin_types["none"] = self.builtin_types["void"]
            
        # 4. 补全 behavior 类型映射
        if "behavior" not in self.builtin_types and "callable" in self.builtin_types:
            self.builtin_types["behavior"] = self.builtin_types["callable"]
        
    def register_func(self, name: str, param_types: List[TypeDescriptor], return_type: TypeDescriptor):
        self.builtin_functions[name] = FunctionMetadata(name=name, param_types=param_types, return_type=return_type)
        
    def get_builtins(self) -> Dict[str, FunctionMetadata]:
        return self.builtin_functions.copy()

    def get_builtin_types(self) -> Dict[str, TypeDescriptor]:
        return self.builtin_types.copy()

    def get_builtin_modules(self) -> Dict[str, TypeDescriptor]:
        return self.builtin_modules.copy()

    def get_builtin_variables(self) -> Dict[str, TypeDescriptor]:
        """获取内置全局变量/常量描述符"""
        return self.builtin_variables.copy()

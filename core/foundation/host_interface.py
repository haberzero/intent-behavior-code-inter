from typing import Dict, Any, Optional, List
from core.domain.types import (
    TypeDescriptor, INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, 
    ModuleMetadata, FunctionMetadata
)

class MetadataRegistry:
    """
    只负责管理 TypeDescriptor 的注册表。
    供编译器（Compiler）使用，完全脱离运行时实现。
    """
    def __init__(self):
        self._module_metadata: Dict[str, ModuleMetadata] = {}
        self._global_functions: Dict[str, FunctionMetadata] = {}

    def register_module(self, name: str, metadata: ModuleMetadata):
        self._module_metadata[name] = metadata

    def register_global_function(self, name: str, metadata: FunctionMetadata):
        self._global_functions[name] = metadata

    def get_module_metadata(self, name: str) -> Optional[ModuleMetadata]:
        return self._module_metadata.get(name)

    def get_global_functions(self) -> Dict[str, FunctionMetadata]:
        return self._global_functions.copy()

    def is_external_module(self, name: str) -> bool:
        return name in self._module_metadata

class RuntimeRegistry:
    """
    负责管理真实的运行时实现。
    供解释器（Interpreter）使用。
    """
    def __init__(self):
        self._implementations: Dict[str, Any] = {}

    def register(self, name: str, implementation: Any):
        self._implementations[name] = implementation

    def get(self, name: str) -> Optional[Any]:
        return self._implementations.get(name)

class HostInterface:
    """
    统一的宿主环境接口注册器。
    协调元数据注册和运行时实现注册。
    """
    def __init__(self):
        self.metadata = MetadataRegistry()
        self.runtime = RuntimeRegistry()
        self._module_metadata_map: Dict[str, ModuleMetadata] = {}

    def register_module(self, name: str, implementation: Any, metadata: Optional[ModuleMetadata] = None):
        """
        同时注册元数据和实现。
        如果 metadata 为 None，则不再进行暴力反射推断（在编译器路径下应显式提供元数据）。
        """
        self.runtime.register(name, implementation)
        if metadata:
            self._module_metadata_map[name] = metadata
            self.metadata.register_module(name, metadata)
        else:
            # 警告：缺少显式元数据。在彻底脱离解释器的目标下，编译器不应依赖此处的逻辑。
            # 这里可以保留一个极简的占位符元数据，但不建议使用。
            self.metadata.register_module(name, ModuleMetadata(name=name))

    def register_global_function(self, name: str, implementation: Any, metadata: FunctionMetadata):
        self.runtime.register(name, implementation)
        self.metadata.register_global_function(name, metadata)

    # --- 兼容性接口 ---
    def is_external_module(self, name: str) -> bool:
        return self.metadata.is_external_module(name)

    def get_module_type(self, name: str) -> Optional[ModuleMetadata]:
        return self._module_metadata_map.get(name) or self.metadata.get_module_metadata(name)

    def get_module_implementation(self, name: str) -> Optional[Any]:
        return self.runtime.get(name)

    def get_all_module_names(self) -> List[str]:
        return list(self.metadata._module_metadata.keys())

    def get_global_functions(self) -> Dict[str, FunctionMetadata]:
        return self.metadata.get_global_functions()

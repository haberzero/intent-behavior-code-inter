from typing import Dict, Any, Optional, List
from core.domain.types import (
    TypeDescriptor, INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, 
    ModuleMetadata, FunctionMetadata
)

from core.domain.types.registry import MetadataRegistry

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
            self.metadata.register(metadata)
        else:
            # 警告：缺少显式元数据。在彻底脱离解释器的目标下，编译器不应依赖此处的逻辑。
            # 这里可以保留一个极简的占位符元数据，但不建议使用。
            self.metadata.register(ModuleMetadata(name=name))

    def register_global_function(self, name: str, implementation: Any, metadata: FunctionMetadata):
        self.runtime.register(name, implementation)
        self.metadata.register(metadata)

    # --- 兼容性接口 ---
    def is_external_module(self, name: str) -> bool:
        # [IES 2.1 Refactor] 直接检查注册表是否存在该描述符
        return self.metadata.resolve(name) is not None

    def get_module_type(self, name: str) -> Optional[ModuleMetadata]:
        # [IES 2.1 Refactor] 直接解析描述符并验证类型
        if name in self._module_metadata_map:
            return self._module_metadata_map[name]
        
        desc = self.metadata.resolve(name)
        return desc if isinstance(desc, ModuleMetadata) else None

    def get_module_implementation(self, name: str) -> Optional[Any]:
        return self.runtime.get(name)

    def get_all_module_names(self) -> List[str]:
        # [IES 2.1 Refactor] 从注册表快照中提取模块名称
        return [d.name for d in self.metadata.all_descriptors.values() if isinstance(d, ModuleMetadata)]

    def get_global_functions(self) -> Dict[str, FunctionMetadata]:
        # [IES 2.1 Refactor] 从注册表快照中提取全局函数
        return {d.name: d for d in self.metadata.all_descriptors.values() if isinstance(d, FunctionMetadata)}

from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.types import ModuleMetadata, FunctionMetadata
    from core.kernel.types.registry import MetadataRegistry

class HostModuleRegistry:
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
    def __init__(self, external_registry=None):
        from core.kernel.types.registry import MetadataRegistry
        self.metadata: 'MetadataRegistry' = external_registry if external_registry else MetadataRegistry()
        self.runtime = HostModuleRegistry()
        self._module_metadata_map: Dict[str, 'ModuleMetadata'] = {}

    def register_module(self, name: str, implementation: Any, metadata: Optional['ModuleMetadata'] = None):
        """
        同时注册元数据和实现。
        如果 metadata 为 None，则不再进行暴力反射推断（在编译器路径下应显式提供元数据）。
        """
        self.runtime.register(name, implementation)
        if metadata:
            self._module_metadata_map[name] = metadata
            self.metadata.register(metadata)
        else:
            from core.kernel.types import ModuleMetadata
            self.metadata.register(ModuleMetadata(name=name))

    def register_global_function(self, name: str, implementation: Any, metadata: 'FunctionMetadata'):
        self.runtime.register(name, implementation)
        self.metadata.register(metadata)

    def get_module_implementation(self, name: str) -> Optional[Any]:
        return self.runtime.get(name)

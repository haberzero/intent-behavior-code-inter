from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.types import ModuleMetadata, FunctionMetadata
    from core.kernel.types.registry import MetadataRegistry
    from core.kernel.axioms.registry import AxiomRegistry


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
    [IES 2.2] 统一的宿主环境接口注册器。

    协调元数据注册和运行时实现注册。
    所有 HostInterface 实例必须绑定到带有 AxiomRegistry 的 MetadataRegistry。
    """
    def __init__(self, external_registry: Optional['MetadataRegistry'] = None):
        from core.kernel.types.registry import MetadataRegistry
        from core.kernel.axioms.registry import AxiomRegistry
        from core.kernel.axioms.primitives import register_core_axioms

        if external_registry is not None:
            self.metadata: 'MetadataRegistry' = external_registry
        else:
            axiom_reg = AxiomRegistry()
            register_core_axioms(axiom_reg)
            self.metadata = MetadataRegistry(axiom_registry=axiom_reg)

        self.runtime = HostModuleRegistry()
        self._module_metadata_map: Dict[str, 'ModuleMetadata'] = {}

    def register_module(self, name: str, implementation: Any, metadata: Optional['ModuleMetadata'] = None):
        """
        [IES 2.2] 同时注册元数据和实现。

        如果 metadata 为 None，则创建一个仅含名称的 ModuleMetadata。
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

    def get_axiom_registry(self) -> Optional['AxiomRegistry']:
        """获取关联的 AxiomRegistry"""
        return self.metadata.get_axiom_registry()

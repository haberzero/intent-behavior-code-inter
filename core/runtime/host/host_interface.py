from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.spec import ModuleSpec, FuncSpec
    from core.kernel.spec.registry import SpecRegistry
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
    统一的宿主环境接口注册器。

    协调元数据注册和运行时实现注册。
    所有 HostInterface 实例必须绑定到带有 AxiomRegistry 的 SpecRegistry。
    """
    def __init__(self, external_registry: Optional['SpecRegistry'] = None):
        from core.kernel.spec.registry import SpecRegistry
        from core.kernel.axioms.registry import AxiomRegistry
        from core.kernel.axioms.primitives import register_core_axioms
        from core.kernel.factory import create_default_registry

        if external_registry is not None:
            self.metadata: 'SpecRegistry' = external_registry
        else:
            self.metadata = create_default_registry()

        self.runtime = HostModuleRegistry()
        self._module_metadata_map: Dict[str, 'ModuleSpec'] = {}
        self._discovery_map: Dict[str, str] = {}  # Mapping: discovery_name -> module_name
        self._reverse_discovery_map: Dict[str, str] = {}  # Mapping: module_name -> discovery_name

    def register_module(self, name: str, implementation: Any, metadata: Optional['ModuleSpec'] = None, discovery_name: Optional[str] = None):
        """
        同时注册元数据和实现。

        discovery_name: 物理名称 (如目录名)。
        """
        self.runtime.register(name, implementation)
        if discovery_name:
            self._discovery_map[discovery_name] = name
            self._reverse_discovery_map[name] = discovery_name

        if metadata:
            self._module_metadata_map[name] = metadata
            self.metadata.register(metadata)
        else:
            from core.kernel.spec import ModuleSpec
            self.metadata.register(ModuleSpec(name=name))

    def get_module_by_discovery_name(self, discovery_name: str) -> Optional[str]:
        """根据物理发现名称查找已注册的模块名称"""
        return self._discovery_map.get(discovery_name)

    def get_discovery_name_by_module(self, module_name: str) -> Optional[str]:
        """根据逻辑模块名查找物理发现名称"""
        return self._reverse_discovery_map.get(module_name)

    def register_global_function(self, name: str, implementation: Any, metadata: 'FuncSpec'):
        self.runtime.register(name, implementation)
        self.metadata.register(metadata)

    def get_module_implementation(self, name: str) -> Optional[Any]:
        return self.runtime.get(name)

    def get_axiom_registry(self) -> Optional['AxiomRegistry']:
        """获取关联的 AxiomRegistry"""
        return self.metadata.get_axiom_registry()

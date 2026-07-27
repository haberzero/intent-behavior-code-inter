from typing import Dict, Any, Optional, List, Set, TYPE_CHECKING

from core.base.enums import Provenance
from core.kernel.spec import TypeDef
from core.kernel.spec.registry import SpecRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms
from core.kernel.factory import create_default_registry


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
    def __init__(self, external_registry: Optional[SpecRegistry] = None):
        if external_registry is not None:
            self.metadata: SpecRegistry = external_registry
        else:
            self.metadata = create_default_registry()

        self.runtime = HostModuleRegistry()
        self._module_metadata_map: Dict[str, TypeDef] = {}
        self._discovery_map: Dict[str, str] = {}  # Mapping: discovery_name -> module_name
        self._reverse_discovery_map: Dict[str, str] = {}  # Mapping: module_name -> discovery_name
        self._kernel_native_names: Set[str] = set()  # kernel-native 逻辑名集合

    def reserve_kernel_native_name(self, name: str) -> None:
        """将逻辑模块名标记为 kernel-native，禁止后续用户插件覆盖。"""
        self._kernel_native_names.add(name)

    def is_kernel_native(self, name: str) -> bool:
        """判断逻辑模块名是否为 kernel-native。"""
        return name in self._kernel_native_names

    def register_module(self, name: str, implementation: Any, metadata: Optional[TypeDef] = None, discovery_name: Optional[str] = None):
        """
        同时注册元数据和实现。

        discovery_name: 物理名称 (如目录名)。

        若 name 已被标记为 kernel-native，则只允许 kernel-native 自身注册；
        用户插件尝试覆盖时直接忽略。
        """
        is_kernel_native_meta = metadata is not None and metadata.provenance == Provenance.KERNEL_NATIVE

        if name in self._kernel_native_names and not is_kernel_native_meta:
            # 用户插件尝试覆盖 kernel-native 模块，忽略
            return

        if is_kernel_native_meta:
            self._kernel_native_names.add(name)

        self.runtime.register(name, implementation)
        if discovery_name:
            self._discovery_map[discovery_name] = name
            self._reverse_discovery_map[name] = discovery_name

        if metadata:
            self._module_metadata_map[name] = metadata
            self.metadata.register(metadata)
        else:
            self.metadata.register(TypeDef(name=name))

    def get_module_by_discovery_name(self, discovery_name: str) -> Optional[str]:
        """根据物理发现名称查找已注册的模块名称"""
        return self._discovery_map.get(discovery_name)

    def get_discovery_name_by_module(self, module_name: str) -> Optional[str]:
        """根据逻辑模块名查找物理发现名称"""
        return self._reverse_discovery_map.get(module_name)

    def register_global_function(self, name: str, implementation: Any, metadata: TypeDef):
        self.runtime.register(name, implementation)
        self.metadata.register(metadata)

    def get_module_implementation(self, name: str) -> Optional[Any]:
        return self.runtime.get(name)

    def get_axiom_registry(self) -> Optional['AxiomRegistry']:
        """获取关联的 AxiomRegistry"""
        return self.metadata.get_axiom_registry()

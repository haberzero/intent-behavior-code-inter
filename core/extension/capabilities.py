from typing import Any, Optional, Dict, Callable, List
from dataclasses import dataclass, field

__all__ = [
    "PluginCapabilities",
    "ExtensionCapabilities",
]

@dataclass
class PluginCapabilities:
    """[IES 2.1 SDK] 插件能力容器。统一管理所有可注入到插件的能力。"""
    llm_provider: Optional[Any] = None
    llm_executor: Optional[Any] = None
    intent_manager: Optional[Any] = None
    state_reader: Optional[Any] = None
    symbol_view: Optional[Any] = None
    stack_inspector: Optional[Any] = None
    permission_manager: Optional[Any] = None
    service_context: Optional[Any] = None
    _capability_registry: Optional[Any] = field(default=None, repr=False)
    _registry: Optional[Any] = field(default=None, repr=False)

    def expose(self, capability_name: str, provider: Any, priority: int = 0) -> None:
        """向能力注册表注册一个能力提供者"""
        if self._capability_registry:
            self._capability_registry.register(capability_name, provider, priority)

    def revoke(self, capability_name: str) -> None:
        """从能力注册表移除能力"""
        if self._capability_registry:
            self._capability_registry.unregister(capability_name)

    def get(self, capability_name: str) -> Optional[Any]:
        """获取已注册的能力"""
        if self._capability_registry:
            return self._capability_registry.get(capability_name)
        return None


ExtensionCapabilities = PluginCapabilities

from typing import Any, Optional, Dict, Callable, List
from dataclasses import dataclass, field

__all__ = [
    "PluginCapabilities",
    "ExtensionCapabilities",
]

@dataclass
class PluginCapabilities:
    """插件能力容器。统一管理所有可注入到插件的能力。"""
    llm_provider: Optional[Any] = None
    llm_executor: Optional[Any] = None
    intent_manager: Optional[Any] = None
    state_reader: Optional[Any] = None
    symbol_view: Optional[Any] = None
    stack_inspector: Optional[Any] = None
    permission_manager: Optional[Any] = None
    service_context: Optional[Any] = None
    execution_context: Optional[Any] = None
    _capability_registry: Optional[Any] = field(default=None, repr=False)
    _registry: Optional[Any] = field(default=None, repr=False)
    _plugin_id: str = field(default="", repr=False)

    def expose(self, capability_name: str, provider: Any, priority: int = 50) -> None:
        """向能力注册表注册一个能力提供者（以当前插件身份）。"""
        if self._capability_registry:
            self._capability_registry.register(
                capability_name, provider, plugin_id=self._plugin_id, priority=priority,
            )

    def revoke(self, capability_name: str) -> None:
        """从能力注册表移除当前插件提供的能力。"""
        if self._capability_registry:
            self._capability_registry.unregister(capability_name, plugin_id=self._plugin_id)

    def get(self, capability_name: str) -> Optional[Any]:
        """获取已注册的能力"""
        if self._capability_registry:
            return self._capability_registry.get(capability_name)
        return None

    @property
    def kernel_registry(self) -> Optional[Any]:
        """
        暴露 KernelRegistry 引用，供核心层插件使用。

        通过此属性访问 KernelRegistry，使插件可以调用
        get_host_service()、get_stack_inspector()、get_state_reader()、
        get_llm_executor() 等稳定接口，而无需持有 ServiceContext 引用。
        """
        return self._registry


ExtensionCapabilities = PluginCapabilities

from typing import Any, Callable, Optional, List, Dict
from abc import ABC

from core.extension.exceptions import PluginError, InterpreterError, CompilerError
from core.extension.capabilities import PluginCapabilities, ExtensionCapabilities


class IbPlugin(ABC):
    """
    [IES 2.1 SDK] 插件基类。
    提供自动化的虚表（VTable）生成和依赖注入契约支持。
    所有现代 IBCI 插件均应继承此类。
    """
    EXPOSE_LAZY = "lazy"
    EXPOSE_EAGER = "eager"

    def __init__(self, plugin_id: Optional[str] = None):
        self._plugin_id = plugin_id
        self._capabilities: Optional[PluginCapabilities] = None
        self._exposed_capabilities: Dict[str, Any] = {}

    @property
    def plugin_id(self) -> str:
        if self._plugin_id:
            return self._plugin_id
        return f"{self.__class__.__module__}:{self.__class__.__name__}"

    def setup(self, capabilities: PluginCapabilities) -> None:
        """
        [IES 2.0 Contract] 插件初始化入口。
        子类若需重写，请务必调用 super().setup(capabilities) 或确保持有 capabilities 引用。
        """
        self._capabilities = capabilities

    def get_vtable(self) -> Dict[str, Callable]:
        """
         虚表生成。

        从模块级 __ibcext_vtable__ 函数获取方法映射表。
        """
        if hasattr(self, '_ibcext_vtable_func') and callable(self._ibcext_vtable_func):
            return self._ibcext_vtable_func()
        return {}

    def expose(
        self,
        capability_name: str,
        provider: Any,
        priority: int = 50,
        mode: str = EXPOSE_EAGER
    ) -> None:
        """
         暴露能力到注册表。
        允许插件向 CapabilityRegistry 注册自己的能力供其他插件使用。
        """
        if mode == self.EXPOSE_LAZY:
            self._exposed_capabilities[capability_name] = {
                "type": "lazy",
                "provider": provider,
                "priority": priority
            }
            return

        actual_provider = provider
        if callable(provider) and not isinstance(provider, type):
            import types
            actual_provider = types.MethodType(provider, self)

        self._do_expose(capability_name, actual_provider, priority)

    def _do_expose(self, capability_name: str, provider: Any, priority: int) -> None:
        """执行实际的暴露操作"""
        if self._capabilities and hasattr(self._capabilities, '_capability_registry') and self._capabilities._capability_registry:
            registry = self._capabilities._capability_registry
            registry.register(
                capability_name,
                provider,
                plugin_id=self.plugin_id,
                priority=priority
            )
        self._exposed_capabilities[capability_name] = provider

    def revoke(self, capability_name: str) -> None:
        """撤回一个能力"""
        if self._capabilities and hasattr(self._capabilities, '_capability_registry') and self._capabilities._capability_registry:
            registry = self._capabilities._capability_registry
            registry.unregister(capability_name, plugin_id=self.plugin_id)
        self._exposed_capabilities.pop(capability_name, None)

    def revoke_all(self) -> None:
        """撤回所有能力"""
        if self._capabilities and hasattr(self._capabilities, '_capability_registry') and self._capabilities._capability_registry:
            registry = self._capabilities._capability_registry
            registry.unregister_all(plugin_id=self.plugin_id)
        self._exposed_capabilities.clear()

    def get_exposed_capabilities(self) -> Dict[str, Any]:
        """获取已暴露的能力列表"""
        return dict(self._exposed_capabilities)

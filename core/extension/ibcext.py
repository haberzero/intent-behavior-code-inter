from typing import Any, Callable, Optional, List, Dict
from abc import ABC

from core.extension.exceptions import PluginError, InterpreterError, CompilerError
from core.extension.capabilities import PluginCapabilities, ExtensionCapabilities


# ---------------------------------------------------------------------------
# IBC-Inter 插件体系层次说明
# ---------------------------------------------------------------------------
#
# IBC-Inter 插件分为两个层次：
#
# 【非侵入层（Non-Invasive Level）】
#   - 零内核依赖：_spec.py 只含纯 dict vtable，实现类不导入 core.*
#   - 通过 setup(capabilities) 接收注入的能力容器，只按需取用浅层能力
#     （如 capabilities.service_context.permission_manager）
#   - 适合：数学计算、JSON、HTTP、文件操作等无状态工具性插件
#   - 代表模块：ibci_math, ibci_json, ibci_time, ibci_net, ibci_file, ibci_schema
#
# 【核心层（Core Level）】
#   - 继承本文件中的 IbPlugin 基类
#   - 通过 PluginCapabilities 深度访问内核能力：
#       stack_inspector  调用栈/意图栈内省
#       state_reader     运行时变量和 LLM 结果读取
#       llm_executor     LLM 执行器
#       service_context  ServiceContext（含 host_service、scheduler 等）
#   - 可通过 capabilities.expose("xxx_provider", self) 向 CapabilityRegistry
#     注册自身，供其他插件或内核代码发现
#   - 适合：运行时调试、系统状态查询、宿主能力（持久化/隔离执行）等
#   - 代表模块：ibci_ihost, ibci_idbg, ibci_isys, ibci_sys
#
# 两种层次使用相同的 _spec.py 协议（__ibcext_metadata__ + __ibcext_vtable__）
# 和相同的 ModuleLoader 加载流程。核心层仅在实现类上额外继承 IbPlugin。
# ---------------------------------------------------------------------------


class IbPlugin(ABC):
    """
    核心层插件基类。

    提供：
    - setup(capabilities) 生命周期钩子，由 ModuleLoader 在加载时调用
    - expose()/revoke() 向 CapabilityRegistry 注册/撤销能力
    - plugin_id 唯一标识符

    非侵入层插件不需要继承此类，直接实现 setup(capabilities) 方法即可。
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
        插件初始化入口。
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

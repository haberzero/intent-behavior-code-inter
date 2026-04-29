"""
ibci_ihost/core.py

IBCI IHost 核心级宿主能力插件实现。

IHost 是 IBCI 核心级插件（Core-Level Plugin）：
- 继承 IbPlugin，通过 setup(capabilities) 注入内核能力
- 通过 capabilities.kernel_registry.get_host_service() 访问内核 HostService
- 向 CapabilityRegistry 注册自身为 "ihost_provider"，供其它插件查找

暴露给 ibci 脚本的能力（通过 import ihost）：
- save_state(path)       持久化当前运行现场
- load_state(path)       恢复运行现场
- run_isolated(path, policy)  在隔离环境中运行另一个 .ibci 脚本
- get_source()           获取当前模块源代码（元编程）
"""
from typing import Any, Dict, Optional
from core.extension.ibcext import IbPlugin, ExtensionCapabilities


class IHostPlugin(IbPlugin):
    """
    IHost 宿主能力插件。

    核心级插件，通过 KernelRegistry.get_host_service() 委托内核 HostService 完成
    所有实际操作，自身不持有任何运行时状态。
    """
    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None

    @property
    def plugin_id(self) -> str:
        return "ibc:ihost"

    def setup(self, capabilities: ExtensionCapabilities) -> None:
        super().setup(capabilities)
        self._capabilities = capabilities
        capabilities.expose("ihost_provider", self)

    # ------------------------------------------------------------------
    # ibci 暴露接口
    # ------------------------------------------------------------------

    def save_state(self, path: str) -> None:
        """持久化当前运行现场到文件。"""
        hs = self._host_service()
        if hs:
            hs.save_state(path)

    def load_state(self, path: str) -> None:
        """从文件恢复运行现场。"""
        hs = self._host_service()
        if hs:
            hs.load_state(path)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> bool:
        """在隔离环境中运行另一个 .ibci 脚本，返回是否成功。"""
        hs = self._host_service()
        if not hs:
            return False
        result = hs.run_isolated(path, policy)
        # HostService.run_isolated 返回 IbObject(bool)；对外统一拆箱为 Python bool
        if hasattr(result, 'get_value'):
            return bool(result.get_value())
        return bool(result)

    def spawn_isolated(self, path: str, policy: Dict[str, Any]) -> str:
        """M4：在隔离后台线程中异步启动另一个 .ibci 脚本，返回 handle 字符串。"""
        hs = self._host_service()
        if not hs:
            return ""
        return hs.spawn_isolated(path, policy)

    def collect(self, handle: str) -> dict:
        """M4：阻塞等待 spawn_isolated 返回的 handle 执行完成，返回子环境导出的变量字典。"""
        hs = self._host_service()
        if not hs:
            return {}
        return hs.collect(handle)

    def get_source(self) -> str:
        """获取当前运行模块的源代码（元编程）。"""
        hs = self._host_service()
        if hs:
            return hs.get_source()
        return ""

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _host_service(self) -> Optional[Any]:
        """通过 KernelRegistry 稳定钩子获取内核 HostService 实例。"""
        if self._capabilities:
            kr = self._capabilities.kernel_registry
            if kr:
                return kr.get_host_service()
        return None


def create_implementation() -> IHostPlugin:
    """工厂函数：创建 IHostPlugin 实例。"""
    return IHostPlugin()

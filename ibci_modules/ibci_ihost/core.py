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
- getenv(key)            读取宿主 OS 环境变量（缺失返回空串）
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

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> "HostAwaitable":
        """在隔离环境中运行另一个 .ibci 脚本，返回可等待句柄（多值 dict）。"""
        hs = self._host_service()
        if not hs:
            raise RuntimeError("IHost service not available; cannot run_isolated.")
        return hs.run_isolated(path, policy)

    def spawn_isolated(self, path: str, policy: Dict[str, Any]) -> str:
        """在隔离后台线程中异步启动另一个 .ibci 脚本，返回 handle 字符串。"""
        hs = self._host_service()
        if not hs:
            raise RuntimeError("IHost service not available; cannot spawn_isolated.")
        return hs.spawn_isolated(path, policy)

    def collect(self, handle: str) -> "HostAwaitable":
        """返回可等待句柄：等待 spawn_isolated 子执行完成，取回子环境导出的变量字典。"""
        hs = self._host_service()
        if not hs:
            raise RuntimeError("IHost service not available; cannot collect.")
        return hs.collect(handle)

    def run_file(self, path: str, policy: Dict[str, Any]) -> "IbRunResult":
        """独立子进程运行另一个 .ibci 文件，捕获执行结果记录 ``run_result``
        （字段 exit_status/stdout/exception；错误作值；stdout 被捕获不经父面）。"""
        hs = self._host_service()
        if not hs:
            raise RuntimeError("IHost service not available; cannot run_file.")
        return hs.run_file(path, policy)

    def run_code(self, code: str, policy: Dict[str, Any]) -> "IbRunResult":
        """独立子进程运行一段 IBCI 代码字符串，捕获执行结果记录 ``run_result``
        （与 run_file 机制同构：同一 spawn 核心字符串源，子 project_root = 父
        project_root；错误作值；stdout 被捕获不经父面）。"""
        hs = self._host_service()
        if not hs:
            raise RuntimeError("IHost service not available; cannot run_code.")
        return hs.run_code(code, policy)

    def get_source(self) -> str:
        """获取当前运行模块的源代码（元编程）。"""
        hs = self._host_service()
        if hs:
            return hs.get_source()
        return ""

    def getenv(self, key: str) -> str:
        """读取宿主 OS 环境变量（缺失返回空串）。"""
        hs = self._host_service()
        if hs:
            return hs.getenv(key)
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

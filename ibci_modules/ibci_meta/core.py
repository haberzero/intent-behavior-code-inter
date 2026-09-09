"""
ibci_modules/ibci_meta/core.py

IBCI Meta 核心级元编程插件实现。

meta 是 IBCI 核心级插件（Core-Level Plugin）：暴露"代码作值"的**编译门**原语
（安全执行架构的编译门：

- ``compile(code)``：代码字符串进程内**编译作值**（compile-only 静态校验，**不执行**）——
  语法/语义错误 fail-fast 抛 ``CompilerError``（diagnostics 带 ibci 源定位：合成 entry
  标记 + line/column），成功静默（void）。与 CLI ``check`` 面同构。

meta 通过 capabilities.kernel_registry.get_host_service() 委托内核 HostService
（meta_compile）——自身不持有运行时状态（同 ihost 模式）。
"""
from core.extension.ibcext import IbPlugin, ExtensionCapabilities
from typing import Optional


class MetaPlugin(IbPlugin):
    """Meta 元编程插件（编译门原语）。"""

    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None

    @property
    def plugin_id(self) -> str:
        return "ibc:meta"

    def setup(self, capabilities: ExtensionCapabilities) -> None:
        super().setup(capabilities)
        self._capabilities = capabilities

    # ------------------------------------------------------------------
    # ibci 暴露接口
    # ------------------------------------------------------------------

    def compile(self, code: str) -> None:
        """代码字符串进程内编译校验（compile-only，**不执行**）。

        语法/语义错误 fail-fast 抛 ``CompilerError``（diagnostics 带 ibci 源定位：
        合成 entry ``__string_exec__`` 标记 + line/column）；成功静默返回（void）。
        经 HostService.meta_compile：子引擎 compile-only（零父状态污染）。
        """
        hs = self._host_service()
        if not hs:
            raise RuntimeError("Meta service not available; cannot meta.compile.")
        hs.meta_compile(code)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _host_service(self) -> Optional[object]:
        """通过 KernelRegistry 稳定钩子获取内核 HostService 实例。"""
        if self._capabilities:
            kr = self._capabilities.kernel_registry
            if kr:
                return kr.get_host_service()
        return None


def create_implementation() -> MetaPlugin:
    """工厂函数：创建 MetaPlugin 实例。"""
    return MetaPlugin()

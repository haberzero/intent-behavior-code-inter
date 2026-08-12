"""
ibci_isys/core.py

IBCI ISys 核心级系统状态与控制插件实现。

与 Python 标准库的 sys 模块类似，isys 是 IBCI 脚本与解释器/运行时环境
进行交互的统一入口，包含两类能力：

【路径信息】
- entry_path()         → 入口文件绝对路径
- entry_dir()          → 入口文件所在目录（所有相对路径的解析基准）
- project_root()       → 项目根目录（沙箱边界）

【沙箱控制】
- is_sandboxed()       → 当前是否处于沙箱模式
- request_external_access()  → 请求启用外部访问权限

isys 是核心级插件：通过 setup(capabilities) 注入 ExecutionContext 和
PermissionManager，无需继承 IbPlugin（功能所需内核能力较浅）。
"""
from typing import Optional, Any


class ISysLib:
    """
    ISys 2.0: IBCI 运行时状态与系统控制模块。

    路径查询（isys）与沙箱控制（sys）两大能力域。
    """

    def __init__(self):
        self._capabilities: Optional[Any] = None
        self._permission_manager: Optional[Any] = None

    def setup(self, capabilities) -> None:
        self._capabilities = capabilities
        # PluginCapabilities.service_context / PermissionManager 由 loader 在
        # setup() 前无条件注入（契约保证字段恒在）——直访契约，注入缺失即 fail-fast。
        self._permission_manager = capabilities.service_context.permission_manager

    # ------------------------------------------------------------------
    # 路径信息
    # ------------------------------------------------------------------

    def entry_path(self) -> str:
        """获取入口文件的绝对路径。"""
        return self._capabilities.execution_context.get_entry_path() or ""

    def entry_dir(self) -> str:
        """获取入口文件所在的目录（相对路径解析基准）。"""
        return self._capabilities.execution_context.get_entry_dir() or ""

    def project_root(self) -> str:
        """获取项目根目录（沙箱边界）。"""
        return self._permission_manager.root_dir or ""

    # ------------------------------------------------------------------
    # 沙箱控制
    # ------------------------------------------------------------------

    def is_sandboxed(self) -> bool:
        """检查当前是否在沙箱模式下运行。"""
        pm = self._permission_manager
        if pm is None:
            return True  # 权限管理器不可用（契约外状态）时默认沙箱开启（安全优先）
        return not pm.is_external_access_enabled()

    def request_external_access(self) -> None:
        """请求启用外部访问权限（允许访问项目目录之外的文件）。"""
        pm = self._permission_manager
        if pm is None:
            raise RuntimeError(
                "isys.request_external_access: permission manager not available"
            )
        pm.enable_external_access()


def create_implementation() -> ISysLib:
    """工厂函数：创建 ISysLib 实例。"""
    return ISysLib()

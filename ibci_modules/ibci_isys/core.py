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

    合并自原 ibci_isys（路径查询）与 ibci_sys（沙箱控制）两个模块。
    """

    def __init__(self):
        self._capabilities: Optional[Any] = None
        self._permission_manager: Optional[Any] = None

    def setup(self, capabilities) -> None:
        self._capabilities = capabilities
        # PermissionManager 通过 service_context 注入
        sc = getattr(capabilities, 'service_context', None)
        if sc:
            self._permission_manager = getattr(sc, 'permission_manager', None)

    # ------------------------------------------------------------------
    # 路径信息
    # ------------------------------------------------------------------

    def entry_path(self) -> str:
        """获取入口文件的绝对路径。"""
        ec = getattr(self._capabilities, 'execution_context', None)
        if ec:
            path = ec.get_entry_path()
            return path if path else ""
        return ""

    def entry_dir(self) -> str:
        """获取入口文件所在的目录（相对路径解析基准）。"""
        ec = getattr(self._capabilities, 'execution_context', None)
        if ec:
            path = ec.get_entry_dir()
            return path if path else ""
        return ""

    def project_root(self) -> str:
        """获取项目根目录（沙箱边界）。"""
        pm = self._permission_manager
        if pm:
            return getattr(pm, 'root_dir', None) or ""
        return ""

    # ------------------------------------------------------------------
    # 沙箱控制
    # ------------------------------------------------------------------

    def is_sandboxed(self) -> bool:
        """检查当前是否在沙箱模式下运行。"""
        pm = self._permission_manager
        if pm and hasattr(pm, 'is_external_access_enabled'):
            return not pm.is_external_access_enabled()
        return True  # 无法获取时默认沙箱开启（安全优先）

    def request_external_access(self) -> None:
        """请求启用外部访问权限（允许访问项目目录之外的文件）。"""
        pm = self._permission_manager
        if pm and hasattr(pm, 'enable_external_access'):
            pm.enable_external_access()


def create_implementation() -> ISysLib:
    """工厂函数：创建 ISysLib 实例。"""
    return ISysLib()

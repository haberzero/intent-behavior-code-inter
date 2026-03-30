"""
[IES 2.2] Sys 系统能力插件

纯 Python 实现，零侵入。
最小版本暂时绕过沙箱权限管理。
"""


class SysLib:
    """
    [IES 2.2] Sys 2.2: 系统能力插件。
    具备对运行时栈和路径环境的查询能力。
    """
    def setup(self, capabilities):
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager

    def request_external_access(self) -> None:
        self.permission_manager.enable_external_access()

    def is_sandboxed(self) -> bool:
        return not self.permission_manager.is_external_access_enabled()

    def script_dir(self) -> str:
        """获取当前脚本所在的绝对目录"""
        return self.capabilities.stack_inspector.get_current_script_dir() or ""

    def script_path(self) -> str:
        """获取当前脚本的绝对路径"""
        return self.capabilities.stack_inspector.get_current_script_path() or ""

    def project_root(self) -> str:
        """获取项目工作空间的根目录"""
        return self.permission_manager.root_dir


def create_implementation():
    return SysLib()

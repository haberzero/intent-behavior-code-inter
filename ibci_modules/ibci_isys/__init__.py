"""
Isys (IBCI System) 内核运行时状态插件

这是 IBCI 的核心运行时模块，负责：
- 入口文件路径管理
- 项目根目录查询
- 运行时状态查询

作为内核侵入式插件，它与 ExecutionContext 紧密配合。
所有 IBCI 脚本都可以访问这个模块来查询运行时状态。
"""


class ISysLib:
    """
    ISys 1.0: IBCI 内核运行时状态模块。

    职责：
    - 入口文件路径（entry_path, entry_dir）
    - 项目根目录（project_root）
    - 运行时状态查询

    特点：
    - 与 ExecutionContext 紧密耦合
    - 通过 capabilities.execution_context 访问
    - 所有 IBCI 脚本共享同一实例
    """
    def setup(self, capabilities):
        self.capabilities = capabilities

    def entry_path(self) -> str:
        """
        获取入口文件的绝对路径。

        这是 IBCI 程序启动时的入口文件路径。
        所有相对路径都基于这个路径所在的目录。
        """
        ec = self.capabilities.execution_context
        if ec:
            path = ec.get_entry_path()
            return path if path else ""
        return ""

    def entry_dir(self) -> str:
        """
        获取入口文件所在的目录。

        这是所有相对路径解析的基准目录。
        无论在哪个 IBCI 文件中执行，相对路径都相对于这个目录。
        """
        ec = self.capabilities.execution_context
        if ec:
            path = ec.get_entry_dir()
            return path if path else ""
        return ""

    def project_root(self) -> str:
        """
        获取项目根目录。

        项目根目录是包含 plugins/ 或 ibci_modules/ 的目录。
        这是沙箱的边界。
        """
        pm = self.capabilities.permission_manager
        if pm:
            return pm.root_dir or ""
        return ""


def create_implementation():
    """工厂函数"""
    return ISysLib()

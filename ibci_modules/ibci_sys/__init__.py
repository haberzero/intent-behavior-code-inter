class SysLib:
    """
    职责：
    - 请求外部访问权限
    - 检查沙箱状态
    """
    def setup(self, capabilities):
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager

    def request_external_access(self) -> None:
        """
        请求启用外部访问权限。

        调用此方法后，沙箱将允许访问项目根目录之外的文件。
        注意：这可能带来安全风险。
        """
        self.permission_manager.enable_external_access()

    def is_sandboxed(self) -> bool:
        """
        检查当前是否在沙箱模式运行。

        返回:
            bool: 如果启用沙箱限制返回 True，否则返回 False
        """
        return not self.permission_manager.is_external_access_enabled()


def create_implementation():
    """工厂函数"""
    return SysLib()

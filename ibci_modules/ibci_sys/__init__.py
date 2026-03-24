"""
[IES 2.2] Sys 系统能力插件

纯 Python 实现，零侵入。
最小版本暂时绕过沙箱权限管理。
"""


class SysLib:
    """
    [IES 2.2] Sys 2.2: 系统能力插件。
    不继承任何核心类，完全独立。
    最小版本：暂时不提供沙箱控制。
    """
    def request_external_access(self) -> None:
        pass

    def is_sandboxed(self) -> bool:
        return False


def create_implementation():
    return SysLib()

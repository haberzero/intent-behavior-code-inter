from typing import Optional
from core.extension import ibcext

class SysLib(ibcext.IbPlugin):
    """
    Sys 2.1: 系统能力插件。
    """
    def __init__(self):
        super().__init__()

    @ibcext.method("request_external_access")
    def request_external_access(self) -> None:
        pm = self._capabilities.permission_manager
        if pm:
            pm.enable_external_access()

    @ibcext.method("is_sandboxed")
    def is_sandboxed(self) -> bool:
        pm = self._capabilities.permission_manager
        return not pm.is_external_access_enabled() if pm else True

def create_implementation():
    return SysLib()

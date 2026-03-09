from typing import Optional
from core.runtime.interfaces import PermissionManager
from core.extension import sdk as ibci

class SysLib:
    def __init__(self):
        self._permission_manager: Optional[PermissionManager] = None

    def setup(self, permission_manager: PermissionManager):
        self._permission_manager = permission_manager

    @ibci.method("request_external_access")
    def request_external_access(self) -> None:
        self._permission_manager.enable_external_access()
        
    @ibci.method("is_sandboxed")
    def is_sandboxed(self) -> bool:
        return not self._permission_manager.is_external_access_enabled()

def create_implementation():
    return SysLib()

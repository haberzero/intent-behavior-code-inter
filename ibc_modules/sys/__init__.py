from typing import Optional
from core.runtime.interpreter.interfaces import PermissionManager

class SysLib:
    def __init__(self):
        self._permission_manager: Optional[PermissionManager] = None

    def setup(self, permission_manager: PermissionManager):
        self._permission_manager = permission_manager

    def request_external_access(self) -> None:
        self._permission_manager.enable_external_access()
        
    def is_sandboxed(self) -> bool:
        return not self._permission_manager.is_external_access_enabled()

def create_implementation():
    return SysLib()

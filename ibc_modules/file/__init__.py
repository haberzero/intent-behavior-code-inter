import os
from typing import Optional
from utils.interpreter.interfaces import PermissionManager

class FileLib:
    def __init__(self):
        self._permission_manager: Optional[PermissionManager] = None

    def setup(self, permission_manager: PermissionManager):
        self._permission_manager = permission_manager

    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self._permission_manager.root_dir, path)

    def read(self, path: str) -> str:
        full_path = self._resolve_path(path)
        self._permission_manager.validate_path(full_path, "read")
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
            
    def write(self, path: str, content: str) -> None:
        full_path = self._resolve_path(path)
        self._permission_manager.validate_path(full_path, "write")
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    def exists(self, path: str) -> bool:
        full_path = self._resolve_path(path)
        self._permission_manager.validate_path(full_path, "check existence")
        return os.path.exists(full_path)

# In runtime, register_stdlib will create an instance and call setup
def create_implementation():
    return FileLib()

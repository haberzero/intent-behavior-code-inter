import os
from typing import Optional
from core.extension import ibcext

class FileLib(ibcext.IbPlugin):
    """
    File 2.1: 文件操作插件。
    """
    def __init__(self):
        super().__init__()

    def _resolve_path(self, path: str) -> str:
        pm = self._capabilities.permission_manager
        if os.path.isabs(path):
            return path
        return os.path.join(pm.root_dir, path) if pm else path

    @ibcext.method("read")
    def read(self, path: str) -> str:
        pm = self._capabilities.permission_manager
        full_path = self._resolve_path(path)
        if pm: pm.validate_path(full_path, "read")
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()

    @ibcext.method("write")
    def write(self, path: str, content: str) -> None:
        pm = self._capabilities.permission_manager
        full_path = self._resolve_path(path)
        if pm: pm.validate_path(full_path, "write")
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    @ibcext.method("exists")
    def exists(self, path: str) -> bool:
        pm = self._capabilities.permission_manager
        full_path = self._resolve_path(path)
        if pm: pm.validate_path(full_path, "check existence")
        return os.path.exists(full_path)

def create_implementation():
    return FileLib()

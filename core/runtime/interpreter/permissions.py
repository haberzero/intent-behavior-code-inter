import os
from typing import Optional
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject
from core.runtime.path import IbPath, PathValidator


class PermissionManager:
    """
    Manages runtime permissions and path sandboxing for IBC-Inter.

    使用 IBCI PathValidator 进行安全验证，完全独立于 Python os.path。
    """
    def __init__(self, root_dir: str):
        self.root_dir = os.path.realpath(root_dir)
        self._external_access_enabled = False
        self._root_path = IbPath.from_native(self.root_dir)

    def enable_external_access(self):
        """
        Enables access to files outside the root directory.
        Should be used with caution.
        """
        self._external_access_enabled = True

    def disable_external_access(self):
        self._external_access_enabled = False

    def is_external_access_enabled(self) -> bool:
        return self._external_access_enabled

    def validate_path(self, path: str, operation: str = "access"):
        """
        Validates if the given path is allowed to be accessed.

        使用 IBCI PathValidator 进行安全验证，完全独立于 Python os.path.commonpath()。

        参数:
            path: 要验证的路径（字符串）
            operation: 操作类型（用于错误信息）
        """
        abs_path = os.path.realpath(path)

        if self._external_access_enabled:
            return

        ib_path = IbPath.from_native(abs_path)

        is_valid, error_msg = PathValidator.validate(
            ib_path, self._root_path, allow_external=False
        )

        if not is_valid:
            raise InterpreterError(
                f"Security Error: Permission denied for {operation} on path outside workspace: {path}. "
                f"IBC-Inter is currently restricted to its root directory."
            )

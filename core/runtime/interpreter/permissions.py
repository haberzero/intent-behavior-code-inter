import os
from typing import Optional
from core.types.exception_types import InterpreterError

class PermissionManager:
    """
    Manages runtime permissions and path sandboxing for IBC-Inter.
    """
    def __init__(self, root_dir: str):
        self.root_dir = os.path.realpath(root_dir)
        self._external_access_enabled = False

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
        If external access is disabled, the path must be within root_dir.
        """
        abs_path = os.path.realpath(path)
        
        if self._external_access_enabled:
            # Audit log could be added here
            return

        try:
            if os.path.commonpath([self.root_dir, abs_path]) != self.root_dir:
                raise InterpreterError(
                    f"Security Error: Permission denied for {operation} on path outside workspace: {path}. "
                    f"IBC-Inter is currently restricted to its root directory."
                )
        except ValueError:
             # This can happen on Windows if drives are different
             raise InterpreterError(
                f"Security Error: Permission denied for {operation} (drive mismatch): {path}. "
                f"IBC-Inter is currently restricted to its root directory."
             )

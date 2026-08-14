from typing import Optional
from core.base.diagnostics.codes import RUN_PERMISSION_ERROR
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject
from core.kernel.path import IbPath, PathValidator


class PermissionManager:
    """
    Manages runtime permissions and path sandboxing for IBC-Inter.

    使用 IBCI PathValidator 进行安全验证，完全独立于 Python os.path。
    """
    def __init__(self, root_dir: str):
        # root_dir 已由 engine 规范化，消费者信任，仅 IbPath 包装。
        self._project_root = IbPath.from_native(root_dir)
        self.root_dir = root_dir
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

        经 IBCI PathValidator 统一沙箱检查（全仓唯一沙箱实现）。

        参数:
            path: 要验证的路径（字符串）
            operation: 操作类型（用于错误信息）
        """
        ib_path = PathValidator.canonicalize_for_security(path)

        if self._external_access_enabled:
            return

        is_valid, error_msg = PathValidator.validate(
            ib_path, self._project_root, allow_external=False
        )

        if not is_valid:
            raise InterpreterError(
                f"Security Error: Permission denied for {operation} on path outside workspace: {path}. "
                f"IBC-Inter is currently restricted to its root directory.",
                error_code=RUN_PERMISSION_ERROR,
            )

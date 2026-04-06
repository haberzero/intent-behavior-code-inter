"""
IBCI Path Validator - 路径安全验证器

完全独立于 Python os.path.commonpath() 实现路径安全验证。
提供沙箱边界检查和路径安全性验证。
"""
from typing import Tuple
from .ib_path import IbPath


class PathValidator:
    """
    IBCI 路径安全验证器

    完全独立于 Python os.path.commonpath()，实现跨平台的路径安全验证。
    用于沙箱边界检查和权限管理。
    """

    @staticmethod
    def is_within(parent: IbPath, child: IbPath) -> bool:
        """
        检查 child 是否在 parent 内部

        这是 PathValidator 的核心方法，替代 Python 的 os.path.commonpath()。

        参数:
            parent: 父路径（边界）
            child: 子路径（要检查的路径）

        返回:
            bool: child 是否在 parent 内部
        """
        if not parent or not child:
            return False

        if not parent.is_absolute or not child.is_absolute:
            return False

        return child.startswith(parent)

    @staticmethod
    def validate(
        path: IbPath,
        project_root: IbPath,
        allow_external: bool = False
    ) -> Tuple[bool, str]:
        """
        验证路径安全性

        参数:
            path: 要验证的路径
            project_root: 项目根目录（沙箱边界）
            allow_external: 是否允许外部访问

        返回:
            (is_valid, error_message): 验证结果和错误信息
        """
        if not path:
            return False, "Path is empty"

        if not path.is_absolute:
            return False, f"Path must be absolute for security check: {path}"

        if allow_external:
            return True, ""

        if not PathValidator.is_within(project_root, path):
            return False, f"Path '{path}' is outside project root '{project_root}'"

        return True, ""

    @staticmethod
    def normalize(path: str) -> IbPath:
        """
        路径规范化

        参数:
            path: 原始路径

        返回:
            IbPath: 规范化后的路径
        """
        return IbPath.from_native(path)

    @staticmethod
    def validate_many(
        paths: list,
        project_root: IbPath,
        allow_external: bool = False
    ) -> Tuple[bool, str, list]:
        """
        批量验证路径安全性

        参数:
            paths: 要验证的路径列表
            project_root: 项目根目录
            allow_external: 是否允许外部访问

        返回:
            (all_valid, first_error, failed_paths): 全部验证结果、第一个错误、所有失败路径
        """
        failed_paths = []

        for path in paths:
            is_valid, error_msg = PathValidator.validate(
                path, project_root, allow_external
            )
            if not is_valid:
                failed_paths.append((path, error_msg))

        if failed_paths:
            first_path, first_error = failed_paths[0]
            return False, first_error, failed_paths

        return True, "", []

    @staticmethod
    def is_safe_name(name: str) -> bool:
        """
        检查文件名/目录名是否安全

        参数:
            name: 文件或目录名

        返回:
            bool: 是否安全
        """
        if not name:
            return False

        dangerous_chars = ["..", "/", "\\", "\0", "\n", "\r"]
        for char in dangerous_chars:
            if char in name:
                return False

        if name.startswith("."):
            return True

        if name in ["CON", "PRN", "AUX", "NUL",
                    "COM1", "COM2", "COM3", "COM4",
                    "LPT1", "LPT2", "LPT3"]:
            return False

        return True

    @staticmethod
    def get_containing_directory(path: IbPath) -> IbPath:
        """
        获取路径的包含目录

        参数:
            path: 路径

        返回:
            IbPath: 包含目录
        """
        if path.is_absolute:
            parent = path.parent
            return parent if parent else path
        else:
            resolved = path.resolve_dot_segments()
            return resolved.parent if resolved.parent else resolved

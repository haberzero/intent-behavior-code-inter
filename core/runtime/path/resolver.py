"""
IBCI Path Resolver - 路径解析服务

提供 IBCI 三层路径语义的统一解析：
1. 绝对路径 - 以 / 或盘符开头
2. 脚本相对路径 - 以 ./ 或 ../ 开头
3. 项目相对路径 - 其他所有情况
"""
from typing import Optional
from .ib_path import IbPath


class PathResolver:
    """
    IBCI 路径解析器

    提供统一的路径解析能力，支持三种路径语义：
    - 绝对路径：直接返回
    - 脚本相对路径：以 ./ 或 ../ 开头，相对于当前脚本位置
    - 项目相对路径：相对于项目根目录
    """

    def __init__(
        self,
        project_root: IbPath,
        script_dir: Optional[IbPath] = None
    ):
        """
        初始化路径解析器

        参数:
            project_root: 项目根目录（必须是绝对路径）
            script_dir: 当前脚本所在目录（可选，用于脚本相对路径）
        """
        self._project_root = project_root
        self._script_dir = script_dir

    @property
    def project_root(self) -> IbPath:
        """获取项目根目录"""
        return self._project_root

    @property
    def script_dir(self) -> Optional[IbPath]:
        """获取脚本目录"""
        return self._script_dir

    def resolve(self, path: str) -> IbPath:
        """
        统一路径解析

        这是 IBCI 路径解析的核心方法，根据路径类型选择不同的解析策略。

        参数:
            path: 原始路径字符串（可以是任意格式）

        返回:
            IbPath: 解析后的绝对路径
        """
        if not path:
            return IbPath.from_native("")

        ib_path = IbPath.from_native(path)

        if ib_path.is_absolute:
            return self._resolve_absolute(ib_path)

        if path.startswith("./") or path.startswith("../"):
            if self._script_dir:
                return self._resolve_script_relative(ib_path, path)

        return self._resolve_project_relative(ib_path, path)

    def _resolve_absolute(self, path: IbPath) -> IbPath:
        """解析绝对路径"""
        return path.resolve_dot_segments()

    def _resolve_script_relative(self, path: IbPath, original: str) -> IbPath:
        """解析脚本相对路径"""
        if not self._script_dir:
            return self._resolve_project_relative(path, original)

        if original.startswith("../"):
            parent_count = 0
            remaining = original
            while remaining.startswith("../"):
                parent_count += 1
                remaining = remaining[3:]

            result = self._script_dir
            for _ in range(parent_count):
                if result.parent:
                    result = result.parent
                else:
                    break

            if remaining:
                result = result / remaining

            return result.resolve_dot_segments()

        if original.startswith("./"):
            remaining = original[2:] if original.startswith("./") else original
            return (self._script_dir / remaining).resolve_dot_segments()

        return (self._script_dir / original).resolve_dot_segments()

    def _resolve_project_relative(self, path: IbPath, original: str) -> IbPath:
        """解析项目相对路径"""
        if not self._project_root:
            return path.resolve_dot_segments()

        resolved = (self._project_root / original).resolve_dot_segments()
        return resolved

    def is_within_project(self, path: IbPath) -> bool:
        """
        检查路径是否在项目内

        参数:
            path: 要检查的路径

        返回:
            bool: 是否在项目内
        """
        if not self._project_root or not path:
            return False

        return path.startswith(self._project_root)

    def make_relative_to_project(self, path: IbPath) -> IbPath:
        """
        将绝对路径转换为项目相对路径

        参数:
            path: 要转换的绝对路径

        返回:
            IbPath: 项目相对路径（如果路径在项目内）
                    原始路径（如果路径在项目外）
        """
        if not self._project_root or not path:
            return path

        if path.startswith(self._project_root):
            project_relative = path._normalized[len(self._project_root._normalized):]
            if project_relative.startswith("/"):
                project_relative = project_relative[1:]
            return IbPath.from_native(project_relative)

        return path

    def make_relative_to_script(self, path: IbPath) -> Optional[IbPath]:
        """
        将绝对路径转换为脚本相对路径

        参数:
            path: 要转换的绝对路径

        返回:
            IbPath: 脚本相对路径（如果可计算）
                    None（如果没有脚本目录信息）
        """
        if not self._script_dir or not path:
            return None

        if path.startswith(self._script_dir):
            script_relative = path._normalized[len(self._script_dir._normalized):]
            if script_relative.startswith("/"):
                script_relative = script_relative[1:]
            return IbPath.from_native("./" + script_relative)

        return None

    def resolve_many(self, *paths: str) -> list:
        """
        批量解析路径

        参数:
            *paths: 要解析的多个路径

        返回:
            list[IbPath]: 解析后的路径列表
        """
        return [self.resolve(p) for p in paths]

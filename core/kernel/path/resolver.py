"""
IBCI Path Resolver - 路径解析服务（规范解析器）

本解析器采用 **entry_dir 单锚点语义**：
"所有相对路径都基于入口文件目录解析，无论在哪个 IBCI 文件中执行"。

这是 IBCI 的**唯一**规范路径解析器。所有需要把相对路径解析为绝对路径的站点
（ExecutionContext.resolve_path、HostService._resolve_isolated_path 等）都应委托本类，
不得各自手搓 os.path.abspath/join。
"""
from __future__ import annotations

from typing import Optional

from core.base.path import IbPath


class PathResolver:
    """
    IBCI 规范路径解析器（entry_dir 单锚点）。

    解析规则：
    1. **绝对路径**（以 ``/`` 或盘符开头）：直接 ``resolve_dot_segments`` 规范化返回。
    2. **相对路径**：锚定到 ``entry_dir``，即 ``(entry_dir / rel).resolve_dot_segments()``。
    3. 若 ``entry_dir`` 未提供（早期/孤立场景）：相对路径仅做 ``resolve_dot_segments``，
       不强行锚定（保持可预测，不悄悄退回 CWD）。

    设计原则：
    - **不使用 ``os.getcwd()`` 兜底**（CWD 是隐式全局状态，违反"显式优于隐式"）。
    - **不区分 ``./`` ``../`` 与普通相对**——所有相对路径统一锚定 entry_dir（契约）。
      ``..`` 由 ``resolve_dot_segments`` 处理。
    - 全程基于 ``IbPath``，零 ``os.path`` 调用（与 Python 路径世界解耦）。
    """

    def __init__(self, entry_dir: Optional[IbPath] = None):
        """
        参数:
            entry_dir: 入口文件所在目录（IbPath）。所有相对路径将锚定于此。
                       None 表示无入口上下文（孤立场景）；此时相对路径仅规范化、不锚定。
        """
        if entry_dir is not None and not isinstance(entry_dir, IbPath):
            entry_dir = IbPath.from_native(entry_dir)
        self._entry_dir = entry_dir

    @property
    def entry_dir(self) -> Optional[IbPath]:
        """入口目录（可能为 None）。"""
        return self._entry_dir

    def resolve(self, path: str) -> IbPath:
        """
        统一路径解析入口（契约的唯一实现）。

        参数:
            path: 原始路径字符串（任意格式）

        返回:
            IbPath: 解析后的（规范化）路径。空字符串返回空 IbPath。
        """
        if not path:
            return IbPath.from_native("")

        ib_path = IbPath.from_native(path)

        if ib_path.is_absolute:
            return ib_path.resolve_dot_segments()

        if self._entry_dir is not None:
            return (self._entry_dir / ib_path).resolve_dot_segments()

        # 无入口上下文：仅规范化，不锚定（不悄悄退回 CWD）
        return ib_path.resolve_dot_segments()

    def is_within_entry(self, path: IbPath) -> bool:
        """检查 path 是否位于 entry_dir 内部（无 entry_dir 时返回 False）。"""
        if self._entry_dir is None or not path:
            return False
        if not path.is_absolute:
            path = self.resolve(path.to_native())
        return path.startswith(self._entry_dir)

    def make_relative_to_entry(self, path: IbPath) -> Optional[IbPath]:
        """
        将绝对路径转换为相对 entry_dir 的路径。

        返回:
            IbPath: 相对路径；若 path 不在 entry_dir 内或无 entry_dir，返回 None。
        """
        if self._entry_dir is None or not path:
            return None
        if not path.startswith(self._entry_dir):
            return None
        entry_str = self._entry_dir._normalized
        rel = path._normalized[len(entry_str):]
        if rel.startswith("/"):
            rel = rel[1:]
        return IbPath.from_native(rel)

    def resolve_many(self, *paths: str) -> list:
        """批量解析路径。"""
        return [self.resolve(p) for p in paths]

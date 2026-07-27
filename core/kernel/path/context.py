"""
IBCI PathContext - 执行上下文路径锚点（canonical）。

本值对象是统一的锚点容器——Engine 构造一次，向下传递；消费者不再各自派生/规范化。

两个锚点：
- ``entry_dir``：入口文件所在目录——**数据路径解析的锚**（契约）。
- ``project_root``：项目根目录——**沙箱边界 + 插件发现的锚**。

二者关系：``project_root`` 通常是 ``entry_dir`` 的祖先（由 ProjectDetector 向上探测），
退化时（无项目标记）等于 ``entry_dir``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.base.path import IbPath
from .resolver import PathResolver


@dataclass(frozen=True)
class PathContext:
    """
    不可变路径锚点容器。

    所有路径消费者（compiler scheduler / module resolver / runtime permissions /
    host service 等）应接收本对象，而非各自持有 ``root_dir: str``。
    """

    entry_dir: IbPath
    project_root: IbPath

    def __post_init__(self):
        if not isinstance(self.entry_dir, IbPath):
            object.__setattr__(self, "entry_dir", IbPath.from_native(self.entry_dir))
        if not isinstance(self.project_root, IbPath):
            object.__setattr__(self, "project_root", IbPath.from_native(self.project_root))

    @classmethod
    def from_native(cls, entry_dir: str, project_root: Optional[str] = None) -> "PathContext":
        """
        从原生字符串构造（自动规范为 IbPath）。

        参数:
            entry_dir: 入口目录（任意路径格式）
            project_root: 项目根；None 时退化等于 entry_dir
        """
        entry = IbPath.from_native(entry_dir)
        root = IbPath.from_native(project_root) if project_root else entry
        return cls(entry_dir=entry, project_root=root)

    def resolver(self) -> PathResolver:
        """构造规范路径解析器（entry_dir 单锚点）。"""
        return PathResolver(entry_dir=self.entry_dir)

    def with_entry(self, entry_dir: str) -> "PathContext":
        """派生一个新 PathContext（换 entry_dir，project_root 不变）。"""
        return PathContext(entry_dir=IbPath.from_native(entry_dir), project_root=self.project_root)

    @staticmethod
    def derive_isolated(child_entry: str) -> tuple:
        """
        派生子隔离执行上下文的路径锚点。

        本方法仅做路径派生（子 project_root = 子入口所在目录），**不**做隔离策略校验。
        隔离策略校验（子 entry 必须在父 project_root 内）在调用方
        ``IBCIEngine._validate_and_derive_isolated`` 完成——保持派生与策略分离。

        子 project_root = 子入口所在目录（保证子入口始终在子沙箱内、可被编译）。

        参数:
            child_entry: 子入口文件路径

        返回:
            (resolved_entry: str, child_project_root: str) —— 解析后的子入口与子沙箱根。
            未来若改为显式 ``policy["sandbox"]`` 指定，仅改本方法。
        """
        child_ib = IbPath.from_native(child_entry).resolve_dot_segments()
        parent = child_ib.parent
        child_root = parent if parent is not None else child_ib
        return (child_ib.to_native(), child_root.to_native())

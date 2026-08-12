"""
core/runtime/objects/media_backing.py

磁盘型多模态/文件对象的 backing 抽象。

设计原则
--------
- ``MediaBacking`` 只持有 ``IbPath``，不持有字节、不持有 OS fd。
- ``FileBacking`` 指向已存在的、经沙箱校验的源文件。
- ``GeneratedBacking`` 指向 LLM 生成时溢写的工件文件。
- 无 ``MemoryBacking``。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.base.path import IbPath


class MediaBacking(ABC):
    """文件容器对象的抽象 backing：一个不可变的路径引用。"""

    @property
    @abstractmethod
    def path(self) -> IbPath:
        """返回 backing 指向的 IbPath。"""
        ...


class FileBacking(MediaBacking):
    """指向已存在源文件的 backing（如 ``audio.from_file(path)`` 的返回值）。"""

    def __init__(self, path: IbPath, sandboxed: bool = True):
        self._path = path
        self._sandboxed = sandboxed

    @property
    def path(self) -> IbPath:
        return self._path

    @property
    def sandboxed(self) -> bool:
        return self._sandboxed

    def __repr__(self) -> str:
        return f"FileBacking(path={self._path!r}, sandboxed={self._sandboxed})"


class GeneratedBacking(MediaBacking):
    """指向 LLM 生成工件文件的 backing（未来生成音频/图像/视频时使用）。"""

    def __init__(self, path: IbPath):
        self._path = path

    @property
    def path(self) -> IbPath:
        return self._path

    def __repr__(self) -> str:
        return f"GeneratedBacking(path={self._path!r})"

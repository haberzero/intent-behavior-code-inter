"""
IBCI InstallPaths - 内置模块/安装根路径服务（canonical）。

Per ADR-015 D3：本服务是 IBCI 安装根（"ibci_modules 在哪"）的**唯一**计算点。
历史上 4 处独立用 ``__file__`` 遍历（3 种不同公式）计算此路径，导致碎片化。
所有需要内置模块路径的站点都应委托本服务。

设计原则：
- 计算一次，缓存复用（安装根在进程生命周期内不变）。
- 零 ``os.path`` 在调用方——本服务是 IBCI 与 Python ``__file__`` 的唯一交互点。
- 返回 ``IbPath``，与统一路径体系一致。

命名（ADR-020 §E）：原 ``BuiltinPaths``（"builtin" 一词五义之一）→ ``InstallPaths``，
精确表达"安装根路径"语义。
"""
from __future__ import annotations

from typing import Optional

from core.base.path import IbPath


class InstallPaths:
    """
    安装路径服务（单例式缓存）。

    提供：
    - ``install_root``：IBCI 安装根目录（ibci_modules 的父目录，即仓库根）。
    - ``modules_dir``：内置模块目录（``<install_root>/ibci_modules``）。
    - ``plugins_dir``：内置插件目录占位（``<install_root>/plugins``，可能不存在）。
    """

    _install_root: Optional[IbPath] = None

    @classmethod
    def _compute_install_root(cls) -> IbPath:
        """经 ``ibci_modules.__file__`` 定位安装根（标准 Python 包定位惯用法）。"""
        import ibci_modules
        module_file = getattr(ibci_modules, "__file__", None)
        if module_file is None:
            # 包没有 __file__（ namespace package 或打包场景）：退回 core 的祖父目录
            import core
            core_file = getattr(core, "__file__", None)
            if core_file is None:
                raise RuntimeError("InstallPaths: cannot determine install root (no __file__)")
            # core/ 的父目录即安装根
            core_dir = IbPath.from_native(core_file).parent
            return core_dir.parent if core_dir.parent is not None else core_dir
        # ibci_modules/__init__.py 的父目录的父目录 = 安装根
        module_dir = IbPath.from_native(module_file).parent
        return module_dir.parent if module_dir.parent is not None else module_dir

    @classmethod
    def install_root(cls) -> IbPath:
        """IBCI 安装根目录（缓存）。"""
        if cls._install_root is None:
            cls._install_root = cls._compute_install_root()
        return cls._install_root

    @classmethod
    def modules_dir(cls) -> IbPath:
        """内置模块目录（``<install_root>/ibci_modules``）。"""
        root = cls.install_root()
        return root / "ibci_modules"

    @classmethod
    def plugins_dir(cls) -> IbPath:
        """内置插件目录占位（``<install_root>/plugins``，可能不存在）。"""
        root = cls.install_root()
        return root / "plugins"

    @classmethod
    def _reset_cache(cls) -> None:
        """重置缓存（仅测试用）。"""
        cls._install_root = None

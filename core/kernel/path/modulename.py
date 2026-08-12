"""
IBCI ModuleNameSpace - 模块名 ↔ 相对路径映射服务（canonical）。

本服务是模块名与相对路径互转的唯一规范实现。

约定：
- IBCI 模块名以 ``.`` 分隔（如 ``pkg.sub.mod``）。
- 对应的相对路径以 ``/`` 分隔（如 ``pkg/sub/mod``）——与 ``IbPath.SEPARATOR`` 一致。
- 与 OS 分隔符 ``os.sep`` **完全解耦**：本服务永远在 IBCI 语义层操作，
  只在最终与文件系统交互时由 ``IbPath.to_native()`` 转换。
"""
from __future__ import annotations

from core.base.path import IbPath

# IBCI 模块名分隔符（语义层，不随 OS 变化）
MODULE_SEPARATOR = "."
PATH_SEPARATOR = IbPath.SEPARATOR  # "/" — IbPath 内部规范分隔符


class ModuleNameSpace:
    """
    模块名 ↔ 相对路径互转服务（OS-separator-agnostic）。
    """

    @staticmethod
    def relpath_to_module_name(rel_path: str) -> str:
        """
        相对路径 → 模块名。

        参数:
            rel_path: 相对路径（``os.sep`` 或 ``/`` 分隔均可；扩展名可选）。

        返回:
            模块名（``.`` 分隔，无扩展名）。空输入返回空串。

        示例:
            ``"pkg/sub/mod.ibci"`` → ``"pkg.sub.mod"``
            ``"pkg/sub/mod"`` → ``"pkg.sub.mod"``
            ``"mod"`` → ``"mod"``
        """
        if not rel_path:
            return ""
        # 经 IbPath 规范化（统一分隔符为 /，去重斜杠），再切分
        ib = IbPath.from_native(rel_path)
        parts = [p for p in ib.parts if p and p != "."]
        # 去掉最后一个部分的扩展名（如 .ibci / .py）
        if parts:
            last = parts[-1]
            if "." in last:
                # 仅去掉文件扩展名（最后一个 '.' 之后）；模块名本身不含 '.' 因为它已被 '/' 分隔
                stem = last.rsplit(".", 1)[0]
                parts[-1] = stem
        return MODULE_SEPARATOR.join(parts)

    @staticmethod
    def module_to_relpath(module_name: str) -> str:
        """
        模块名 → 相对路径（不含扩展名；由调用方按 resolver.extensions 探测）。

        参数:
            module_name: 模块名（``.`` 分隔）。

        返回:
            相对路径（``/`` 分隔，IbPath 规范）。空输入返回空串。

        示例:
            ``"pkg.sub.mod"`` → ``"pkg/sub/mod"``
        """
        if not module_name:
            return ""
        parts = module_name.split(MODULE_SEPARATOR)
        return PATH_SEPARATOR.join(p for p in parts if p)

    @staticmethod
    def module_to_ibpath(module_name: str) -> IbPath:
        """模块名 → IbPath（相对）。"""
        return IbPath.from_native(ModuleNameSpace.module_to_relpath(module_name))

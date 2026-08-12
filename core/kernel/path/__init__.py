"""
IBCI kernel path model — IBCI 路径模型（语言核心概念）。

锚点模型、沙箱、模块名映射、快照布局、FS 感知规范化。
位于 kernel 层，compiler 与 runtime（兄弟层）都通过本包取路径模型，
消除 compiler→runtime 违规。

本包是 path API 的统一 facade：再导出 base/path 的原子原语，
使消费者一处导入即可获得全部路径能力（InstallPaths 除外，它在 runtime/path）。
"""
# 从 base/path 再导出原子原语（facade）
from core.base.path import IbPath, safe_relpath
# 本包的 IBCI 路径模型
from .resolver import PathResolver
from .validator import PathValidator
from .modulename import ModuleNameSpace
from .context import PathContext
from .snapshot import SnapshotLayout

__all__ = [
    "IbPath",
    "safe_relpath",
    "PathResolver",
    "PathValidator",
    "ModuleNameSpace",
    "PathContext",
    "SnapshotLayout",
]

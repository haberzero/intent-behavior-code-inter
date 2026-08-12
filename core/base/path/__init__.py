"""
IBCI base path primitives — 原子路径原语（任何层可用，可迁移到任何语言）。

纯值对象与纯词法操作，无 IBCI 语义、无 FS 访问。
位于 base 层，供 kernel/compiler/runtime/extension 全部合法依赖。
"""
from .ib_path import IbPath
from .relpath import safe_relpath

__all__ = [
    "IbPath",
    "safe_relpath",
]

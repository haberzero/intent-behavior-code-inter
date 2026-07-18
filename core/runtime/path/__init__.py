"""
IBCI runtime path — 运行时/环境特有的路径服务。

Per ADR-017：纯路径原语与 IBCI 路径模型已下沉至 base/path 与 kernel/path。
本包仅保留运行时/环境特有的能力：安装发现（InstallPaths）。

注意：``InstallPaths`` ``import ibci_modules``（安装发现），属于环境/运行时关注点，
故留 runtime 层；compiler 不需要它（search_paths 由 engine 传入）。

命名（ADR-020 §E）：原 ``BuiltinPaths`` → ``InstallPaths``（"builtin" 一词五义消除）。
"""
from .install import InstallPaths

__all__ = [
    "InstallPaths",
]

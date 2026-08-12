"""
IBCI 相对路径计算辅助（canonical）。

``safe_relpath`` 处理 ``os.path.relpath`` 的 Windows 跨盘 ``ValueError``。
统一化于 path 包，使所有路径计算内聚于一处。

注：``os.path.relpath`` 本身是合法的 OS 边界操作（处理 ``..`` 的相对路径计算）；
本函数在其基础上增加跨盘容错（跨盘时相对路径数学上未定义，返回绝对路径）。
"""
from __future__ import annotations

import os

from .ib_path import IbPath


def safe_relpath(path: str, start: str) -> str:
    """跨盘安全的相对路径计算。

    在 Windows 上，当 ``path`` 与 ``start`` 位于不同盘符时，``os.path.relpath``
    抛 ``ValueError``（相对路径此时数学上未定义）。本函数在此情形下返回
    规范化的绝对路径——仅需稳定字符串标识的调用方（如模块名派生）继续工作；
    确实需要相对路径的调用方应保证两输入同盘。

    经 IbPath 规范化后返回（统一分隔符）。
    """
    try:
        rel = os.path.relpath(path, start)
        return IbPath.from_native(rel).to_native()
    except ValueError:
        # 跨盘：相对路径未定义，返回规范化的绝对路径
        return IbPath.from_native(path).resolve_dot_segments().to_native()

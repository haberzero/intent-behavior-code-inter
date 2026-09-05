"""_common — 试用工具链共享助手（单一权威源，各脚本经同目录 import 复用）。"""

import os


def find_repo_root(start: str):
    """从起始目录逐级上溯查找含 ``main.py`` 的仓库根；找不到返回 None。"""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, "main.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None

"""
IBCI Path Module - 路径管理模块

提供 IBCI 独立的路径管理能力，与 Python os.path 解耦。
"""
from .ib_path import IbPath
from .resolver import PathResolver
from .validator import PathValidator

__all__ = [
    "IbPath",
    "PathResolver",
    "PathValidator",
]

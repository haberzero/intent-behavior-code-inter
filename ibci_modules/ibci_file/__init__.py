"""
File 文件操作插件
统一入口点，逻辑分离到 core.py
"""
from .core import create_implementation

__all__ = ["create_implementation"]

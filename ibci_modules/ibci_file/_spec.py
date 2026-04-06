"""
File 文件操作插件规范
合并了基础文件操作和高级文件分析功能
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "file",
        "version": "2.3.0",
        "description": "File operation and analysis plugin (unified from file + third_file)",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

    基础操作:
    - read: str -> str (读取文件内容)
    - write: (str, str) -> void (写入文件内容)
    - exists: str -> bool (检查文件是否存在)
    - remove: str -> void (删除文件)

    高级分析:
    - search_in_files: (str, str, list) -> list (递归搜索文件内容)
    - list_files_recursive: (str, list) -> list (递归列出文件)
    - get_line_count: str -> int (获取文件行数)
    - read_lines_range: (str, int, int) -> list (按范围读取行)
    - get_file_size: str -> int (获取文件大小)
    - find_todos: str -> list (查找TODO注释)
    """
    return {
        "functions": {
            # 基础操作
            "read": {
                "param_types": ["str"],
                "return_type": "str"
            },
            "write": {
                "param_types": ["str", "str"],
                "return_type": "void"
            },
            "exists": {
                "param_types": ["str"],
                "return_type": "bool"
            },
            "remove": {
                "param_types": ["str"],
                "return_type": "void"
            },
            # 高级分析
            "search_in_files": {
                "param_types": ["str", "str", "list"],
                "return_type": "list"
            },
            "list_files_recursive": {
                "param_types": ["str", "list"],
                "return_type": "list"
            },
            "get_line_count": {
                "param_types": ["str"],
                "return_type": "int"
            },
            "read_lines_range": {
                "param_types": ["str", "int", "int"],
                "return_type": "list"
            },
            "get_file_size": {
                "param_types": ["str"],
                "return_type": "int"
            },
            "find_todos": {
                "param_types": ["str"],
                "return_type": "list"
            }
        }
    }

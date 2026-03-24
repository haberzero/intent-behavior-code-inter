"""
[IES 2.2] File 文件操作插件规范

IES 2.2 协议实现（第一方组件）：
- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "file",
        "version": "2.2.0",
        "description": "File operation plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    [IES 2.2] 方法虚表 - 返回原生 IBC-Inter 元数据声明

    read: str -> str (读取文件内容)
    write: (str, str) -> void (写入文件内容)
    exists: str -> bool (检查文件是否存在)
    """
    return {
        "functions": {
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
            }
        }
    }

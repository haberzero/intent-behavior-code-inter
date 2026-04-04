"""
Net 网络请求插件规范

- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "net",
        "version": "2.2.0",
        "description": "Network request plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

    get: (str, dict) -> str (HTTP GET 请求)
    post: (str, any, dict) -> dict (HTTP POST 请求)
    """
    return {
        "functions": {
            "get": {
                "param_types": ["str", "dict"],
                "return_type": "str"
            },
            "post": {
                "param_types": ["str", "any", "dict"],
                "return_type": "dict"
            }
        }
    }

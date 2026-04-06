from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "net",
        "version": "0.0.1",
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

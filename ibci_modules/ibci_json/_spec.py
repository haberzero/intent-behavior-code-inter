from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "json",
        "version": "0.0.1",
        "description": "JSON processing plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

    parse: str -> dict (JSON 字符串解析为字典)
    stringify: any -> str (任意对象序列化为 JSON 字符串)
    """
    return {
        "functions": {
            "parse": {
                "param_types": ["str"],
                "return_type": "dict"
            },
            "stringify": {
                "param_types": ["any"],
                "return_type": "str"
            }
        }
    }

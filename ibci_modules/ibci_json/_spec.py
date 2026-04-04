"""
JSON 处理插件规范

- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入

元数据结构：
- functions: Dict[str, Dict] - 函数签名声明
  - param_types: List[str] - 参数类型列表
  - return_type: str - 返回类型
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "json",
        "version": "2.2.0",
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

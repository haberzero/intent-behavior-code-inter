from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "schema",
        "version": "0.0.1",
        "description": "JSON Schema validation plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

    validate: (dict, dict) -> bool (校验数据是否符合规则)
    assert_schema: (dict, dict) -> void (校验失败则抛出异常)
    """
    return {
        "functions": {
            "validate": {
                "param_types": ["dict", "dict"],
                "return_type": "bool"
            },
            "assert_schema": {
                "param_types": ["dict", "dict"],
                "return_type": "void"
            }
        }
    }

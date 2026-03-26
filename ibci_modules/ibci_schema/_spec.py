"""
[IES 2.2] Schema JSON Schema 校验插件规范

IES 2.2 协议实现（第一方组件）：
- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "schema",
        "version": "2.2.0",
        "description": "JSON Schema validation plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    [IES 2.2] 方法虚表 - 返回原生 IBC-Inter 元数据声明

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

"""
[IES 2.2] Schema JSON Schema 校验插件规范

IES 2.2 协议实现：
- __ibcext_metadata__() 返回插件元数据
- __ibcext_vtable__() 返回方法映射表
"""
from typing import Dict, Any, Callable


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "ibc:schema",
        "version": "2.2.0",
        "description": "JSON Schema validation plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Callable]:
    """[IES 2.2] 方法虚表"""
    from . import SchemaLib
    impl = SchemaLib()
    return {
        "validate": impl.validate,
        "assert": impl._assert,
    }

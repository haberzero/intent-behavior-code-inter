"""
[IES 2.2] IDBG 调试插件规范

IES 2.2 协议实现：
- __ibcext_metadata__() 返回插件元数据
- __ibcext_vtable__() 返回方法映射表
"""
from typing import Dict, Any, Callable


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "idbg",
        "version": "2.2.0",
        "description": "Kernel debugger plugin for runtime introspection",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Callable]:
    """[IES 2.2] 方法虚表"""
    from .core import IDbgPlugin
    impl = IDbgPlugin()
    return {
        "vars": impl.get_vars,
        "last_llm": impl.get_last_llm,
        "env": impl.get_env,
        "fields": impl.inspect_fields,
    }

"""
[IES 2.2] Sys 系统能力插件规范

IES 2.2 协议实现：
- __ibcext_metadata__() 返回插件元数据
- __ibcext_vtable__() 返回方法映射表
"""
from typing import Dict, Any, Callable


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "sys",
        "version": "2.2.0",
        "description": "System capability plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Callable]:
    """[IES 2.2] 方法虚表"""
    from . import SysLib
    impl = SysLib()
    return {
        "request_external_access": impl.request_external_access,
        "is_sandboxed": impl.is_sandboxed,
    }

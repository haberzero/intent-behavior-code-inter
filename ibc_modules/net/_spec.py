"""
[IES 2.2] Net 网络请求插件规范

IES 2.2 协议实现：
- __ibcext_metadata__() 返回插件元数据
- __ibcext_vtable__() 返回方法映射表
"""
from typing import Dict, Any, Callable


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "net",
        "version": "2.2.0",
        "description": "Network request plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Callable]:
    """[IES 2.2] 方法虚表"""
    from . import NetLib
    impl = NetLib()
    return {
        "get": impl.get,
        "post": impl.post,
    }

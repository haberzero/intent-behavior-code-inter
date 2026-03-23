"""
[IES 2.2] HOST 插件规范

IES 2.2 协议实现：
- __ibcext_metadata__() 返回插件元数据
- __ibcext_vtable__() 返回方法映射表
"""
from typing import Dict, Any, Callable


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "host",
        "version": "2.2.0",
        "description": "Host capability plugin for runtime persistence and isolation",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Callable]:
    """[IES 2.2] 方法虚表"""
    from .core import HostImplementation
    impl = HostImplementation()
    return {
        "save_state": impl.ib_save_state,
        "load_state": impl.ib_load_state,
        "run_isolated": impl.ib_run,
        "get_source": impl.ib_get_source,
    }

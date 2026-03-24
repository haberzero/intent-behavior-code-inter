"""
[IES 2.2] Time 时间处理插件规范

IES 2.2 协议实现（第一方组件）：
- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "time",
        "version": "2.2.0",
        "description": "Time processing plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    [IES 2.2] 方法虚表 - 返回原生 IBC-Inter 元数据声明

    now: void -> float (获取当前时间戳)
    sleep: float -> void (休眠指定秒数)
    """
    return {
        "functions": {
            "now": {
                "param_types": [],
                "return_type": "float"
            },
            "sleep": {
                "param_types": ["float"],
                "return_type": "void"
            }
        }
    }

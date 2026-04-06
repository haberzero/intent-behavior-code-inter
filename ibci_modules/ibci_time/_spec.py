from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "time",
        "version": "0.0.1",
        "description": "Time processing plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

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

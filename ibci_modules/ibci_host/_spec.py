"""
[IES 2.2] HOST 主机能力插件规范

IES 2.2 协议实现（第一方组件）：
- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "host",
        "version": "2.2.0",
        "description": "Host capability plugin for runtime persistence and isolation",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    [IES 2.2] 方法虚表 - 返回原生 IBC-Inter 元数据声明

    save_state: str -> void (保存状态到文件)
    load_state: str -> void (从文件加载状态)
    run_isolated: (str, dict) -> bool (在隔离环境中运行脚本)
    get_source: void -> str (获取当前源文件内容)
    """
    return {
        "functions": {
            "save_state": {
                "param_types": ["str"],
                "return_type": "void"
            },
            "load_state": {
                "param_types": ["str"],
                "return_type": "void"
            },
            "run_isolated": {
                "param_types": ["str", "dict"],
                "return_type": "bool"
            },
            "get_source": {
                "param_types": [],
                "return_type": "str"
            }
        }
    }

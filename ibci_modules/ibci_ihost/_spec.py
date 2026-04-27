from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "ihost",
        "kind": "method_module",
        "version": "1.0.0",
        "description": "IBCI host capability plugin: runtime persistence, isolated execution and meta-programming",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回 IBCI 元数据声明

    save_state: str -> void      保存当前运行现场到文件
    load_state: str -> void      从文件恢复运行现场
    run_isolated: (str, dict) -> bool  在隔离环境中运行另一个 ibci 脚本
    get_source: void -> str      获取当前模块的源代码（元编程）
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

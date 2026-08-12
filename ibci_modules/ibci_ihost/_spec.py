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
    """
    return {
        "functions": {
            "save_state": {"params": [{"name": "path", "type": "str"}], "return_type": "void"},
            "load_state": {"params": [{"name": "path", "type": "str"}], "return_type": "void"},
            "run_isolated": {
                "params": [{"name": "path", "type": "str"}, {"name": "policy", "type": "dict"}],
                "return_type": "dict",
            },
            "spawn_isolated": {
                "params": [{"name": "path", "type": "str"}, {"name": "policy", "type": "dict"}],
                "return_type": "str",
            },
            "collect": {"params": [{"name": "handle", "type": "str"}], "return_type": "dict"},
            "get_source": {"params": [], "return_type": "str"}
        }
    }

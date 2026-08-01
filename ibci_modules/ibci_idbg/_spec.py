from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "idbg",
        "kind": "method_module",
        "version": "0.0.1",
        "description": "Kernel debugger plugin for runtime introspection",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明
    """
    return {
        "functions": {
            "vars": {"params": [], "return_type": "dict"},
            "print_vars": {"params": [], "return_type": "void"},
            "current_llm": {"params": [], "return_type": "dict"},
            "show_target_prompt": {"params": [], "return_type": "void"},
            "show_target_result": {"params": [], "return_type": "void"},
            "show_all": {"params": [], "return_type": "void"},
            "current_result": {"params": [], "return_type": "dict"},
            "retry_stack": {"params": [], "return_type": "list"},
            "show_retry_stack": {"params": [], "return_type": "void"},
            "protection_map": {"params": [], "return_type": "dict"},
            "show_protection_map": {"params": [], "return_type": "void"},
            "intents": {"params": [], "return_type": "list"},
            "show_intents": {"params": [], "return_type": "void"},
            "env": {"params": [], "return_type": "dict"},
            "show_env": {"params": [], "return_type": "void"},
            "fields": {"params": [{"name": "obj", "type": "any"}], "return_type": "dict"}
        }
    }

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

    vars: void -> dict (获取当前作用域变量)
    last_llm: void -> dict (获取上次 LLM 调用信息)
    show_last_prompt: void -> void (打印上次 LLM 完整提示词)
    show_last_result: void -> void (打印上次 LLM 原始输出结果)
    show_all: void -> void (打印上次 LLM 完整信息)
    last_result: void -> dict (获取上次 LLM 执行结果)
    retry_stack: void -> list (获取当前重试帧栈)
    intents: void -> list (获取详细意图栈)
    show_intents: void -> void (打印意图栈到控制台)
    env: void -> dict (获取环境变量)
    fields: any -> dict (检查对象的字段)
    """
    return {
        "functions": {
            "vars": {
                "param_types": [],
                "return_type": "dict"
            },
            "last_llm": {
                "param_types": [],
                "return_type": "dict"
            },
            "show_last_prompt": {
                "param_types": [],
                "return_type": "void"
            },
            "show_last_result": {
                "param_types": [],
                "return_type": "void"
            },
            "show_all": {
                "param_types": [],
                "return_type": "void"
            },
            "last_result": {
                "param_types": [],
                "return_type": "dict"
            },
            "retry_stack": {
                "param_types": [],
                "return_type": "list"
            },
            "intents": {
                "param_types": [],
                "return_type": "list"
            },
            "show_intents": {
                "param_types": [],
                "return_type": "void"
            },
            "env": {
                "param_types": [],
                "return_type": "dict"
            },
            "fields": {
                "param_types": ["any"],
                "return_type": "dict"
            }
        }
    }

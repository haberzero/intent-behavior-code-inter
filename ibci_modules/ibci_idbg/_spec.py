"""
IDBG 调试插件规范

- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "idbg",
        "version": "2.2.0",
        "description": "Kernel debugger plugin for runtime introspection",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

    vars: void -> dict (获取当前作用域变量)
    last_llm: void -> dict (获取上次 LLM 调用信息)
    last_result: void -> dict (获取上次 LLM 执行结果)
    retry_stack: void -> list (获取当前重试帧栈)
    intents: void -> list (获取详细意图栈)
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

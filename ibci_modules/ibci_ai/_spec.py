from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "ai",
        "kind": "method_module",
        "version": "0.0.1",
        "description": "AI LLM provider plugin for intent-driven reasoning",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明
    """
    return {
        "functions": {
            "set_config": {
                "params": [
                    {"name": "url", "type": "str"},
                    {"name": "key", "type": "str"},
                    {"name": "model", "type": "str"},
                ],
                "return_type": "void",
            },
            "register_model": {
                "params": [
                    {"name": "name", "type": "str"},
                    {"name": "url", "type": "str"},
                    {"name": "key", "type": "str"},
                    {"name": "model", "type": "str"},
                ],
                "return_type": "void",
            },
            "has_api_key": {"params": [], "return_type": "bool"},
            "probe_model": {"params": [], "return_type": "str"},
            "set_retry": {"params": [{"name": "count", "type": "int"}], "return_type": "void"},
            "set_timeout": {"params": [{"name": "seconds", "type": "float"}], "return_type": "void"},
            "set_return_type_prompt": {
                "params": [
                    {"name": "type_name", "type": "str"},
                    {"name": "prompt", "type": "str"},
                ],
                "return_type": "void",
            },
            "get_return_type_prompt": {"params": [{"name": "type_name", "type": "str"}], "return_type": "str"},
            "get_current_call_info": {"params": [], "return_type": "dict"},
            "run_batch": {
                "params": [
                    {"name": "behavior", "type": "behavior"},
                    {"name": "items", "type": "list"},
                ],
                "return_type": "list",
            },
            "set_global_intent": {"params": [{"name": "intent", "type": "str"}], "return_type": "void"},
            "clear_global_intents": {"params": [], "return_type": "void"},
            "remove_global_intent": {"params": [{"name": "intent", "type": "str"}], "return_type": "void"},
            "mask": {"params": [{"name": "tag_pattern", "type": "str"}], "return_type": "void"},
            "get_global_intents": {"params": [], "return_type": "list"},
            "get_current_intent_stack": {"params": [], "return_type": "list"},
            "stream_call": {
                "params": [
                    {"name": "sys_prompt", "type": "str"},
                    {"name": "user_prompt", "type": "str"},
                ],
                "return_type": "any",
                "description": "流式 LLM 调用：后台消费增量，返回可等待句柄（Waitable）",
            },
            "stream_channel": {
                "params": [
                    {"name": "sys_prompt", "type": "str"},
                    {"name": "user_prompt", "type": "str"},
                ],
                "return_type": "chan",
                "description": "流式 LLM 调用：返回承载增量块的 stream Channel（渲染用）",
            }
        }
    }

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
            "load_config": {
                "params": [{"name": "path", "type": "str"}],
                "return_type": "void",
                "description": "从指定 api_config.json 文件加载配置（指定路径入口）",
            },
            "load_project_config": {
                "params": [],
                "return_type": "void",
                "description": "显式加载 project_root/api_config.json 并应用（一等入口；不存在则 no-op）",
            },
            "apply_config": {
                "params": [{"name": "config", "type": "dict"}],
                "return_type": "void",
                "description": "应用结构化配置 dict（defaults + default_model + models）",
            },
            "set_mock_mode": {
                "params": [
                    {"name": "enable", "type": "bool", "default": True},
                ],
                "return_type": "void",
                "description": "对称开关：set_mock_mode() 进入 MOCK 测试模式；set_mock_mode(False) 退出并重建真实客户端",
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
            "get_retry": {"params": [], "return_type": "int"},
            "is_auto_intent_injection_enabled": {"params": [], "return_type": "bool"},
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

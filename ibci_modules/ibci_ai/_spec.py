"""
[IES 2.2] AI 插件规范

IES 2.2 协议实现（第一方组件）：
- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "ai",
        "version": "2.2.0",
        "description": "AI LLM provider plugin for intent-driven reasoning",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    [IES 2.2] 方法虚表 - 返回原生 IBC-Inter 元数据声明
    """
    return {
        "functions": {
            "set_config": {"param_types": ["str", "str", "str"], "return_type": "void"},
            "set_retry": {"param_types": ["int"], "return_type": "void"},
            "set_timeout": {"param_types": ["float"], "return_type": "void"},
            "set_general_prompt": {"param_types": ["str"], "return_type": "void"},
            "set_branch_prompt": {"param_types": ["str"], "return_type": "void"},
            "set_loop_prompt": {"param_types": ["str"], "return_type": "void"},
            "set_scene_config": {"param_types": ["str", "dict"], "return_type": "void"},
            "get_scene_prompt": {"param_types": ["str"], "return_type": "str"},
            "get_retry_prompt": {"param_types": ["str"], "return_type": "str"},
            "set_return_type_prompt": {"param_types": ["str", "str"], "return_type": "void"},
            "get_return_type_prompt": {"param_types": ["str"], "return_type": "str"},
            "set_retry_hint": {"param_types": ["str"], "return_type": "void"},
            "get_last_call_info": {"param_types": [], "return_type": "dict"},
            "set_decision_map": {"param_types": ["dict"], "return_type": "void"},
            "get_decision_map": {"param_types": [], "return_type": "dict"},
            "set_global_intent": {"param_types": ["str"], "return_type": "void"},
            "clear_global_intents": {"param_types": [], "return_type": "void"},
            "remove_global_intent": {"param_types": ["str"], "return_type": "void"},
            "mask": {"param_types": ["str"], "return_type": "void"},
            "get_global_intents": {"param_types": [], "return_type": "list"},
            "get_current_intent_stack": {"param_types": [], "return_type": "list"}
        }
    }

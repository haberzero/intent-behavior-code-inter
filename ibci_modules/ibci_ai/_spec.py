"""
[IES 2.2] AI 插件规范

IES 2.2 协议实现（第一方组件 - 深度嵌入）：
- __ibcext_metadata__() 返回插件元数据
- __ibcext_vtable__() 返回方法映射表（使用 Python callable）

注意：ai 模块深度嵌入运行流程，需要与内核代码高度绑定。
其他模块应使用纯字典格式元数据声明。
"""
from typing import Dict, Any, Callable


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "ai",
        "version": "2.2.0",
        "description": "AI LLM provider plugin for intent-driven reasoning",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Callable]:
    """
    [IES 2.2] 方法虚表

    ai 模块深度嵌入运行流程，返回 Python callable 以支持 LLM 集成。
    """
    from ibci_modules.ibci_ai.core import AIPlugin
    impl = AIPlugin()
    return {
        "set_config": impl.set_config,
        "set_retry": impl.set_retry,
        "set_timeout": impl.set_timeout,
        "set_general_prompt": impl.set_general_prompt,
        "set_branch_prompt": impl.set_branch_prompt,
        "set_loop_prompt": impl.set_loop_prompt,
        "set_scene_config": impl.set_scene_config,
        "get_scene_prompt": impl.get_scene_prompt,
        "get_retry_prompt": impl.get_retry_prompt,
        "set_return_type_prompt": impl.set_return_type_prompt,
        "get_return_type_prompt": impl.get_return_type_prompt,
        "set_retry_hint": impl.set_retry_hint,
        "get_last_call_info": impl.get_last_call_info,
        "set_decision_map": impl.set_decision_map,
        "get_decision_map": impl.get_decision_map,
        "set_global_intent": impl.set_global_intent,
        "clear_global_intents": impl.clear_global_intents,
        "remove_global_intent": impl.remove_global_intent,
        "mask": impl.mask,
        "get_global_intents": impl.get_global_intents,
        "get_current_intent_stack": impl.get_current_intent_stack,
    }

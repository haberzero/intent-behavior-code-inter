from core.domain.types.descriptors import ModuleMetadata, FunctionMetadata, STR_DESCRIPTOR, INT_DESCRIPTOR, FLOAT_DESCRIPTOR, DICT_DESCRIPTOR, LIST_DESCRIPTOR

metadata = ModuleMetadata(
    name="ai",
    required_capabilities=["LLM_PROVIDER", "INTENT_MANAGER"],
    members={
        "set_config": FunctionMetadata(name="set_config", param_types=[STR_DESCRIPTOR, STR_DESCRIPTOR, STR_DESCRIPTOR], return_type=None),
        "set_retry_hint": FunctionMetadata(name="set_retry_hint", param_types=[STR_DESCRIPTOR], return_type=None),
        "set_retry": FunctionMetadata(name="set_retry", param_types=[INT_DESCRIPTOR], return_type=None),
        "set_timeout": FunctionMetadata(name="set_timeout", param_types=[FLOAT_DESCRIPTOR], return_type=None),
        "set_general_prompt": FunctionMetadata(name="set_general_prompt", param_types=[STR_DESCRIPTOR], return_type=None),
        "set_branch_prompt": FunctionMetadata(name="set_branch_prompt", param_types=[STR_DESCRIPTOR], return_type=None),
        "set_loop_prompt": FunctionMetadata(name="set_loop_prompt", param_types=[STR_DESCRIPTOR], return_type=None),
        "set_return_type_prompt": FunctionMetadata(name="set_return_type_prompt", param_types=[STR_DESCRIPTOR, STR_DESCRIPTOR], return_type=None),
        "get_return_type_prompt": FunctionMetadata(name="get_return_type_prompt", param_types=[STR_DESCRIPTOR], return_type=STR_DESCRIPTOR),
        "set_decision_map": FunctionMetadata(name="set_decision_map", param_types=[DICT_DESCRIPTOR], return_type=None),
        "get_decision_map": FunctionMetadata(name="get_decision_map", param_types=[], return_type=DICT_DESCRIPTOR),
        "get_last_call_info": FunctionMetadata(name="get_last_call_info", param_types=[], return_type=DICT_DESCRIPTOR),
        "get_scene_prompt": FunctionMetadata(name="get_scene_prompt", param_types=[STR_DESCRIPTOR], return_type=STR_DESCRIPTOR),
        "set_scene_config": FunctionMetadata(name="set_scene_config", param_types=[STR_DESCRIPTOR, DICT_DESCRIPTOR], return_type=None),
        "set_global_intent": FunctionMetadata(name="set_global_intent", param_types=[STR_DESCRIPTOR], return_type=None),
        "clear_global_intents": FunctionMetadata(name="clear_global_intents", param_types=[], return_type=None),
        "remove_global_intent": FunctionMetadata(name="remove_global_intent", param_types=[STR_DESCRIPTOR], return_type=None),
        "get_global_intents": FunctionMetadata(name="get_global_intents", param_types=[], return_type=LIST_DESCRIPTOR),
        "get_current_intent_stack": FunctionMetadata(name="get_current_intent_stack", param_types=[], return_type=LIST_DESCRIPTOR),
        "mask": FunctionMetadata(name="mask", param_types=[STR_DESCRIPTOR], return_type=None),
    }
)

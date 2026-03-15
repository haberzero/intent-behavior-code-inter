from core.domain.types.descriptors import ModuleMetadata, FunctionMetadata, DICT_DESCRIPTOR, VAR_DESCRIPTOR

metadata = ModuleMetadata(
    name="idbg",
    required_capabilities=["STATE_READER", "LLM_EXECUTOR", "LLM_PROVIDER", "STACK_INSPECTOR"],
    members={
        "vars": FunctionMetadata(name="vars", param_types=[], return_type=DICT_DESCRIPTOR),
        "last_llm": FunctionMetadata(name="last_llm", param_types=[], return_type=DICT_DESCRIPTOR),
        "env": FunctionMetadata(name="env", param_types=[], return_type=DICT_DESCRIPTOR),
        "fields": FunctionMetadata(name="fields", param_types=[VAR_DESCRIPTOR], return_type=DICT_DESCRIPTOR),
    }
)

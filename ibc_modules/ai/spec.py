from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("ai")
    .func("set_config", params=["str", "str", "str"])
    .func("set_retry_hint", params=["str"])
    .func("set_retry", params=["int"])
    .func("set_timeout", params=["float"])
    .func("set_general_prompt", params=["str"])
    .func("set_branch_prompt", params=["str"])
    .func("set_loop_prompt", params=["str"])
    .func("set_return_type_prompt", params=["str", "str"])
    .func("get_return_type_prompt", params=["str"], returns="str")
    .build())

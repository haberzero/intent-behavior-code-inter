from utils.module_spec_builder import SpecBuilder

spec = (SpecBuilder("ai")
    .func("set_config", params=["str", "str", "str"])
    .func("set_retry_hint", params=["str"])
    .func("set_retry", params=["int"])
    .func("set_timeout", params=["float"])
    .build())

from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("idbg")
    .func("vars", returns="dict")
    .func("last_llm", returns="dict")
    .func("env", returns="dict")
    .func("fields", params=["var"], returns="dict")
    .build())

from core.foundation.module_spec_builder import SpecBuilder

spec = (SpecBuilder("sys")
    .func("request_external_access")
    .func("is_sandboxed", returns="bool")
    .build())

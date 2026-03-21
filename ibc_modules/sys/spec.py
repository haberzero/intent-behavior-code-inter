from core.extension.spec_builder import SpecBuilder

spec = (SpecBuilder("sys")
    .func("request_external_access")
    .func("is_sandboxed", returns="bool")
    .build())

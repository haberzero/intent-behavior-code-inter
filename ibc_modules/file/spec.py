from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("file")
    .func("read", params=["str"], returns="str")
    .func("write", params=["str", "str"])
    .func("exists", params=["str"], returns="bool")
    .build())

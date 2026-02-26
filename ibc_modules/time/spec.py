from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("time")
    .func("now", returns="float")
    .func("sleep", params=["float"])
    .build())

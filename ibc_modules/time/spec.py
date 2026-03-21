from core.extension.spec_builder import SpecBuilder

spec = (SpecBuilder("time")
    .func("now", returns="float")
    .func("sleep", params=["float"])
    .build())

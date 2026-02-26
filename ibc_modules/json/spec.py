from utils.module_spec_builder import SpecBuilder

spec = (SpecBuilder("json")
    .func("parse", params=["str"], returns="any")
    .func("stringify", params=["any"], returns="str")
    .build())

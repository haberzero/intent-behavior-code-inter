from core.extension.spec_builder import SpecBuilder

spec = (SpecBuilder("host")
    .func("save_state", params=["str"])
    .func("load_state", params=["str"])
    .func("run", params=["str", "dict"], returns="bool")
    .func("get_source", returns="str")
    .build())

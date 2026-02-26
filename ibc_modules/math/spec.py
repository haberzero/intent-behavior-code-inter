from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("math")
    .func("sqrt", params=["float"], returns="float")
    .var("pi", type="float")
    .func("pow", params=["float", "float"], returns="float")
    .func("sin", params=["float"], returns="float")
    .func("cos", params=["float"], returns="float")
    .build())

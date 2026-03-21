from core.extension.spec_builder import SpecBuilder

spec = SpecBuilder("calc") \
    .func("add", params=["int", "int"], returns="int") \
    .func("mul", params=["int", "int"], returns="int") \
    .build()

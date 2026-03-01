from core.support.module_spec_builder import SpecBuilder

def get_spec():
    return (SpecBuilder("schema")
        .func("validate", params=["dict", "dict"], returns="bool")
        .func("assert", params=["dict", "dict"])
        .build())

spec = get_spec()

from core.support.module_spec_builder import SpecBuilder

def get_spec():
    return (SpecBuilder("net")
        .func("get", params=["str", "dict"], returns="str")
        .func("post", params=["str", "dict", "dict"], returns="dict")
        .build())

spec = get_spec()

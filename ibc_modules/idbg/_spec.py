from core.extension.spec_builder import SpecBuilder

metadata = (
    SpecBuilder("idbg")
    .func("vars", [], "dict")
    .func("last_llm", [], "dict")
    .func("env", [], "dict")
    .func("fields", ["any"], "dict")
)
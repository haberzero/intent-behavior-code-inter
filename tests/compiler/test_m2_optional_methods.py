"""
M2: Optional[T] method capability/type-signature coverage.
"""

from core.engine import IBCIEngine
from core.kernel.factory import create_default_registry
from core.kernel.issue import CompilerError


def compile_code(code: str):
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    try:
        artifact = engine.compile_string(code, silent=True)
        return artifact, set()
    except CompilerError as e:
        return None, {d.code for d in e.diagnostics}


def assert_compiles(code: str):
    artifact, errors = compile_code(code)
    assert artifact is not None
    assert not errors, f"Expected no compiler errors, got: {errors}"


class TestM2OptionalMethodResolution:
    def test_unwrap_return_type_is_wrapped_type(self):
        reg = create_default_registry()
        optional_int = reg.resolve_specialization(reg.resolve("Optional"), [reg.resolve("int")])
        unwrap_spec = reg.resolve_member(optional_int, "unwrap")
        assert unwrap_spec is not None
        assert unwrap_spec.return_type.head == "int"

    def test_or_else_signature_is_specialized(self):
        reg = create_default_registry()
        optional_int = reg.resolve_specialization(reg.resolve("Optional"), [reg.resolve("int")])
        or_else_spec = reg.resolve_member(optional_int, "or_else")
        assert or_else_spec is not None
        assert or_else_spec.return_type.head == "int"
        assert [t.head for t in or_else_spec.param_types] == ["int"]


class TestM2OptionalMethodCompileSemantics:
    def test_or_else_allows_unwrap_to_plain_type(self):
        assert_compiles(
            "Optional[int] x = None\n"
            "int y = x.or_else(3)\n"
        )

    def test_unwrap_allows_assign_to_plain_type(self):
        assert_compiles(
            "Optional[int] x = 1\n"
            "int y = x.unwrap()\n"
        )

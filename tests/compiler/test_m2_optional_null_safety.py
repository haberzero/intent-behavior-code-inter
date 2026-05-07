"""
M2: Optional[T] null-safety compile-time checks.
"""

import os
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


def make_engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)


def compile_code(code: str):
    engine = make_engine()
    try:
        artifact = engine.compile_string(code, silent=True)
        return artifact, set()
    except CompilerError as e:
        return None, {d.code for d in e.diagnostics}


def assert_compiles(code: str):
    artifact, errors = compile_code(code)
    assert artifact is not None
    assert not errors, f"Expected no compiler errors, got: {errors}"


def assert_has_sem003(code: str):
    _, errors = compile_code(code)
    assert "SEM_003" in errors, f"Expected SEM_003, got: {errors}"


class TestM2OptionalNullSafety:
    def test_optional_int_accepts_none(self):
        assert_compiles(
            "Optional[int] x = None\n"
            "Optional[int] y = x\n"
        )

    def test_optional_int_accepts_int(self):
        assert_compiles(
            "Optional[int] x = 1\n"
            "Optional[int] y = x\n"
        )

    def test_plain_int_rejects_none(self):
        assert_has_sem003("int x = None\n")

    def test_plain_int_rejects_optional_int(self):
        assert_has_sem003(
            "Optional[int] x = 1\n"
            "int y = x\n"
        )


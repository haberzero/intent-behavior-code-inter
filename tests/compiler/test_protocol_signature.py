"""
tests/compiler/test_protocol_signature.py — 协议签名编译期契约（SEM_PROTOCOL_SIGNATURE）。

compile-only（不运行 IBCI 代码）；自原 test_prompt_protocol.py 拆分（mixed-concerns：
编译期契约归 compiler/，纯数据结构公理归 kernel/）。
"""

from tests.conftest import compile_ibci


class TestProtocolSignatureCompileTime:
    """语义 pass 对坏签名的 SEM_PROTOCOL_SIGNATURE warning（编译不阻断）。"""

    def test_wrong_to_prompt_params_produces_warning(self):
        """User class __to_prompt__ with wrong params should compile with warning."""
        code = """
class Foo:
    str name
    func __to_prompt__(str extra) -> str:
        return name
"""
        artifact = compile_ibci(code)
        assert artifact is not None

    def test_correct_to_prompt_no_warning(self):
        """User class __to_prompt__ with correct signature compiles cleanly."""
        code = """
class Bar:
    str name
    func __to_prompt__() -> str:
        return name
"""
        artifact = compile_ibci(code)
        assert artifact is not None

    def test_validate_prompt_protocol_compiles(self):
        """User class __validate_prompt__(str) -> tuple compiles."""
        code = """
class Validatable:
    str pattern
    func __validate_prompt__(str raw) -> tuple:
        return (True, "")
"""
        artifact = compile_ibci(code)
        assert artifact is not None

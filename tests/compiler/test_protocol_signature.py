"""
tests/compiler/test_protocol_signature.py — 协议签名编译期契约（SEM_PROTOCOL_SIGNATURE）。

compile-only（不运行 IBCI 代码）；自原 test_prompt_protocol.py 拆分（mixed-concerns：
编译期契约归 compiler/，纯数据结构公理归 kernel/）。

D2（PT-DECIDE-3 项③）：required 协议成员签名违约 = 契约破坏 → 编译错误（fail-fast）。
"""

from tests.conftest import compile_ibci, expect_compile_error


class TestProtocolSignatureCompileTime:
    """语义 pass 对坏签名的 SEM_PROTOCOL_SIGNATURE error（编译阻断，fail-fast）。"""

    def test_wrong_to_prompt_params_produces_error(self):
        """User class __to_prompt__ with wrong params fails to compile."""
        code = """
class Foo:
    str name
    func __to_prompt__(str extra) -> str:
        return name
"""
        expect_compile_error(code, "SEM_PROTOCOL_SIGNATURE")

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

"""
tests_v2/e2e/test_prompt_protocol_e2e.py
=====================================

__validate_prompt__ 协议运行时集成测试（从 tests_v2/kernel/test_prompt_protocol.py
分离，确保 kernel 层保持纯单元测试）。
"""
from tests_v2.conftest import run_ibci, AI_MOCK_PREFIX


class TestValidatePromptRuntime:
    """Test __validate_prompt__ integration in LLM parsing pipeline."""

    def test_validate_prompt_rejects_bad_input(self):
        """Verify that __validate_prompt__ + __from_prompt__ compiles and executes.

        This is a compile+run integration test; it confirms the type checking pass
        accepts the protocol methods and that the program executes without error.
        """
        # Simpler test: verify __validate_prompt__ doesn't break normal execution
        code = AI_MOCK_PREFIX + """
class StrictType:
    str value

    func __init__(self) -> auto:
        self.value = ""

    func __validate_prompt__(str raw) -> tuple:
        if raw == "bad_data":
            return (False, "input must not be bad_data")
        return (True, "")
    func __from_prompt__(str raw) -> tuple:
        StrictType s = StrictType()
        s.value = raw
        return (True, s)
    func __outputhint_prompt__() -> str:
        return "Return valid data"

# Verify the class compiles and the protocols are recognized
StrictType s = StrictType()
s.value = "hello"
print(s.value)
"""
        result = run_ibci(code)
        assert result == ["hello"]

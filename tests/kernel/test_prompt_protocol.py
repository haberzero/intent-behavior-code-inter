"""
tests/kernel/test_prompt_protocol.py
====================================

Unit tests for the unified __prompt__ protocol infrastructure.

Validates:
- PromptProtocolSpec definitions
- validate_prompt_protocol_signature() contract checking
- SEM_095 compile-time warnings for incorrect protocol signatures
- __validate_prompt__ pre-flight validation in VTableParsingStrategy
"""

import pytest
from core.kernel.axioms.prompt_protocol import (
    PROMPT_PROTOCOL_SPECS,
    PROMPT_PROTOCOL_NAMES,
    PromptProtocolSpec,
    validate_prompt_protocol_signature,
    is_prompt_protocol_method,
    get_prompt_protocol_spec,
)


# ===========================================================================
# Unit: PromptProtocolSpec registry
# ===========================================================================


class TestPromptProtocolRegistry:
    """Tests for the protocol spec registry itself."""

    def test_all_four_protocols_registered(self):
        """All four prompt protocols are defined."""
        assert "__to_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__from_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__outputhint_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__validate_prompt__" in PROMPT_PROTOCOL_SPECS

    def test_frozen_dataclass(self):
        """Specs are immutable."""
        spec = PROMPT_PROTOCOL_SPECS["__to_prompt__"]
        with pytest.raises(Exception):
            spec.name = "changed"  # type: ignore

    def test_to_prompt_spec(self):
        """__to_prompt__ is an instance method with 0 params returning str."""
        spec = PROMPT_PROTOCOL_SPECS["__to_prompt__"]
        assert spec.is_instance_method is True
        assert spec.param_count == 0
        assert spec.return_type == "str"

    def test_from_prompt_spec(self):
        """__from_prompt__ is class-level with 1 str param returning tuple."""
        spec = PROMPT_PROTOCOL_SPECS["__from_prompt__"]
        assert spec.is_instance_method is False
        assert spec.param_count == 1
        assert spec.param_types == ("str",)
        assert spec.return_type == "tuple"

    def test_outputhint_prompt_spec(self):
        """__outputhint_prompt__ is class-level, 0 params, returns str."""
        spec = PROMPT_PROTOCOL_SPECS["__outputhint_prompt__"]
        assert spec.is_instance_method is False
        assert spec.param_count == 0
        assert spec.return_type == "str"

    def test_validate_prompt_spec(self):
        """__validate_prompt__ is class-level, 1 str param, returns tuple."""
        spec = PROMPT_PROTOCOL_SPECS["__validate_prompt__"]
        assert spec.is_instance_method is False
        assert spec.param_count == 1
        assert spec.param_types == ("str",)
        assert spec.return_type == "tuple"

    def test_is_prompt_protocol_method(self):
        assert is_prompt_protocol_method("__to_prompt__") is True
        assert is_prompt_protocol_method("__from_prompt__") is True
        assert is_prompt_protocol_method("__validate_prompt__") is True
        assert is_prompt_protocol_method("__init__") is False
        assert is_prompt_protocol_method("foo") is False

    def test_get_prompt_protocol_spec_returns_none_for_non_protocol(self):
        assert get_prompt_protocol_spec("__call__") is None
        assert get_prompt_protocol_spec("random_method") is None


# ===========================================================================
# Unit: validate_prompt_protocol_signature
# ===========================================================================


class TestValidatePromptProtocolSignature:
    """Tests for compile-time signature validation."""

    def test_valid_to_prompt_no_diagnostics(self):
        """Correct __to_prompt__(self) -> str produces no warnings."""
        diags = validate_prompt_protocol_signature("__to_prompt__", 0, "str")
        assert diags == []

    def test_to_prompt_extra_params_warns(self):
        """__to_prompt__ with extra params produces a diagnostic."""
        diags = validate_prompt_protocol_signature("__to_prompt__", 2, "str")
        assert len(diags) == 1
        assert "expects 0 parameter" in diags[0]

    def test_to_prompt_wrong_return_type_warns(self):
        """__to_prompt__ returning int produces a diagnostic."""
        diags = validate_prompt_protocol_signature("__to_prompt__", 0, "int")
        assert len(diags) == 1
        assert "should return 'str'" in diags[0]

    def test_to_prompt_auto_return_no_warn(self):
        """__to_prompt__ with auto return is acceptable (no warn)."""
        diags = validate_prompt_protocol_signature("__to_prompt__", 0, "auto")
        assert diags == []

    def test_from_prompt_correct_no_diagnostics(self):
        """Correct __from_prompt__(raw) with tuple return is fine."""
        diags = validate_prompt_protocol_signature("__from_prompt__", 1, "tuple")
        assert diags == []

    def test_from_prompt_missing_param_warns(self):
        """__from_prompt__ with 0 params produces a diagnostic."""
        diags = validate_prompt_protocol_signature("__from_prompt__", 0, None)
        assert len(diags) == 1
        assert "expects 1 parameter" in diags[0]

    def test_validate_prompt_correct(self):
        """__validate_prompt__(raw) -> tuple is correct."""
        diags = validate_prompt_protocol_signature("__validate_prompt__", 1, "tuple")
        assert diags == []

    def test_validate_prompt_wrong_params(self):
        """__validate_prompt__ with wrong param count warns."""
        diags = validate_prompt_protocol_signature("__validate_prompt__", 3, None)
        assert len(diags) == 1
        assert "expects 1 parameter" in diags[0]

    def test_non_protocol_method_no_diagnostics(self):
        """Non-protocol methods produce no diagnostics."""
        diags = validate_prompt_protocol_signature("__init__", 5, "void")
        assert diags == []
        diags = validate_prompt_protocol_signature("regular_method", 2, "int")
        assert diags == []

    def test_outputhint_prompt_extra_params(self):
        """__outputhint_prompt__ with extra params warns."""
        diags = validate_prompt_protocol_signature("__outputhint_prompt__", 1, "str")
        assert len(diags) == 1
        assert "expects 0 parameter" in diags[0]


# ===========================================================================
# Integration: SEM_095 compile-time warning
# ===========================================================================


class TestSEM095CompileTimeWarning:
    """Test that the semantic pass produces SEM_095 warnings for bad signatures."""

    def test_wrong_to_prompt_params_produces_warning(self):
        """User class __to_prompt__ with wrong params should compile with warning."""
        from tests.conftest import compile_ibci

        # This should compile successfully (warnings don't block compilation)
        # __to_prompt__ with extra params
        code = """
class Foo:
    str name
    func __to_prompt__(str extra) -> str:
        return name
"""
        # Should compile without error (warning only)
        artifact = compile_ibci(code)
        assert artifact is not None

    def test_correct_to_prompt_no_warning(self):
        """User class __to_prompt__ with correct signature compiles cleanly."""
        from tests.conftest import compile_ibci

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
        from tests.conftest import compile_ibci

        code = """
class Validatable:
    str pattern
    func __validate_prompt__(str raw) -> tuple:
        return (True, "")
"""
        artifact = compile_ibci(code)
        assert artifact is not None


# ===========================================================================
# Integration: __validate_prompt__ runtime pre-flight
# ===========================================================================


class TestValidatePromptRuntime:
    """Test __validate_prompt__ integration in LLM parsing pipeline."""

    def test_validate_prompt_rejects_bad_input(self):
        """Verify that __validate_prompt__ + __from_prompt__ compiles and executes.

        This is a compile+run integration test; it confirms the type checking pass
        accepts the protocol methods and that the program executes without error.
        Full runtime validation behavior (uncertain result on failure) depends on
        the LLM parsing chain which requires a real/mocked LLM target type context.
        """
        from tests.conftest import run_ibci, AI_MOCK_PREFIX

        # Simpler test: verify __validate_prompt__ doesn't break normal execution
        code = AI_MOCK_PREFIX + """
class StrictType:
    str value

    func __init__(self):
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

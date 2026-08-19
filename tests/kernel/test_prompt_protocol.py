"""
tests/kernel/test_prompt_protocol.py
====================================

Unit tests for the unified __prompt__ protocol infrastructure.

Validates:
- PromptProtocolSpec definitions
- validate_prompt_protocol_signature() contract checking
- SEM_PROTOCOL_SIGNATURE compile-time warnings for incorrect protocol signatures
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

    def test_prompt_protocol_family_registered(self):
        """The full __prompt__ family (incl. __payload_prompt__) is defined.

        ``__payload_prompt__`` was the missing 5th member (D1 双注册表收敛)——
        与 ``core/kernel/protocol.py::BUILTIN_PROTOCOLS`` 的 ``payload_prompt``
        条目共享同一方法名权威。
        """
        assert "__to_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__from_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__outputhint_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__validate_prompt__" in PROMPT_PROTOCOL_SPECS
        assert "__payload_prompt__" in PROMPT_PROTOCOL_SPECS

    def test_builtin_protocol_payload_consistent(self):
        """D1：方法名权威共享——BUILTIN_PROTOCOLS 的 payload_prompt 与该 SPECS 一致。"""
        from core.kernel.protocol import BUILTIN_PROTOCOLS
        payload = next(p for p in BUILTIN_PROTOCOLS if p.name == "payload_prompt")
        assert payload.methods == ("__payload_prompt__",)
        assert "__payload_prompt__" in PROMPT_PROTOCOL_SPECS

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

    def test_payload_prompt_spec(self):
        """__payload_prompt__ is an instance method with 0 params returning any.

        Runtime dispatch is zero-argument (``receive('__payload_prompt__', [])``),
        so the user-facing contract excludes value/spec parameters.
        """
        spec = PROMPT_PROTOCOL_SPECS["__payload_prompt__"]
        assert spec.is_instance_method is True
        assert spec.param_count == 0
        assert spec.return_type == "any"

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
        assert is_prompt_protocol_method("__payload_prompt__") is True
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

    def test_payload_prompt_correct_no_diagnostics(self):
        """__payload_prompt__(self) -> dict is correct (0 params excl self)."""
        assert validate_prompt_protocol_signature("__payload_prompt__", 0, "dict") == []
        assert validate_prompt_protocol_signature("__payload_prompt__", 0, "any") == []

    def test_payload_prompt_extra_params_warns(self):
        """__payload_prompt__ with extra params (beyond self) warns — runtime
        dispatch is zero-argument."""
        diags = validate_prompt_protocol_signature("__payload_prompt__", 2, "dict")
        assert len(diags) == 1
        assert "expects 0 parameter" in diags[0]


# ===========================================================================
# P5：validate_prompt 死条目激活（G7 能力公理收尾）+ required/optional 形式化
# ===========================================================================


class TestValidatePromptActivation:
    """P5a：validate_prompt 协议条目激活（D2 to_prompt 同构）——axiom_cap 统一
    声明（内置默认 False）+ 结构成员判定（用户类）+ satisfies 行为。"""

    def _entry(self):
        from core.kernel.protocol import BUILTIN_PROTOCOLS

        return next(p for p in BUILTIN_PROTOCOLS if p.name == "validate_prompt")

    def test_entry_declares_axiom_cap_and_structural_methods(self):
        entry = self._entry()
        assert entry.axiom_cap == "has_validate_prompt_cap"
        assert entry.structural_methods == ("__validate_prompt__",)
        assert entry.methods == ("__validate_prompt__",)

    def test_axiom_flag_defaults_false(self):
        from core.kernel.axioms.primitives.base import BaseAxiom

        assert BaseAxiom.has_validate_prompt_cap is False

    def test_builtin_type_does_not_satisfy_validate_prompt(self):
        """内置类型（axiom 承载，flag 默认 False）不满足 validate_prompt——
        预校验由内建解析器承担，不经 __validate_prompt__ 协议。"""
        from core.kernel.factory import create_default_registry

        reg = create_default_registry()
        int_spec = reg.resolve("int")
        assert int_spec is not None
        assert reg.satisfies_protocol(int_spec, "validate_prompt") is False

    def test_user_class_with_validate_method_satisfies(self):
        """声明 __validate_prompt__ 的用户类经结构成员判定满足 validate_prompt。"""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec import TypeDef, TypeKind, MethodMemberSpec

        reg = create_default_registry()
        spec = TypeDef(name="Validated", kind=TypeKind.CLASS.value, provenance="USER_DEFINED")
        spec.members["__validate_prompt__"] = MethodMemberSpec(
            name="__validate_prompt__",
            kind="method",
            return_type=None,
            param_types=[],
        )
        assert reg.satisfies_protocol(spec, "validate_prompt") is True


class TestLLMCallableRequiredOptional:
    """P5b：required/optional 协议条目形式化（P1 §2.2）——methods 保持必需权威，
    optional_methods 声明可选能力（__intent__/__retry__），不参与强制判定。"""

    def _entry(self):
        from core.kernel.protocol import BUILTIN_PROTOCOLS

        return next(p for p in BUILTIN_PROTOCOLS if p.name == "llm_callable")

    def test_optional_methods_formalized(self):
        entry = self._entry()
        assert entry.methods == ("__llm_call__",)
        assert entry.optional_methods == ("__intent__", "__retry__")

    def test_all_methods_union_ordered_unique(self):
        entry = self._entry()
        assert entry.all_methods() == ("__llm_call__", "__intent__", "__retry__")

    def test_requires_only_required_method(self):
        entry = self._entry()
        assert entry.requires("__llm_call__") is True
        assert entry.requires("__intent__") is False  # optional 不属必需
        assert entry.requires("__retry__") is False

    def test_optional_does_not_participate_in_satisfaction(self):
        """satisfies 只查 required（__llm_call__）：仅有 optional 方法而无
        __llm_call__ 的类不满足 llm_callable。"""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec import TypeDef, TypeKind, MethodMemberSpec

        reg = create_default_registry()
        spec = TypeDef(name="OnlyOptional", kind=TypeKind.CLASS.value, provenance="USER_DEFINED")
        spec.members["__intent__"] = MethodMemberSpec(
            name="__intent__",
            kind="method",
            return_type=None,
            param_types=[],
        )
        spec.members["__retry__"] = MethodMemberSpec(
            name="__retry__",
            kind="method",
            return_type=None,
            param_types=[],
        )
        assert reg.satisfies_protocol(spec, "llm_callable") is False
        # 声明 __llm_call__ 后满足
        spec.members["__llm_call__"] = MethodMemberSpec(
            name="__llm_call__",
            kind="method",
            return_type=None,
            param_types=[],
        )
        assert reg.satisfies_protocol(spec, "llm_callable") is True



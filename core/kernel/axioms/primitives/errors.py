"""
core/kernel/axioms/primitives/errors.py

Exception and LLM-error axioms.
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


# ------------------------------------------------------------------ #
# Exception                                                           #
# ------------------------------------------------------------------ #

class ExceptionAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "Exception"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            # message 作为字段（field）声明，语义分析器 resolve_member 返回 str 类型，
            # 运行时通过 __getattr__ → fields['message'] 直接取出字符串值。
            "message": MemberSpec(name="message", kind="field", type_ref=TypeRef.of("str")),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "Exception")

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "Exception"


# ------------------------------------------------------------------ #
# LLM Exception hierarchy                                             #
# ------------------------------------------------------------------ #

class LLMErrorAxiom(BaseAxiom):
    """Base axiom for all LLM-originated exceptions.

    LLMError IS-A Exception, so ``except Exception as e:`` can catch it.
    Fields: message (str), raw_response (str).
    """

    has_converter_cap = True

    @property
    def name(self) -> str:
        return "LLMError"

    def get_parent_axiom_name(self) -> Optional[str]:
        return "Exception"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "message":      MemberSpec(name="message",      kind="field", type_ref=TypeRef.of("str")),
            "raw_response": MemberSpec(name="raw_response", kind="field", type_ref=TypeRef.of("str")),
            "cast_to":      _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "LLMError")

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("Exception", "LLMError")


class LLMParseErrorAxiom(BaseAxiom):
    """Raised when an unprotected LLM assignment's __from_prompt__ fails.

    Fields: message (str), raw_response (str), type_name (str — expected type).
    """

    has_converter_cap = True

    @property
    def name(self) -> str:
        return "LLMParseError"

    def get_parent_axiom_name(self) -> Optional[str]:
        return "LLMError"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "message":      MemberSpec(name="message",      kind="field", type_ref=TypeRef.of("str")),
            "raw_response": MemberSpec(name="raw_response", kind="field", type_ref=TypeRef.of("str")),
            "type_name":    MemberSpec(name="type_name",    kind="field", type_ref=TypeRef.of("str")),
            "cast_to":      _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "LLMParseError")

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("Exception", "LLMError", "LLMParseError")


class LLMRetryExhaustedErrorAxiom(BaseAxiom):
    """Raised when a llmexcept-protected assignment exhausts all retries.

    Fields: message (str), raw_response (str), max_retry (int).
    """

    has_converter_cap = True

    @property
    def name(self) -> str:
        return "LLMRetryExhaustedError"

    def get_parent_axiom_name(self) -> Optional[str]:
        return "LLMError"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "message":      MemberSpec(name="message",      kind="field", type_ref=TypeRef.of("str")),
            "raw_response": MemberSpec(name="raw_response", kind="field", type_ref=TypeRef.of("str")),
            "max_retry":    MemberSpec(name="max_retry",    kind="field", type_ref=TypeRef.of("int")),
            "cast_to":      _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "LLMRetryExhaustedError")

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("Exception", "LLMError", "LLMRetryExhaustedError")


class LLMCallErrorAxiom(BaseAxiom):
    """Raised when the LLM provider itself fails (network error, timeout, etc.).

    Fields: message (str), raw_response (str), provider_error (str).
    """

    has_converter_cap = True

    @property
    def name(self) -> str:
        return "LLMCallError"

    def get_parent_axiom_name(self) -> Optional[str]:
        return "LLMError"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "message":        MemberSpec(name="message",        kind="field", type_ref=TypeRef.of("str")),
            "raw_response":   MemberSpec(name="raw_response",   kind="field", type_ref=TypeRef.of("str")),
            "provider_error": MemberSpec(name="provider_error", kind="field", type_ref=TypeRef.of("str")),
            "cast_to":        _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "LLMCallError")

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("Exception", "LLMError", "LLMCallError")

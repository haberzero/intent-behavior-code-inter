"""
core/kernel/axioms/primitives/errors.py

Exception and LLM-error axioms.

The 4 LLM-error axiom classes (LLMError, LLMParseError, LLMRetryExhaustedError,
LLMCallError) are structurally identical except for: name, parent, one extra
field, and the is_compatible chain. They share a common base ``_LLMErrorAxiomBase``
that implements the repeated logic; each subclass is a 4-line configuration.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, TYPE_CHECKING

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
            "message": MemberSpec(name="message", kind="field", type_ref=TypeRef.of("str")),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "Exception")

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "Exception"


# ------------------------------------------------------------------ #
# LLM Exception hierarchy                                             #
# ------------------------------------------------------------------ #

class _LLMErrorAxiomBase(BaseAxiom):
    """Shared base for all LLM-originated exception axioms.

    Subclasses configure 4 class-level attributes:
    - ``_axiom_name``:       the type name (e.g. ``"LLMParseError"``)
    - ``_parent_name``:      parent axiom name (``"Exception"`` or ``"LLMError"``)
    - ``_extra_field``:      ``(field_name, type_ref_str)`` tuple or ``None``
    - ``_compatible_chain``: tuple of type names assignable to this type
    """

    has_converter_cap = True

    _axiom_name: str = ""
    _parent_name: Optional[str] = None
    _extra_field: Optional[Tuple[str, str]] = None
    _compatible_chain: Tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self._axiom_name

    def get_parent_axiom_name(self) -> Optional[str]:
        return self._parent_name

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        specs: Dict[str, MethodMemberSpec] = {
            "message":      MemberSpec(name="message",      kind="field", type_ref=TypeRef.of("str")),
            "raw_response": MemberSpec(name="raw_response", kind="field", type_ref=TypeRef.of("str")),
            "cast_to":      _m("cast_to", params=["any"], ret="any"),
        }
        if self._extra_field is not None:
            fname, ftype = self._extra_field
            specs[fname] = MemberSpec(name=fname, kind="field", type_ref=TypeRef.of(ftype))
        return specs

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", self._axiom_name)

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head in self._compatible_chain


class LLMErrorAxiom(_LLMErrorAxiomBase):
    """Base axiom for all LLM-originated exceptions.

    LLMError IS-A Exception, so ``except Exception as e:`` can catch it.
    Fields: message (str), raw_response (str).
    """

    _axiom_name = "LLMError"
    _parent_name = "Exception"
    _extra_field = None
    _compatible_chain = ("Exception", "LLMError")


class LLMParseErrorAxiom(_LLMErrorAxiomBase):
    """Raised when an unprotected LLM assignment's __from_prompt__ fails.

    Fields: message (str), raw_response (str), type_name (str — expected type).
    """

    _axiom_name = "LLMParseError"
    _parent_name = "LLMError"
    _extra_field = ("type_name", "str")
    _compatible_chain = ("Exception", "LLMError", "LLMParseError")


class LLMRetryExhaustedErrorAxiom(_LLMErrorAxiomBase):
    """Raised when a llmexcept-protected assignment exhausts all retries.

    Fields: message (str), raw_response (str), max_retry (int).
    """

    _axiom_name = "LLMRetryExhaustedError"
    _parent_name = "LLMError"
    _extra_field = ("max_retry", "int")
    _compatible_chain = ("Exception", "LLMError", "LLMRetryExhaustedError")


class LLMCallErrorAxiom(_LLMErrorAxiomBase):
    """Raised when the LLM provider itself fails (network error, timeout, etc.).

    Fields: message (str), raw_response (str), provider_error (str).
    """

    _axiom_name = "LLMCallError"
    _parent_name = "LLMError"
    _extra_field = ("provider_error", "str")
    _compatible_chain = ("Exception", "LLMError", "LLMCallError")


# ------------------------------------------------------------------ #
# 线程错误层次（ThreadError/ThreadCancelled/ThreadFailed）                    #
# ------------------------------------------------------------------ #

class _ThreadErrorAxiomBase(_LLMErrorAxiomBase):
    """任务错误公理基类（ThreadError/ThreadCancelled/ThreadFailed 共用）。

    结构同 LLM 错误：IS-A Exception 链，携带 message 字段。
    子类配置 ``_axiom_name``/``_parent_name``/``_compatible_chain``。
    """

    _extra_field = None


class ThreadErrorAxiom(_ThreadErrorAxiomBase):
    """Raised/returned on a thread-level failure (base of task errors)."""

    _axiom_name = "ThreadError"
    _parent_name = "Exception"
    _compatible_chain = ("Exception", "ThreadError")


class ThreadCancelledAxiom(_ThreadErrorAxiomBase):
    """Cancelled 任务错误：线程被协作式取消。"""

    _axiom_name = "ThreadCancelled"
    _parent_name = "ThreadError"
    _compatible_chain = ("Exception", "ThreadError", "ThreadCancelled")


class ThreadFailedAxiom(_ThreadErrorAxiomBase):
    """Failed 任务错误：线程函数体执行失败。"""

    _axiom_name = "ThreadFailed"
    _parent_name = "ThreadError"
    _compatible_chain = ("Exception", "ThreadError", "ThreadFailed")

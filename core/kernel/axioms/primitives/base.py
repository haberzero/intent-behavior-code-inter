"""
core/kernel/axioms/primitives/base.py

Base axiom and the ``_m`` helper shared by every concrete axiom family.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


# ------------------------------------------------------------------ #
# Helper: build a MethodMemberSpec                                    #
# ------------------------------------------------------------------ #

def _m(
    name: str,
    params: Optional[List[str]] = None,
    ret: str = "void",
    is_llm: bool = False,
    mutating: bool = False,
    llmexcept_safe: bool = False,
) -> MethodMemberSpec:
    """Convenience constructor for MethodMemberSpec constants."""
    return MethodMemberSpec(
        name=name,
        kind="llm_method" if is_llm else "method",
        return_type=TypeRef.of(ret), param_types=[TypeRef.of(p) for p in params or []],
        mutating=mutating, llmexcept_safe=llmexcept_safe)


# ------------------------------------------------------------------ #
# Base axiom                                                          #
# ------------------------------------------------------------------ #

class BaseAxiom:
    """
    Default implementations for the unified TypeAxiom interface.

    Concrete axioms override the ``has_*_cap`` flags they support and
    the corresponding capability methods.  Unset capabilities surface
    as ``False`` flags + safe no-op method bodies so callers can rely on
    the flags as a single source of truth.
    """

    # ---- Capability flags (default: not capable) ------------------- #
    has_call_cap: bool = False
    has_iter_cap: bool = False
    has_subscript_cap: bool = False
    has_operator_cap: bool = False
    has_converter_cap: bool = False
    has_parser_cap: bool = False
    has_from_prompt_cap: bool = False
    has_output_hint_cap: bool = False
    has_payload_prompt_cap: bool = False
    has_llm_call_cap: bool = False

    # ---- Method / operator specs ----------------------------------- #
    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {}

    def get_operators(self) -> Dict[str, str]:
        return {}

    # ---- Capability methods (no-op defaults) ----------------------- #
    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return None

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        return None

    def resolve_operation_type_name(
        self, op: str, other_name: Optional[str]
    ) -> Optional[str]:
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return False

    def parse_value(self, raw_value: str) -> Any:
        return raw_value

    def from_prompt(
        self, raw_response: str, spec: Optional["IbSpec"] = None
    ) -> Tuple[bool, Any]:
        return (False, "axiom does not support from_prompt")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return ""

    def __payload_prompt__(
        self, value: Any, spec: Optional["IbSpec"] = None
    ) -> Union[str, Dict[str, Any], List[Dict[str, Any]]]:
        """Multi-modal payload protocol — default returns str(value) (text fallback).

        Concrete axioms for multi-modal types (audio/image/video) override this
        to return structured content blocks (dicts) for LLM API payloads.

        Return values:
        - str: plain text (equivalent to __to_prompt__ behavior)
        - dict: single structured content block (e.g. {"type":"image_url",...})
        - List[dict]: multiple content blocks
        """
        return str(value)

    # ---- Type characteristics -------------------------------------- #
    def is_dynamic(self) -> bool:
        return False

    def is_class(self) -> bool:
        return False

    def is_module(self) -> bool:
        return False

    def is_compatible(self, other_name: str) -> bool:
        return other_name == self.name

    def get_parent_axiom_name(self) -> Optional[str]:
        return "Object"

    def can_return_from_isolated(self) -> bool:
        return False

    def get_diff_hint(self, other_name: str) -> Optional[str]:
        return None

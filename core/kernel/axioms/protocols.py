"""
core/kernel/axioms/protocols.py

Unified TypeAxiom interface — single capability surface (M5).

Design (post-M5 unification)
----------------------------
All capability methods live directly on ``TypeAxiom``.  The previous family
of separate ``CallCapability`` / ``IterCapability`` / ... protocol classes
has been collapsed into a single interface.  Each axiom declares the
capabilities it actually supports via ``has_*_cap`` class attributes; the
default in ``BaseAxiom`` is ``False``.

All type references in method signatures are plain strings (type names) so
the axiom layer remains independent of the spec layer (no circular
imports).

Capability query pattern (kept stable for callers):

    axiom = registry.get_axiom(spec)
    if axiom and axiom.has_operator_cap:
        result_name = axiom.resolve_operation_type_name("+", "float")

The convenience accessor ``SpecRegistry.get_operator_cap(spec)`` returns
the axiom itself when capable, else ``None`` — preserving the truthy-check
idiom used throughout the compiler and runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec
    from core.kernel.spec.member import MethodMemberSpec


# ------------------------------------------------------------------ #
# TypeAxiom — the unified axiom interface                             #
# ------------------------------------------------------------------ #

@runtime_checkable
class TypeAxiom(Protocol):
    """
    Unified axiom interface.  One axiom per built-in type.

    An axiom is a stateless description of a type's *behaviour* expressed
    in plain string type names — it never imports or references the spec
    layer or runtime.

    Capability declaration
    ----------------------
    Concrete axioms set the relevant ``has_*_cap`` class attribute to
    ``True`` to declare which capability methods are implemented; the
    default ``BaseAxiom`` returns ``False`` for every flag and ``None`` /
    no-op for every method.
    """

    # ---- Identity --------------------------------------------------- #
    @property
    def name(self) -> str: ...

    # ---- Capability flags (default False in BaseAxiom) -------------- #
    has_call_cap: bool
    has_iter_cap: bool
    has_subscript_cap: bool
    has_operator_cap: bool
    has_converter_cap: bool
    has_parser_cap: bool
    has_from_prompt_cap: bool
    has_output_hint_cap: bool
    has_llm_call_cap: bool

    # ---- Capability methods (default no-op in BaseAxiom) ------------ #
    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]: ...
    def get_element_type_name(self) -> str: ...
    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]: ...
    def resolve_operation_type_name(
        self, op: str, other_type_name: Optional[str]
    ) -> Optional[str]: ...
    def can_convert_from(self, source_type_name: str) -> bool: ...
    def parse_value(self, raw_value: str) -> Any: ...
    def from_prompt(
        self, raw_response: str, spec: Optional["IbSpec"] = None
    ) -> Tuple[bool, Any]: ...
    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str: ...

    # ---- Method / operator specs ------------------------------------ #
    def get_method_specs(self) -> "Dict[str, MethodMemberSpec]":
        """Return pure-data method signatures for spec.members bootstrapping."""
        ...

    def get_operators(self) -> Dict[str, str]:
        """Map operator symbols to magic method names (e.g. ``{"+": "__add__"}``)."""
        ...

    # ---- Type characteristics --------------------------------------- #
    def is_dynamic(self) -> bool: ...
    def is_compatible(self, other_name: str) -> bool: ...
    def is_class(self) -> bool: ...
    def is_module(self) -> bool: ...
    def can_return_from_isolated(self) -> bool: ...
    def get_parent_axiom_name(self) -> Optional[str]: ...
    def get_diff_hint(self, other_name: str) -> Optional[str]: ...

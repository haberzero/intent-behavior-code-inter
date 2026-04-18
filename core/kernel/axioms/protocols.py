"""
core/kernel/axioms/protocols.py

Pure capability interfaces for the axiom layer.

Key design change from the old version
---------------------------------------
ALL type references are now plain strings (type names) rather than
TypeDescriptor / IbSpec objects.  This makes the axiom layer completely
independent of the spec layer and eliminates the historic circular import.

Capability query pattern:

    axiom = axiom_registry.get_axiom("int")
    cap   = axiom.get_operator_capability()
    if cap:
        result_name = cap.resolve_operation_type_name("+", "float")
        # → "float"

The SpecRegistry then resolves the returned name to an IbSpec.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec
    from core.kernel.spec.member import MethodMemberSpec


# ------------------------------------------------------------------ #
# Capability interfaces                                                #
# ------------------------------------------------------------------ #

class CallCapability(Protocol):
    """Callable: describes how a type is invoked."""
    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        """Return the name of the return type, or None if unresolvable."""
        ...


class IterCapability(Protocol):
    """Iterable: describes the element type when iterating."""
    def get_element_type_name(self) -> str:
        """Return the name of the element type (e.g. ``"any"``)."""
        ...


class SubscriptCapability(Protocol):
    """Subscriptable: describes the item type for ``obj[key]``."""
    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        """Return the item type name, or None if unsupported."""
        ...


class OperatorCapability(Protocol):
    """Operator-capable: describes binary operation result types."""
    def resolve_operation_type_name(
        self, op: str, other_type_name: Optional[str]
    ) -> Optional[str]:
        """Return the result type name for ``self op other``, or None."""
        ...


class ConverterCapability(Protocol):
    """Convertible: can be produced by a cast from another type."""
    def can_convert_from(self, source_type_name: str) -> bool:
        """True if a value of ``source_type_name`` can be cast to this type."""
        ...


class ParserCapability(Protocol):
    """Parseable: can produce a Python native value from a raw string."""
    def parse_value(self, raw_value: str) -> Any:
        """Parse a native Python value from the raw string representation."""
        ...


class FromPromptCapability(Protocol):
    """LLM-parseable: can parse a value from raw LLM output text."""
    def from_prompt(
        self,
        raw_response: str,
        spec: Optional["IbSpec"] = None,
    ) -> Tuple[bool, Any]:
        """
        Parse ``raw_response`` into a native Python value.

        Returns:
            (True, parsed_value)    – success
            (False, retry_hint)     – failure with a hint for LLM retry
        """
        ...


class IlmoutputHintCapability(Protocol):
    """LLM output hint: can generate a format constraint prompt."""
    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        """Return a short string telling the LLM what format to use."""
        ...


class WritableTrait(Protocol):
    """Writable: the signature can be updated post-construction."""
    def update_signature(
        self,
        param_type_names: List[str],
        return_type_name: Optional[str],
    ) -> None: ...


# ------------------------------------------------------------------ #
# TypeAxiom — the core axiom interface                                #
# ------------------------------------------------------------------ #

@runtime_checkable
class TypeAxiom(Protocol):
    """
    Core axiom interface.  One axiom per built-in type.

    An axiom is a stateless description of a type's *behaviour*.
    It knows nothing about other types' structure — it only knows names.

    Rules
    -----
    * Axioms MUST NOT import from core.kernel.spec or any runtime module.
    * All type references in method signatures MUST be plain strings.
    * ``get_method_specs()`` replaces the old ``get_methods()`` and returns
      MethodMemberSpec objects (pure data, no IbSpec references).
    """

    @property
    def name(self) -> str: ...

    # Capability accessors
    def get_call_capability(self) -> Optional[CallCapability]: ...
    def get_iter_capability(self) -> Optional[IterCapability]: ...
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: ...
    def get_operator_capability(self) -> Optional[OperatorCapability]: ...
    def get_converter_capability(self) -> Optional[ConverterCapability]: ...
    def get_parser_capability(self) -> Optional[ParserCapability]: ...
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: ...
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: ...
    def get_writable_trait(self) -> Optional[WritableTrait]: ...
    def get_llm_call_capability(self) -> Optional[Any]: ...

    def get_method_specs(self) -> "Dict[str, MethodMemberSpec]":
        """
        Return pure-data method signatures for spec.members bootstrapping.
        Replaces the old ``get_methods() -> Dict[str, FunctionMetadata]``.
        """
        ...

    def get_operators(self) -> Dict[str, str]:
        """Map operator symbols to magic method names (e.g. ``{"+": "__add__"}``)."""
        ...

    # Type characteristics
    def is_dynamic(self) -> bool: ...
    def is_compatible(self, other_name: str) -> bool: ...
    def is_class(self) -> bool: ...
    def is_module(self) -> bool: ...
    def can_return_from_isolated(self) -> bool: ...

    def get_parent_axiom_name(self) -> Optional[str]: ...

    def get_diff_hint(self, other_name: str) -> Optional[str]: ...

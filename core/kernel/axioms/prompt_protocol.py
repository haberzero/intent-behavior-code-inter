"""
core/kernel/axioms/prompt_protocol.py

Unified Prompt Protocol Registry — formalizes the __prompt__ family of protocols.

Design
------
The __prompt__ protocol family governs how IBCI types interact with LLMs:

1. ``__to_prompt__(self) -> str``
   Serialize an object instance into a string representation that the LLM
   can understand in the prompt context. Called when the object is interpolated
   into an LLM prompt (e.g., ``$variable`` in behavior expressions).

2. ``__from_prompt__(raw: str) -> tuple[bool, any]``
   Parse an LLM text response back into a typed value. Called as a class-level
   method (receives raw LLM output, returns (success, value_or_hint)).
   Must be a classmethod-like (first param is cls/self=class, second is str).

3. ``__outputhint_prompt__() -> str``
   Return a string describing the expected output format to inject into the
   system prompt, guiding the LLM on how to structure its response.
   Class-level method (no instance needed).

4. ``__validate_prompt__(raw: str) -> tuple[bool, str]``  [NEW — optional]
   Pre-flight validation of raw LLM output before __from_prompt__ parsing.
   Returns (is_valid, error_description_or_empty). If not defined, validation
   is skipped (no-op). Allows user types to reject malformed LLM output with
   descriptive errors before attempting full parsing.

Protocol Contracts
------------------
- ``__to_prompt__``: instance method, 0 params (besides self), returns str
- ``__from_prompt__``: class method semantics, 1 param (raw: str), returns tuple[bool, any]
- ``__outputhint_prompt__``: class method semantics, 0 params, returns str
- ``__validate_prompt__``: class method semantics, 1 param (raw: str), returns tuple[bool, str]

This module provides:
- ``PromptProtocolSpec``: Frozen dataclass describing a single protocol method's contract
- ``PROMPT_PROTOCOL_REGISTRY``: Dict mapping protocol names to their specs
- ``validate_prompt_protocol_signature()``: Compile-time helper for semantic passes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


@dataclass(frozen=True)
class PromptProtocolSpec:
    """Specification of a single __prompt__ protocol method.

    Attributes:
        name: Method name (e.g., "__to_prompt__")
        is_instance_method: True if called on instances, False if class-level
        param_count: Expected number of parameters (excluding self/cls)
        param_types: Expected parameter type names (empty for no params)
        return_type: Expected return type name
        is_required: If True, type system should warn when LLM-facing type lacks it
        description: Human-readable description for diagnostics
    """
    name: str
    is_instance_method: bool
    param_count: int
    param_types: Tuple[str, ...] = field(default_factory=tuple)
    return_type: str = "str"
    is_required: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Protocol Definitions
# ---------------------------------------------------------------------------

PROMPT_PROTOCOL_SPECS: Dict[str, PromptProtocolSpec] = {
    "__to_prompt__": PromptProtocolSpec(
        name="__to_prompt__",
        is_instance_method=True,
        param_count=0,
        param_types=(),
        return_type="str",
        is_required=False,
        description="Serialize instance to LLM-visible string representation",
    ),
    "__from_prompt__": PromptProtocolSpec(
        name="__from_prompt__",
        is_instance_method=False,
        param_count=1,
        param_types=("str",),
        return_type="tuple",
        is_required=False,
        description="Parse raw LLM output into typed value; returns (bool, any)",
    ),
    "__outputhint_prompt__": PromptProtocolSpec(
        name="__outputhint_prompt__",
        is_instance_method=False,
        param_count=0,
        param_types=(),
        return_type="str",
        is_required=False,
        description="Provide output format hint for LLM system prompt injection",
    ),
    "__validate_prompt__": PromptProtocolSpec(
        name="__validate_prompt__",
        is_instance_method=False,
        param_count=1,
        param_types=("str",),
        return_type="tuple",
        is_required=False,
        description="Pre-flight validation of raw LLM output before parsing",
    ),
}

# Convenience: set of all protocol method names
PROMPT_PROTOCOL_NAMES: FrozenSet[str] = frozenset(PROMPT_PROTOCOL_SPECS.keys())

# Methods exempt from override signature checks (existing behavior, now formally sourced)
PROMPT_PROTOCOL_SIGNATURE_FREE: FrozenSet[str] = frozenset(PROMPT_PROTOCOL_SPECS.keys())


def validate_prompt_protocol_signature(
    method_name: str,
    declared_param_count: int,
    declared_return_type: Optional[str] = None,
) -> List[str]:
    """Validate a user-defined prompt protocol method against its contract.

    Args:
        method_name: The dunder method name (e.g., "__to_prompt__")
        declared_param_count: Number of params declared (excluding self)
        declared_return_type: Declared return type name, or None if unspecified

    Returns:
        List of diagnostic messages (empty if valid).
        Each message is suitable for use in SEM_xxx warnings.
    """
    spec = PROMPT_PROTOCOL_SPECS.get(method_name)
    if spec is None:
        return []  # Not a prompt protocol method — no validation needed

    diagnostics: List[str] = []

    # Check parameter count
    if declared_param_count != spec.param_count:
        diagnostics.append(
            f"Protocol '{method_name}' expects {spec.param_count} parameter(s) "
            f"(excluding self), but {declared_param_count} declared. "
            f"({spec.description})"
        )

    # Check return type (only if declared and not 'auto'/'any')
    if declared_return_type and declared_return_type not in ("auto", "any", "void"):
        if spec.return_type == "str" and declared_return_type != "str":
            diagnostics.append(
                f"Protocol '{method_name}' should return '{spec.return_type}', "
                f"but '{declared_return_type}' declared."
            )
        # tuple return type check is lenient — we don't enforce tuple subtyping

    return diagnostics


def get_prompt_protocol_spec(method_name: str) -> Optional[PromptProtocolSpec]:
    """Look up the protocol spec for a given method name, or None if not a protocol."""
    return PROMPT_PROTOCOL_SPECS.get(method_name)


def is_prompt_protocol_method(method_name: str) -> bool:
    """Return True if the given method name is a recognized prompt protocol."""
    return method_name in PROMPT_PROTOCOL_NAMES

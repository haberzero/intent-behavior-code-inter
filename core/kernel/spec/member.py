"""
core/kernel/spec/member.py

Pure-data member descriptors stored inside IbSpec.members.

Storage model
-------------
Each member's declared type is stored as a :class:`TypeRef` (frozen, hashable,
structurally recursive).  Resolution happens at call-time via
``SpecRegistry.resolve_typeref(member.type_ref)`` (or, equivalently,
``SpecRegistry.resolve(member.type_ref.head, member.type_ref.module)``).

There are NO object references to IbSpec, Symbol, or any runtime object —
this is what breaks the historic Symbol ↔ TypeDescriptor circular dependency.

Hierarchy
---------
MemberSpec          — base (field or alias)
  MethodMemberSpec  — a callable member (method / llm-method)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .type_ref import TypeRef


_ANY_REF: TypeRef = TypeRef.of("any")
_VOID_REF: TypeRef = TypeRef.of("void")


@dataclass
class MemberSpec:
    """
    Pure-data description of a single member of a class or module.

    The member's declared type is stored as ``type_ref`` (TypeRef).
    """

    name: str
    kind: str  # "field" | "method" | "llm_method"
    type_ref: TypeRef = field(default_factory=lambda: _ANY_REF)
    metadata: dict = field(default_factory=dict)

    def is_method(self) -> bool:
        return self.kind in ("method", "llm_method")

    def is_llm(self) -> bool:
        return self.kind == "llm_method"


@dataclass
class MethodMemberSpec(MemberSpec):
    """
    Pure-data description of a callable member.

    Parameter types and return type are stored as TypeRef values.

    The ``kind`` field defaults to ``"method"``; pass ``kind="llm_method"`` for
    LLM functions.
    """

    kind: str = "method"
    param_types: List[TypeRef] = field(default_factory=list)
    return_type: TypeRef = field(default_factory=lambda: _VOID_REF)

    # Convenience views over TypeRef storage retained because they are
    # genuinely useful (``len(member.param_type_names)`` reads cleaner than
    # ``len(member.param_types)`` though equivalent; both are fine).
    @property
    def param_type_names(self) -> List[str]:
        return [t.head for t in self.param_types]

    @property
    def param_type_modules(self) -> List[Optional[str]]:
        return [t.module for t in self.param_types]

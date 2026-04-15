"""
core/kernel/spec/member.py

Pure-data member descriptors stored inside IbSpec.members.

Key design: ALL type references here are plain strings (type names / module
paths).  There are NO object references to IbSpec, Symbol, or any runtime
object.  This is what breaks the historic Symbol ↔ TypeDescriptor circular
dependency.

Hierarchy
---------
MemberSpec          — base (field or alias)
  MethodMemberSpec  — a callable member (method / llm-method)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MemberSpec:
    """
    Pure-data description of a single member of a class or module.

    ``type_name`` is the unresolved string name of the member's type.
    Resolve it at call-time via ``SpecRegistry.resolve(member.type_name,
    member.type_module)``.
    """

    name: str
    kind: str  # "field" | "method" | "llm_method"
    type_name: str = "any"
    type_module: Optional[str] = None

    def is_method(self) -> bool:
        return self.kind in ("method", "llm_method")

    def is_llm(self) -> bool:
        return self.kind == "llm_method"


@dataclass
class MethodMemberSpec(MemberSpec):
    """
    Pure-data description of a callable member.

    All parameter and return types are stored as plain name strings.
    The ``kind`` field defaults to ``"method"``; set to ``"llm_method"``
    for LLM functions.
    """

    kind: str = "method"

    # Parallel lists: param_type_names[i] is in param_type_modules[i]
    param_type_names: List[str] = field(default_factory=list)
    param_type_modules: List[Optional[str]] = field(default_factory=list)

    return_type_name: str = "void"
    return_type_module: Optional[str] = None

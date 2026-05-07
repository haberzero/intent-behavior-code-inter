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
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .type_ref import TypeRef


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
    metadata: dict = field(default_factory=dict)

    def is_method(self) -> bool:
        return self.kind in ("method", "llm_method")

    def is_llm(self) -> bool:
        return self.kind == "llm_method"

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def type_ref(self) -> "TypeRef":
        """TypeRef for this member's declared type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.type_name, self.type_module)


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

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def return_type_ref(self) -> "TypeRef":
        """TypeRef for the declared return type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.return_type_name, self.return_type_module)

    @property
    def param_type_refs(self) -> "tuple[TypeRef, ...]":
        """Tuple of TypeRefs for declared parameter types."""
        from .type_ref import TypeRef
        mods = list(self.param_type_modules)
        while len(mods) < len(self.param_type_names):
            mods.append(None)
        return tuple(TypeRef.of(n, m) for n, m in zip(self.param_type_names, mods))

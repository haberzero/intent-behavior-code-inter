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
from typing import List, Optional, TYPE_CHECKING

from .type_ref import TypeRef

if TYPE_CHECKING:
    pass


_ANY_REF: TypeRef = TypeRef.of("any")
_VOID_REF: TypeRef = TypeRef.of("void")


@dataclass
class MemberSpec:
    """
    Pure-data description of a single member of a class or module.

    The member's declared type is stored as ``type_ref`` (TypeRef).  Legacy
    ``type_name`` / ``type_module`` accessors are exposed as ``@property``
    derivations and must not be assigned to directly.  Construction accepts
    both ``type_ref=...`` and the legacy ``type_name=...`` / ``type_module=...``
    kwargs (they are normalised to a TypeRef in ``__init__``).
    """

    name: str
    kind: str  # "field" | "method" | "llm_method"
    type_ref: TypeRef = field(default_factory=lambda: _ANY_REF)
    metadata: dict = field(default_factory=dict)

    def __init__(self, *, name: str, kind: str,
                 type_ref: Optional[TypeRef] = None,
                 type_name: Optional[str] = None,
                 type_module: Optional[str] = None,
                 metadata: Optional[dict] = None,
                 # MethodMemberSpec also passes these through this base init
                 # via super().__init__, so accept-and-ignore here.
                 param_types: Optional[List[TypeRef]] = None,
                 return_type: Optional[TypeRef] = None,
                 param_type_names: Optional[List[str]] = None,
                 param_type_modules: Optional[List[Optional[str]]] = None,
                 return_type_name: Optional[str] = None,
                 return_type_module: Optional[str] = None) -> None:
        self.name = name
        self.kind = kind
        self.metadata = metadata if metadata is not None else {}
        if type_ref is not None:
            self.type_ref = type_ref
        else:
            head = type_name if type_name is not None else "any"
            self.type_ref = TypeRef.of(head, type_module)

    def is_method(self) -> bool:
        return self.kind in ("method", "llm_method")

    def is_llm(self) -> bool:
        return self.kind == "llm_method"


@dataclass
class MethodMemberSpec(MemberSpec):
    """
    Pure-data description of a callable member.

    Parameter types and return type are stored as TypeRef values.  Legacy
    ``param_type_names`` / ``param_type_modules`` / ``return_type_name`` /
    ``return_type_module`` accessors remain available as read-only
    ``@property`` derivations; ``__init__`` accepts both forms.

    The ``kind`` field defaults to ``"method"``; pass ``kind="llm_method"`` for
    LLM functions.
    """

    param_types: List[TypeRef] = field(default_factory=list)
    return_type: TypeRef = field(default_factory=lambda: _VOID_REF)

    def __init__(self, *, name: str, kind: str = "method",
                 type_ref: Optional[TypeRef] = None,
                 type_name: Optional[str] = None,
                 type_module: Optional[str] = None,
                 metadata: Optional[dict] = None,
                 param_types: Optional[List[TypeRef]] = None,
                 return_type: Optional[TypeRef] = None,
                 param_type_names: Optional[List[str]] = None,
                 param_type_modules: Optional[List[Optional[str]]] = None,
                 return_type_name: Optional[str] = None,
                 return_type_module: Optional[str] = None) -> None:
        super().__init__(name=name, kind=kind, type_ref=type_ref,
                         type_name=type_name, type_module=type_module,
                         metadata=metadata)
        if param_types is not None:
            self.param_types = list(param_types)
        else:
            names = list(param_type_names or [])
            mods = list(param_type_modules or [])
            while len(mods) < len(names):
                mods.append(None)
            self.param_types = [TypeRef.of(n, m) for n, m in zip(names, mods)]

        if return_type is not None:
            self.return_type = return_type
        else:
            head = return_type_name if return_type_name is not None else "void"
            self.return_type = TypeRef.of(head, return_type_module)

    # Convenience views over TypeRef storage retained because they are
    # genuinely useful (``len(member.param_type_names)`` reads cleaner than
    # ``len(member.param_types)`` though equivalent; both are fine).
    @property
    def param_type_names(self) -> List[str]:
        return [t.head for t in self.param_types]

    @property
    def param_type_modules(self) -> List[Optional[str]]:
        return [t.module for t in self.param_types]

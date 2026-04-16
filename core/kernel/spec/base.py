"""
core/kernel/spec/base.py

IbSpec — the zero-dependency, pure-data foundation of the IBCI type system.

Design principles:
  • No _registry, no _axiom, no runtime state of any kind.
  • Every IbSpec is a plain value record: identity lives in (module_path, name).
  • Capability queries (callable? iterable? which operator result?) go through
    SpecRegistry, which delegates to AxiomRegistry.  Specs themselves are mute.
  • The symbol ↔ type circular dependency is broken by storing member info as
    MemberSpec (pure strings), not as Symbol objects.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .member import MemberSpec


@dataclass(eq=False)
class IbSpec:
    """
    Pure-data description of an IBCI type.

    This is the single source of truth for type identity during both
    compile time and run time.  It intentionally carries no behaviour —
    all capability queries are answered by SpecRegistry (which consults
    AxiomRegistry).

    Naming conventions
    ------------------
    name          : simple (unqualified) name, e.g. ``"int"``, ``"MyClass"``
    module_path   : dotted module qualifier, e.g. ``"my_module"`` or None
    qualified_name: ``f"{module_path}.{name}"`` when module_path is set

    Axiom override
    --------------
    ``_axiom_name`` lets special types (e.g. user-defined Enum subclasses)
    redirect axiom lookups to a different axiom key.  Normally this is None
    and axiom lookups use ``name``.
    """

    name: str = ""
    module_path: Optional[str] = None
    is_nullable: bool = True
    is_user_defined: bool = True

    # Members are MemberSpec objects (pure data, no Symbol references).
    # Populated by the compiler's collector/resolver passes and by axiom
    # method declarations during SpecRegistry bootstrap.
    members: Dict[str, "MemberSpec"] = field(default_factory=dict)

    # Optional override: the axiom key used for capability lookups.
    # Leave as None to use ``name``.
    _axiom_name: Optional[str] = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------ #
    # Identity helpers                                                     #
    # ------------------------------------------------------------------ #

    @property
    def qualified_name(self) -> str:
        """Fully qualified name including module prefix (if any)."""
        if self.module_path:
            return f"{self.module_path}.{self.name}"
        return self.name

    def get_base_name(self) -> str:
        """
        The key used when looking up this spec's axiom in AxiomRegistry.
        Normally equals ``name``; overridable via ``_axiom_name``.
        """
        return self._axiom_name or self.name

    def get_references(self) -> dict:
        """
        Return a dict of cross-reference fields that point to other IbSpec
        objects (or lists of them).  Used by the serializer to walk the type
        graph without hard-coding isinstance checks.

        The default implementation returns an empty dict (no sub-spec refs).
        Subclasses that actually hold IbSpec references should override this.
        Since all concrete specs store type information as name-strings rather
        than live IbSpec objects, the base default is sufficient for most cases.
        """
        return {}

    def is_class(self) -> bool:
        """Return True if this spec describes a class type."""
        from .specs import ClassSpec
        return isinstance(self, ClassSpec)

    # ------------------------------------------------------------------ #
    # Cloning                                                              #
    # ------------------------------------------------------------------ #

    def clone(self) -> "IbSpec":
        """
        Shallow-copy this spec with an independent members dict.
        Since MemberSpec objects are themselves pure data, a shallow copy
        of the members dict is sufficient for isolation.
        """
        cloned = copy.copy(self)
        cloned.members = dict(self.members)
        return cloned

    # ------------------------------------------------------------------ #
    # Repr / str                                                           #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        return self.qualified_name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"

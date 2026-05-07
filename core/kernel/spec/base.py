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
from enum import Enum
from typing import ClassVar, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .member import MemberSpec
    from .type_ref import TypeRef


class TypeKind(str, Enum):
    PRIMITIVE = "primitive"
    FUNCTION = "function"
    CLASS = "class"
    LIST = "list"
    TUPLE = "tuple"
    DICT = "dict"
    OPTIONAL = "optional"
    BOUND_METHOD = "bound_method"
    MODULE = "module"
    DEFERRED = "deferred"
    BEHAVIOR = "behavior"
    CALLABLE_SIG = "callable_sig"
    LAZY = "lazy"


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
    kind: str = TypeKind.PRIMITIVE.value
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
        return self.kind == TypeKind.CLASS.value

    def is_kind(self, *kinds: str) -> bool:
        """Return True if spec.kind matches one of provided kinds."""
        return self.kind in kinds

    # ------------------------------------------------------------------ #
    # [INFO] TypeRef compatibility                                         #
    # ------------------------------------------------------------------ #

    @property
    def type_ref(self) -> "TypeRef":
        """
        Return a TypeRef representing this spec's type identity.

        [INFO] Builds a TypeRef from the existing name/module_path
        fields (and, for generic specs, from the element/key/value type
        fields).  The returned TypeRef is structurally equivalent to what
        the new type system would hold natively.

        This property is read-only and non-caching — TypeRef is cheap to
        construct (frozen dataclass, no registry access required).
        """
        from .type_ref import TypeRef
        return TypeRef.from_spec(self)

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


@dataclass(eq=False)
class TypeDef(IbSpec):
    """
    Unified type-definition data model.

    All former concrete *Spec subclasses (FuncSpec, ClassSpec, ListSpec, …) are
    now aliases for this single class.  Dispatch on the ``kind`` field rather than
    ``isinstance``.
    """

    # -- FuncSpec / CallableSigSpec fields --------------------------------
    param_type_names: List[str] = field(default_factory=list)
    param_type_modules: List[Optional[str]] = field(default_factory=list)
    return_type_name: str = "void"
    return_type_module: Optional[str] = None
    is_llm: bool = False

    # -- ClassSpec fields -------------------------------------------------
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None

    # -- ListSpec / TupleSpec fields --------------------------------------
    element_type_name: str = "any"
    element_type_module: Optional[str] = None
    allowed_element_type_names: List[str] = field(default_factory=list)

    # -- DictSpec fields --------------------------------------------------
    key_type_name: str = "any"
    key_type_module: Optional[str] = None

    # -- DictSpec / DeferredSpec / BehaviorSpec fields (unified) ----------
    value_type_name: str = "any"
    value_type_module: Optional[str] = None

    # -- OptionalSpec fields ----------------------------------------------
    wrapped_type_name: str = "any"
    wrapped_type_module: Optional[str] = None

    # -- BoundMethodSpec fields -------------------------------------------
    receiver_type_name: str = ""
    receiver_type_module: Optional[str] = None
    func_spec_name: str = ""

    # -- DeferredSpec / BehaviorSpec fields -------------------------------
    deferred_mode: str = "lambda"

    # -- ModuleSpec fields ------------------------------------------------
    required_capabilities: List[str] = field(default_factory=list)

    # -- Kind → base-name mapping (used by get_base_name) ----------------
    _KIND_BASE_NAMES: ClassVar[Dict[str, str]] = {}

    def get_base_name(self) -> str:
        if self._axiom_name:
            return self._axiom_name
        return TypeDef._KIND_BASE_NAMES.get(self.kind, self.name)

    # -- TypeRef bridge properties ----------------------------------------

    @property
    def return_type_ref(self) -> "TypeRef":
        from .type_ref import TypeRef
        return TypeRef.of(self.return_type_name, self.return_type_module)

    @property
    def param_type_refs(self) -> "tuple[TypeRef, ...]":
        from .type_ref import TypeRef
        mods = list(self.param_type_modules)
        while len(mods) < len(self.param_type_names):
            mods.append(None)
        return tuple(TypeRef.of(n, m) for n, m in zip(self.param_type_names, mods))

    @property
    def parent_type_ref(self) -> "Optional[TypeRef]":
        if self.parent_name is None:
            return None
        from .type_ref import TypeRef
        return TypeRef.of(self.parent_name, self.parent_module)

    @property
    def element_type_ref(self) -> "TypeRef":
        from .type_ref import TypeRef
        return TypeRef.of(self.element_type_name, self.element_type_module)

    @property
    def key_type_ref(self) -> "TypeRef":
        from .type_ref import TypeRef
        return TypeRef.of(self.key_type_name, self.key_type_module)

    @property
    def value_type_ref(self) -> "TypeRef":
        from .type_ref import TypeRef
        return TypeRef.of(self.value_type_name, self.value_type_module)

    @property
    def wrapped_type_ref(self) -> "TypeRef":
        from .type_ref import TypeRef
        return TypeRef.of(self.wrapped_type_name, self.wrapped_type_module)


TypeDef._KIND_BASE_NAMES = {
    TypeKind.LIST.value:          "list",
    TypeKind.TUPLE.value:         "tuple",
    TypeKind.DICT.value:          "dict",
    TypeKind.OPTIONAL.value:      "Optional",
    TypeKind.BOUND_METHOD.value:  "bound_method",
    TypeKind.MODULE.value:        "module",
    TypeKind.DEFERRED.value:      "deferred",
    TypeKind.BEHAVIOR.value:      "behavior",
    TypeKind.CALLABLE_SIG.value:  "callable_sig",
    TypeKind.LAZY.value:          "module",
}

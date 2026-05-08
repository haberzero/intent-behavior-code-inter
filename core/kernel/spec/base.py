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

from .type_ref import TypeRef as _TypeRef

if TYPE_CHECKING:
    from .member import MemberSpec
    from .type_ref import TypeRef


# Sentinel TypeRef used as default for type fields that have not been set.
# "any" is the universal top type and is used by the existing flat-string
# defaults (``element_type_name = "any"`` etc.).
_ANY_REF = _TypeRef.of("any")


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
    # CALLABLE_INSTANCE unifies the former DEFERRED + BEHAVIOR kinds.
    # A callable instance is a typed value created by `lambda`/`snapshot` (deferred
    # expression) or by `@~...~` (LLM behavior).  At the TYPE level both share the
    # same kind; the runtime dispatch differentiation (regular AST re-evaluation
    # vs LLM invocation) is encoded by the spec's ``name``/``_axiom_name``
    # ("deferred" vs "behavior") and by the runtime value's payload.
    # The capture mode (lambda vs snapshot) is a property of the VALUE
    # (``IbDeferred.capture_mode`` / ``IbBehavior.capture_mode``) and of the
    # creating AST node (``IbLambdaExpr.capture_mode``); it is NOT a property of
    # the type.
    CALLABLE_INSTANCE = "callable_instance"
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

    Storage model
    -------------
    Type-reference fields are stored as :class:`TypeRef` (frozen, hashable,
    structurally recursive).  Legacy flat ``*_name`` / ``*_module`` accessors
    are exposed as read-only ``@property`` derivations from the underlying
    TypeRef storage; they exist to keep call-sites compiling during the
    migration to a fully TypeRef-based API.  Direct attribute writes
    (``spec.return_type_name = "int"``) are no longer supported — write through
    the TypeRef field instead (``spec.return_type = TypeRef.of("int")``).
    """

    # -- Function-like signature (FUNCTION + BOUND_METHOD + CALLABLE_INSTANCE
    #    + CALLABLE_SIG kinds use these). ---------------------------------
    param_types: List["TypeRef"] = field(default_factory=list)
    return_type: "TypeRef" = field(default_factory=lambda: _ANY_REF.replace_head("void"))
    is_llm: bool = False

    # -- Class inheritance (CLASS kind) -----------------------------------
    parent_type: Optional["TypeRef"] = None

    # -- Container element / key / value types (LIST / TUPLE / DICT) -----
    element_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)
    allowed_element_types: List["TypeRef"] = field(default_factory=list)
    key_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)
    value_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)

    # -- Optional[T] (OPTIONAL kind) -------------------------------------
    wrapped_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)

    # -- Bound method receiver (BOUND_METHOD kind) -----------------------
    receiver_type: "TypeRef" = field(default_factory=lambda: _ANY_REF.replace_head(""))
    func_spec_name: str = ""

    # -- ModuleSpec fields ------------------------------------------------
    required_capabilities: List[str] = field(default_factory=list)

    # -- Kind → base-name mapping (used by get_base_name) ----------------
    _KIND_BASE_NAMES: ClassVar[Dict[str, str]] = {}

    def get_base_name(self) -> str:
        if self._axiom_name:
            return self._axiom_name
        return TypeDef._KIND_BASE_NAMES.get(self.kind, self.name)

    # ------------------------------------------------------------------ #
    # Constructor compatibility shim                                      #
    # ------------------------------------------------------------------ #
    # The dataclass ``__init__`` only accepts the new TypeRef-based kwargs
    # (``param_types``, ``return_type``, ``element_type`` …).  Many existing
    # call-sites pass legacy flat-string kwargs (``return_type_name="int"``,
    # ``param_type_modules=[None]`` …).  We override ``__init__`` to accept
    # both forms transparently: legacy strings are converted to TypeRef
    # values before delegating to the dataclass-generated init.
    #
    # Once all call-sites have been migrated to the structured kwargs,
    # this shim can be deleted with no behavioural change.

    _LEGACY_KWARG_TO_FIELD: ClassVar[Dict[str, str]] = {
        "return_type_name":        "return_type",
        "return_type_module":      "return_type",
        "parent_name":             "parent_type",
        "parent_module":           "parent_type",
        "element_type_name":       "element_type",
        "element_type_module":     "element_type",
        "key_type_name":           "key_type",
        "key_type_module":         "key_type",
        "value_type_name":         "value_type",
        "value_type_module":       "value_type",
        "wrapped_type_name":       "wrapped_type",
        "wrapped_type_module":     "wrapped_type",
        "receiver_type_name":      "receiver_type",
        "receiver_type_module":    "receiver_type",
        "param_type_names":        "param_types",
        "param_type_modules":      "param_types",
        "allowed_element_type_names": "allowed_element_types",
    }

    # NOTE: ``__init__`` is intentionally NOT defined here so that ``@dataclass``
    # generates the full structured-kwargs constructor.  After class creation
    # we capture the generated ``__init__`` as ``__dataclass_init__`` and then
    # replace ``TypeDef.__init__`` with a thin wrapper that first normalises
    # legacy ``*_name`` / ``*_module`` kwargs into TypeRef-typed kwargs.
    # See the module-level reassignment below the class.

    @staticmethod
    def _normalise_legacy_kwargs(kwargs: Dict[str, "object"]) -> Dict[str, "object"]:
        """Translate legacy flat-string kwargs into TypeRef-typed kwargs.

        Pairs ``X_name`` / ``X_module`` collapse into a single ``X`` TypeRef.
        Parallel lists ``param_type_names`` / ``param_type_modules`` collapse
        into ``param_types``.  ``parent_name=None`` becomes ``parent_type=None``.
        Already-TypeRef kwargs pass through unchanged.
        """
        from .type_ref import TypeRef

        out: Dict[str, object] = dict(kwargs)

        # Scalar pairs --------------------------------------------------
        scalar_pairs = (
            ("return_type",   "return_type_name",   "return_type_module",   "void"),
            ("element_type",  "element_type_name",  "element_type_module",  "any"),
            ("key_type",      "key_type_name",      "key_type_module",      "any"),
            ("value_type",    "value_type_name",    "value_type_module",    "any"),
            ("wrapped_type",  "wrapped_type_name",  "wrapped_type_module",  "any"),
            ("receiver_type", "receiver_type_name", "receiver_type_module", ""),
        )
        for new_field, name_kw, mod_kw, default_head in scalar_pairs:
            if new_field in out:
                # Caller already supplied the structured field; ignore any
                # legacy companions (they would be redundant).
                out.pop(name_kw, None)
                out.pop(mod_kw, None)
                continue
            if name_kw in out or mod_kw in out:
                head = out.pop(name_kw, default_head)
                module = out.pop(mod_kw, None)
                out[new_field] = TypeRef.of(head, module)

        # Parent (nullable) --------------------------------------------
        if "parent_type" not in out and ("parent_name" in out or "parent_module" in out):
            head = out.pop("parent_name", None)
            module = out.pop("parent_module", None)
            out["parent_type"] = TypeRef.of(head, module) if head else None

        # Parallel lists ------------------------------------------------
        if "param_types" not in out and ("param_type_names" in out or "param_type_modules" in out):
            names = list(out.pop("param_type_names", []) or [])
            mods = list(out.pop("param_type_modules", []) or [])
            while len(mods) < len(names):
                mods.append(None)
            out["param_types"] = [TypeRef.of(n, m) for n, m in zip(names, mods)]
        else:
            # Drop any orphan parallel-list kwargs even when the structured
            # field is supplied (they are redundant and would otherwise
            # raise TypeError on the dataclass init).
            out.pop("param_type_names", None)
            out.pop("param_type_modules", None)

        if "allowed_element_types" not in out and "allowed_element_type_names" in out:
            names = list(out.pop("allowed_element_type_names") or [])
            out["allowed_element_types"] = [TypeRef.of(n) for n in names]

        return out

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # Legacy list / Optional accessors                                    #
    # ------------------------------------------------------------------ #
    # These properties expose the TypeRef storage as plain-string lists or
    # nullable strings.  The scalar ``*_name``/``*_module`` properties have
    # been removed; use ``spec.return_type.head`` / ``spec.element_type.module``
    # etc. directly.  The list / Optional accessors remain because they are
    # genuinely convenient (e.g. ``len(spec.param_type_names)`` is shorter
    # than the equivalent TypeRef-based form) and because mass-migrating
    # every iteration / comparison site is a separate refactor.

    # ------------------------------------------------------------------ #
    # List-typed convenience views                                        #
    # ------------------------------------------------------------------ #
    # These properties return plain-string views over the TypeRef storage
    # for ergonomic iteration / comparison.  They are kept (rather than
    # mass-migrating every iteration site) because they are genuinely
    # convenient — e.g. ``len(spec.param_type_names)`` is much shorter
    # than the equivalent TypeRef-based form.  The corresponding scalar
    # ``*_name`` / ``*_module`` properties have been removed; use
    # ``spec.return_type.head`` / ``spec.parent_type`` etc. directly.

    @property
    def param_type_names(self) -> List[str]:
        return [t.head for t in self.param_types]

    @property
    def param_type_modules(self) -> List[Optional[str]]:
        return [t.module for t in self.param_types]

    # ------------------------------------------------------------------ #
    # Structured TypeRef accessors (clean API)                            #
    # ------------------------------------------------------------------ #

    @property
    def return_type_ref(self) -> "TypeRef":
        return self.return_type

    @property
    def param_type_refs(self) -> "tuple[TypeRef, ...]":
        return tuple(self.param_types)

    @property
    def parent_type_ref(self) -> "Optional[TypeRef]":
        return self.parent_type

    @property
    def element_type_ref(self) -> "TypeRef":
        return self.element_type

    @property
    def key_type_ref(self) -> "TypeRef":
        return self.key_type

    @property
    def value_type_ref(self) -> "TypeRef":
        return self.value_type

    @property
    def wrapped_type_ref(self) -> "TypeRef":
        return self.wrapped_type


TypeDef._KIND_BASE_NAMES = {
    TypeKind.LIST.value:          "list",
    TypeKind.TUPLE.value:         "tuple",
    TypeKind.DICT.value:          "dict",
    TypeKind.OPTIONAL.value:      "Optional",
    TypeKind.BOUND_METHOD.value:  "bound_method",
    TypeKind.MODULE.value:        "module",
    # NOTE: TypeKind.CALLABLE_INSTANCE is intentionally NOT mapped here.
    # Callable-instance prototypes ("deferred"/"behavior") rely on either the
    # spec's own ``name`` (for unparameterised prototypes) or on the
    # ``_axiom_name`` override (for parameterised variants like
    # ``deferred[int]``) to dispatch to the correct axiom.
    TypeKind.CALLABLE_SIG.value:  "callable_sig",
    TypeKind.LAZY.value:          "module",
}

# Capture the dataclass-generated ``__init__`` so the override above can
# delegate to it after legacy-kwarg normalisation.  The override on the class
# body intentionally shadowed the dataclass auto-init at class creation, which
# is why we re-bind it here.
TypeDef.__dataclass_init__ = TypeDef.__init__  # type: ignore[attr-defined]


def _typedef_init_with_legacy_kwargs(self, *args, **kwargs):  # noqa: D401
    kwargs = TypeDef._normalise_legacy_kwargs(kwargs)
    TypeDef.__dataclass_init__(self, *args, **kwargs)  # type: ignore[attr-defined]


TypeDef.__init__ = _typedef_init_with_legacy_kwargs  # type: ignore[assignment]

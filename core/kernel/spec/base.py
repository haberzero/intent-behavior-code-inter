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


# Sentinel TypeRef used as a default placeholder for optional type fields
# that have not been explicitly set.
# "any" is the universal top type used when no specific type constraint is declared.
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
    # CALLABLE_INSTANCE unifies the former FN_CALLABLE + BEHAVIOR kinds.
    # A callable instance is a typed value created by `lambda`/`snapshot` (fn_callable
    # expression) or by `@~...~` (LLM behavior).  At the TYPE level both share the
    # same kind; the runtime dispatch differentiation (regular AST re-evaluation
    # vs LLM invocation) is encoded by the spec's ``name``/``_axiom_name``
    # ("fn_callable" vs "behavior") and by the runtime value's payload.
    # The capture mode (lambda vs snapshot) is a property of the VALUE
    # (``IbFnCallable.capture_mode`` / ``IbBehavior.capture_mode``) and of the
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

    All former concrete *Spec subclasses (function / class / list / dict / tuple
    / optional / bound_method / module / callable_instance / callable_sig /
    lazy) are now folded into this single class — dispatch on the ``kind``
    field rather than ``isinstance``.

    Storage model
    -------------
    Type-reference fields are stored as :class:`TypeRef` (frozen, hashable,
    structurally recursive).  All access goes through the TypeRef API
    (``spec.return_type.head``, ``[t.head for t in spec.param_types]``, …);
    there are no legacy flat-string accessors.
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
    # NS-7: 元组的位置元素类型（`tuple[T1, T2, ...]`）。
    # 与 ``allowed_element_types``（list 的 set-like 多类型 union）正交：
    # ``positional_element_types`` 是按位置异构的、定长有序列表，仅 TUPLE kind
    # 在元素数 ≥ 2 时使用；单类型元组 ``tuple[T]`` 仍走 ``element_type`` 单字段
    # 以保持向后兼容。
    positional_element_types: List["TypeRef"] = field(default_factory=list)
    key_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)
    value_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)

    # -- Optional[T] (OPTIONAL kind) -------------------------------------
    wrapped_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)

    # -- Bound method receiver (BOUND_METHOD kind) -----------------------
    receiver_type: "TypeRef" = field(default_factory=lambda: _ANY_REF.replace_head(""))
    func_spec_name: str = ""

    # -- TypeDef fields ------------------------------------------------
    required_capabilities: List[str] = field(default_factory=list)

    # -- Kind → base-name mapping (used by get_base_name) ----------------
    _KIND_BASE_NAMES: ClassVar[Dict[str, str]] = {}

    def get_base_name(self) -> str:
        if self._axiom_name:
            return self._axiom_name
        return TypeDef._KIND_BASE_NAMES.get(self.kind, self.name)


TypeDef._KIND_BASE_NAMES = {
    TypeKind.LIST.value:          "list",
    TypeKind.TUPLE.value:         "tuple",
    TypeKind.DICT.value:          "dict",
    TypeKind.OPTIONAL.value:      "Optional",
    TypeKind.BOUND_METHOD.value:  "bound_method",
    TypeKind.MODULE.value:        "module",
    # NOTE: TypeKind.CALLABLE_INSTANCE is intentionally NOT mapped here.
    # Callable-instance prototypes ("fn_callable"/"behavior") rely on either the
    # spec's own ``name`` (for unparameterised prototypes) or on the
    # ``_axiom_name`` override (for parameterised variants like
    # ``fn_callable[int]``) to dispatch to the correct axiom.
    TypeKind.CALLABLE_SIG.value:  "callable_sig",
    TypeKind.LAZY.value:          "module",
}

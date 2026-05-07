"""
core/kernel/spec/specs.py

Concrete IbSpec subclasses, one per structural kind of type, plus
the canonical built-in spec constants.

Subclass hierarchy
------------------
IbSpec          (base — generic / primitive)
  FuncSpec      — function / callable type
  ClassSpec     — class type (has parent_name)
  ListSpec      — generic list[T]
  DictSpec      — generic dict[K, V]
  BoundMethodSpec — a method already bound to a receiver
  ModuleSpec    — module / namespace

Built-in constants (module-level singletons)
--------------------------------------------
These are *prototype* specs — pure, immutable, no registry state.
SpecRegistry.register() clones them before storing (giving each
engine instance its own copy).  They are also used directly when
building the SpecFactory's default registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from .base import IbSpec, TypeDef, TypeKind

if TYPE_CHECKING:
    from .type_ref import TypeRef


# ------------------------------------------------------------------ #
# Concrete spec kinds                                                  #
# ------------------------------------------------------------------ #

@dataclass(eq=False)
class FuncSpec(TypeDef):
    """
    Describes a function / callable type.

    For user-defined functions the param/return type names come from the
    compiler resolver.  For built-in functions they come from the axiom's
    get_method_specs() result (see SpecRegistry._bootstrap_axiom_methods).
    """

    is_user_defined: bool = False
    kind: str = field(default=TypeKind.FUNCTION.value, init=False)

    # Parallel lists; index i → param type
    param_type_names: List[str] = field(default_factory=list)
    param_type_modules: List[Optional[str]] = field(default_factory=list)

    return_type_name: str = "void"
    return_type_module: Optional[str] = None

    is_llm: bool = False

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


@dataclass(eq=False)
class ClassSpec(TypeDef):
    """
    Describes a class type.

    ``parent_name`` / ``parent_module`` identify the superclass.
    Resolve via ``SpecRegistry.resolve(parent_name, parent_module)``.
    """

    kind: str = field(default=TypeKind.CLASS.value, init=False)
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def parent_type_ref(self) -> "Optional[TypeRef]":
        """TypeRef for the parent class, or None if no explicit parent."""
        if self.parent_name is None:
            return None
        from .type_ref import TypeRef
        return TypeRef.of(self.parent_name, self.parent_module)


@dataclass(eq=False)
class ListSpec(TypeDef):
    """
    Describes a generic list type.

    Single-type:  list[int]        → element_type_name="int",  allowed_element_type_names=[]
    Multi-type:   list[int, str]   → element_type_name="any",  allowed_element_type_names=["int","str"]
    Bare:         list             → element_type_name="any",  allowed_element_type_names=[]

    For multi-type lists the subscript/iter element type is "any" (the user must cast explicitly);
    the list only accepts elements of the declared types.
    """

    kind: str = field(default=TypeKind.LIST.value, init=False)
    element_type_name: str = "any"
    element_type_module: Optional[str] = None
    # Multi-type element names (empty = single-type or bare list)
    allowed_element_type_names: list = None   # type: ignore[assignment]

    def __post_init__(self):
        if self.allowed_element_type_names is None:
            object.__setattr__(self, 'allowed_element_type_names', [])

    def get_base_name(self) -> str:
        return self._axiom_name or "list"

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def element_type_ref(self) -> "TypeRef":
        """TypeRef for the element type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.element_type_name, self.element_type_module)


@dataclass(eq=False)
class TupleSpec(TypeDef):
    """
    Describes an immutable, fixed-length tuple type: tuple[element_type].
    Unlike ListSpec, tuples are heterogeneous and immutable at runtime.
    """

    kind: str = field(default=TypeKind.TUPLE.value, init=False)
    element_type_name: str = "any"
    element_type_module: Optional[str] = None

    def get_base_name(self) -> str:
        return self._axiom_name or "tuple"

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def element_type_ref(self) -> "TypeRef":
        """TypeRef for the element type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.element_type_name, self.element_type_module)


@dataclass(eq=False)
class DictSpec(TypeDef):
    """
    Describes a generic dict type: dict[key_type, value_type].
    """

    kind: str = field(default=TypeKind.DICT.value, init=False)
    key_type_name: str = "any"
    key_type_module: Optional[str] = None
    value_type_name: str = "any"
    value_type_module: Optional[str] = None

    def get_base_name(self) -> str:
        return self._axiom_name or "dict"

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def key_type_ref(self) -> "TypeRef":
        """TypeRef for the key type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.key_type_name, self.key_type_module)

    @property
    def value_type_ref(self) -> "TypeRef":
        """TypeRef for the value type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.value_type_name, self.value_type_module)


@dataclass(eq=False)
class OptionalSpec(TypeDef):
    """
    Describes an explicit optional type: ``Optional[T]``.

    This is the first step of the null-safety migration: nullability is
    represented at the type level rather than inferred from ``is_nullable``.
    """

    kind: str = field(default=TypeKind.OPTIONAL.value, init=False)
    wrapped_type_name: str = "any"
    wrapped_type_module: Optional[str] = None

    def get_base_name(self) -> str:
        return self._axiom_name or "Optional"

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def wrapped_type_ref(self) -> "TypeRef":
        """TypeRef for the wrapped inner type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.wrapped_type_name, self.wrapped_type_module)


@dataclass(eq=False)
class BoundMethodSpec(TypeDef):
    """
    Describes a bound method (receiver type + original function spec).
    Synthesised at runtime; rarely needs explicit registration.
    """

    kind: str = field(default=TypeKind.BOUND_METHOD.value, init=False)
    receiver_type_name: str = ""
    receiver_type_module: Optional[str] = None
    func_spec_name: str = ""

    def get_base_name(self) -> str:
        return "bound_method"


@dataclass(eq=False)
class ModuleSpec(TypeDef):
    """
    Describes a module (a namespace of exported members).
    """

    kind: str = field(default=TypeKind.MODULE.value, init=False)
    required_capabilities: List[str] = field(default_factory=list)

    def get_base_name(self) -> str:
        return self._axiom_name or "module"


@dataclass(eq=False)
class DeferredSpec(TypeDef):
    """
    Describes a deferred (lambda/snapshot) expression type.

    A deferred expression wraps ANY expression — not just behavior (@~...~) — and
    delays its evaluation until explicitly called.  The ``value_type_name`` records
    the type that the wrapped expression will produce when evaluated.

    This is the axiom-driven replacement for the ad-hoc behavior-only deferred
    mechanism.  ``IbBehavior`` (for LLM behavior expressions) is a *specialisation*
    of the general deferred concept.

    Fields
    ------
    value_type_name : str
        The type the deferred expression evaluates to (e.g. "int", "str", "auto").
    deferred_mode : str
        'lambda' (re-evaluates with fresh context) or 'snapshot' (frozen context).
    """

    kind: str = field(default=TypeKind.DEFERRED.value, init=False)
    value_type_name: str = "auto"
    value_type_module: Optional[str] = None
    deferred_mode: str = "lambda"

    def get_base_name(self) -> str:
        return self._axiom_name or "deferred"

    # [INFO] TypeRef compatibility ------------------------------------

    @property
    def value_type_ref(self) -> "TypeRef":
        """TypeRef for the wrapped expression's result type."""
        from .type_ref import TypeRef
        return TypeRef.of(self.value_type_name, self.value_type_module)


@dataclass(eq=False)
class BehaviorSpec(DeferredSpec):
    """
    Describes a typed behavior (LLM-backed lambda/snapshot) expression.

    BehaviorSpec is the typed variant of DeferredSpec for ``@~...~`` behavior
    expressions.  It carries the same ``value_type_name`` / ``deferred_mode``
    fields as DeferredSpec and additionally preserves the LLM output type at
    compile time.

    Purpose
    -------
    When the user writes::

        int lambda f = @~ compute something ~

    the variable ``f`` is assigned a ``BehaviorSpec(value_type_name="int")``.
    ``SpecRegistry.resolve_return()`` inspects ``value_type_name`` and returns
    the ``int`` spec directly, so ``int result = f()`` compiles without SEM_003.

    Design notes
    ------------
    * ``get_base_name()`` returns ``"behavior"`` so that axiom lookups (via
      ``AxiomRegistry``) correctly resolve to ``BehaviorAxiom``.
    * The spec is NOT registered in ``SpecRegistry`` (ad-hoc instances like
      ``DeferredSpec`` instances are not registered either); it lives only in
      the symbol-table entry for the deferred variable.
    * Upward assignability (``behavior[int]`` into a ``behavior`` slot) works
      because ``BehaviorAxiom.is_compatible("behavior")`` returns True.
    """

    kind: str = field(default=TypeKind.BEHAVIOR.value, init=False)

    def get_base_name(self) -> str:
        return self._axiom_name or "behavior"


@dataclass(eq=False)
class CallableSigSpec(FuncSpec):
    """
    A callable signature constraint produced from a ``fn[(param_types) -> return_type]``
    type annotation node (``IbCallableType``).

    D3: used to enforce structural signature matching at compile time:
    - Parameters typed ``fn[(int, str) -> bool]`` carry the full signature.
    - Inside the function body, calls to such a parameter are structurally
      checked (arg count + type compatibility).
    - At ``fn f = EXPR`` declaration sites, the RHS callable's signature is
      compared against the declared constraint.

    Design notes
    ------------
    * ``name`` is always ``"fn"`` (inherited) so that ``is_dynamic("fn")`` in
      the registry allows any callable on the RHS without blocking assignment.
    * ``get_base_name()`` returns ``"callable_sig"`` so that the registry can
      distinguish this from plain ``FuncSpec`` when needed for structural checks.
    * ``isinstance(spec, FuncSpec)`` is True — ``get_call_cap()`` therefore
      returns the sentinel ``_FUNC_SPEC_CALL_CAP`` automatically.
    * ``resolve_return()`` uses ``return_type_name`` from ``FuncSpec``, giving
      correct compile-time return type inference when calling a ``fn[...]``
      parameter inside the function body.
    """

    kind: str = field(default=TypeKind.CALLABLE_SIG.value, init=False)

    def get_base_name(self) -> str:
        return self._axiom_name or "callable_sig"


@dataclass
class LazySpec(ModuleSpec):
    """
    A deferred module reference used by the compiler scheduler to handle
    cross-file (circular) import dependencies.

    When the scheduler encounters an import whose target module has not yet
    been fully compiled, it creates a ``LazySpec`` as a placeholder.  The
    semantic analyzer will later call ``SpecRegistry.resolve_member()`` which
    transparently resolves the real ``ModuleSpec`` from the registry.

    ``LazySpec`` carries no additional fields beyond the inherited ``name``.
    The registry is NOT embedded here — resolution always goes through the
    ``SpecRegistry`` instance that owns the analysis pass, keeping the spec
    layer side-effect free.
    """

    kind: str = field(default=TypeKind.LAZY.value, init=False)
    is_lazy: bool = field(default=True, init=False, repr=False)

    def get_base_name(self) -> str:
        return "module"


# ------------------------------------------------------------------ #
# Built-in prototype constants                                         #
# ------------------------------------------------------------------ #
# These are *not* registered specs — they are prototypes.
# SpecRegistry.register() will clone them on first registration.

INT_SPEC    = TypeDef(name="int",    kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
FLOAT_SPEC  = TypeDef(name="float",  kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
STR_SPEC    = TypeDef(name="str",    kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
BOOL_SPEC   = TypeDef(name="bool",   kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
VOID_SPEC   = TypeDef(name="void",   kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)
ANY_SPEC    = TypeDef(name="any",    kind=TypeKind.PRIMITIVE.value, is_nullable=True,  is_user_defined=False)
AUTO_SPEC   = TypeDef(name="auto",   kind=TypeKind.PRIMITIVE.value, is_nullable=True,  is_user_defined=False)
NONE_SPEC   = TypeDef(name="None",   kind=TypeKind.PRIMITIVE.value, is_nullable=True,  is_user_defined=False)
SLICE_SPEC  = TypeDef(name="slice",  kind=TypeKind.PRIMITIVE.value, is_nullable=False, is_user_defined=False)

CALLABLE_SPEC   = TypeDef(name="callable", kind=TypeKind.FUNCTION.value, is_nullable=True,  is_user_defined=False)
BEHAVIOR_SPEC   = TypeDef(name="behavior", kind=TypeKind.BEHAVIOR.value, is_nullable=True,  is_user_defined=False)
DEFERRED_SPEC   = DeferredSpec(name="deferred", is_nullable=True, is_user_defined=False)
OPTIONAL_SPEC   = OptionalSpec(name="Optional", is_nullable=True, is_user_defined=False)
EXCEPTION_SPEC  = ClassSpec(name="Exception", is_nullable=True, is_user_defined=False)

# LLM exception hierarchy — ClassSpec with parent_name for proper inheritance chain.
# LLMError IS-A Exception; LLMParseError/LLMRetryExhaustedError/LLMCallError IS-A LLMError.
# Exception itself is also a ClassSpec so user code can write `class MyError(Exception):`.
LLM_ERROR_SPEC = ClassSpec(name="LLMError", is_nullable=True, is_user_defined=False,
                            parent_name="Exception")
LLM_PARSE_ERROR_SPEC = ClassSpec(name="LLMParseError", is_nullable=True, is_user_defined=False,
                                  parent_name="LLMError")
LLM_RETRY_EXHAUSTED_ERROR_SPEC = ClassSpec(name="LLMRetryExhaustedError", is_nullable=True,
                                            is_user_defined=False, parent_name="LLMError")
LLM_CALL_ERROR_SPEC = ClassSpec(name="LLMCallError", is_nullable=True, is_user_defined=False,
                                 parent_name="LLMError")

# fn — callable type inference marker (declaration-time keyword, like auto but for callables)
# 不是一个独立的运行期类型：fn x = myFunc 实际上将 x 的 spec 推导为 myFunc 的具体 callable spec。
FN_SPEC         = TypeDef(name="fn", kind=TypeKind.FUNCTION.value, is_nullable=True,  is_user_defined=False)

# LLM 调用结果类型规格 — IbLLMCallResult 的公理化描述符
LLM_CALL_RESULT_SPEC = TypeDef(name="llm_call_result", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False)

# LLM 不确定结果类型规格 — IbLLMUncertain 的公理化描述符
# 当 LLM 调用重试耗尽时，目标变量被赋值为此类型的单例（而非抛出异常）。
LLM_UNCERTAIN_SPEC = TypeDef(name="llm_uncertain", kind=TypeKind.CLASS.value, is_nullable=True, is_user_defined=False)

BOUND_METHOD_SPEC = BoundMethodSpec(name="bound_method", is_nullable=True, is_user_defined=False)
LIST_SPEC         = ListSpec(name="list",   is_nullable=True,  is_user_defined=False)
TUPLE_SPEC        = TupleSpec(name="tuple", is_nullable=True,  is_user_defined=False)
DICT_SPEC         = DictSpec(name="dict",   is_nullable=True,  is_user_defined=False)
MODULE_SPEC       = ModuleSpec(name="module", is_nullable=False, is_user_defined=False)

ENUM_SPEC = ClassSpec(name="Enum", is_nullable=True, is_user_defined=False,
                      parent_name="Object")
ENUM_SPEC._axiom_name = "enum"

# Intent 意图对象类型规格 — IbIntent 的公理化描述符
INTENT_SPEC = ClassSpec(name="Intent", is_nullable=True, is_user_defined=False,
                        parent_name="Object")

# intent_context 意图上下文类型规格 — IbIntentContext 的公理化描述符（is_class=True）
INTENT_CONTEXT_SPEC = ClassSpec(name="intent_context", is_nullable=True, is_user_defined=False,
                                parent_name="Object")

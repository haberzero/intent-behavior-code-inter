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
from typing import List, Optional

from .base import IbSpec


# ------------------------------------------------------------------ #
# Concrete spec kinds                                                  #
# ------------------------------------------------------------------ #

@dataclass(eq=False)
class FuncSpec(IbSpec):
    """
    Describes a function / callable type.

    For user-defined functions the param/return type names come from the
    compiler resolver.  For built-in functions they come from the axiom's
    get_method_specs() result (see SpecRegistry._bootstrap_axiom_methods).
    """

    is_user_defined: bool = False

    # Parallel lists; index i → param type
    param_type_names: List[str] = field(default_factory=list)
    param_type_modules: List[Optional[str]] = field(default_factory=list)

    return_type_name: str = "void"
    return_type_module: Optional[str] = None

    is_llm: bool = False


@dataclass(eq=False)
class ClassSpec(IbSpec):
    """
    Describes a class type.

    ``parent_name`` / ``parent_module`` identify the superclass.
    Resolve via ``SpecRegistry.resolve(parent_name, parent_module)``.
    """

    parent_name: Optional[str] = None
    parent_module: Optional[str] = None


@dataclass(eq=False)
class ListSpec(IbSpec):
    """
    Describes a generic list type.

    Single-type:  list[int]        → element_type_name="int",  allowed_element_type_names=[]
    Multi-type:   list[int, str]   → element_type_name="any",  allowed_element_type_names=["int","str"]
    Bare:         list             → element_type_name="any",  allowed_element_type_names=[]

    For multi-type lists the subscript/iter element type is "any" (the user must cast explicitly);
    the list only accepts elements of the declared types.
    """

    element_type_name: str = "any"
    element_type_module: Optional[str] = None
    # Multi-type element names (empty = single-type or bare list)
    allowed_element_type_names: list = None   # type: ignore[assignment]

    def __post_init__(self):
        if self.allowed_element_type_names is None:
            object.__setattr__(self, 'allowed_element_type_names', [])

    def get_base_name(self) -> str:
        return self._axiom_name or "list"


@dataclass(eq=False)
class TupleSpec(IbSpec):
    """
    Describes an immutable, fixed-length tuple type: tuple[element_type].
    Unlike ListSpec, tuples are heterogeneous and immutable at runtime.
    """

    element_type_name: str = "any"
    element_type_module: Optional[str] = None

    def get_base_name(self) -> str:
        return self._axiom_name or "tuple"


@dataclass(eq=False)
class DictSpec(IbSpec):
    """
    Describes a generic dict type: dict[key_type, value_type].
    """

    key_type_name: str = "any"
    key_type_module: Optional[str] = None
    value_type_name: str = "any"
    value_type_module: Optional[str] = None

    def get_base_name(self) -> str:
        return self._axiom_name or "dict"


@dataclass(eq=False)
class BoundMethodSpec(IbSpec):
    """
    Describes a bound method (receiver type + original function spec).
    Synthesised at runtime; rarely needs explicit registration.
    """

    receiver_type_name: str = ""
    receiver_type_module: Optional[str] = None
    func_spec_name: str = ""

    def get_base_name(self) -> str:
        return "bound_method"


@dataclass(eq=False)
class ModuleSpec(IbSpec):
    """
    Describes a module (a namespace of exported members).
    """

    required_capabilities: List[str] = field(default_factory=list)

    def get_base_name(self) -> str:
        return self._axiom_name or "module"


@dataclass(eq=False)
class DeferredSpec(IbSpec):
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

    value_type_name: str = "auto"
    value_type_module: Optional[str] = None
    deferred_mode: str = "lambda"

    def get_base_name(self) -> str:
        return self._axiom_name or "deferred"


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

    is_lazy: bool = field(default=True, init=False, repr=False)

    def get_base_name(self) -> str:
        return "module"


# ------------------------------------------------------------------ #
# Built-in prototype constants                                         #
# ------------------------------------------------------------------ #
# These are *not* registered specs — they are prototypes.
# SpecRegistry.register() will clone them on first registration.

INT_SPEC    = IbSpec(name="int",    is_nullable=False, is_user_defined=False)
FLOAT_SPEC  = IbSpec(name="float",  is_nullable=False, is_user_defined=False)
STR_SPEC    = IbSpec(name="str",    is_nullable=False, is_user_defined=False)
BOOL_SPEC   = IbSpec(name="bool",   is_nullable=False, is_user_defined=False)
VOID_SPEC   = IbSpec(name="void",   is_nullable=False, is_user_defined=False)
ANY_SPEC    = IbSpec(name="any",    is_nullable=True,  is_user_defined=False)
AUTO_SPEC   = IbSpec(name="auto",   is_nullable=True,  is_user_defined=False)
NONE_SPEC   = IbSpec(name="None",   is_nullable=True,  is_user_defined=False)
SLICE_SPEC  = IbSpec(name="slice",  is_nullable=False, is_user_defined=False)

CALLABLE_SPEC   = IbSpec(name="callable",    is_nullable=True,  is_user_defined=False)
BEHAVIOR_SPEC   = IbSpec(name="behavior",    is_nullable=True,  is_user_defined=False)
DEFERRED_SPEC   = DeferredSpec(name="deferred", is_nullable=True, is_user_defined=False)
EXCEPTION_SPEC  = IbSpec(name="Exception",   is_nullable=True,  is_user_defined=False)

# LLM exception hierarchy — ClassSpec with parent_name for proper inheritance chain.
# LLMError IS-A Exception; LLMParseError/LLMRetryExhaustedError/LLMCallError IS-A LLMError.
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
FN_SPEC         = IbSpec(name="fn",          is_nullable=True,  is_user_defined=False)

# LLM 调用结果类型规格 — IbLLMCallResult 的公理化描述符
LLM_CALL_RESULT_SPEC = IbSpec(name="llm_call_result", is_nullable=True, is_user_defined=False)

# LLM 不确定结果类型规格 — IbLLMUncertain 的公理化描述符
# 当 LLM 调用重试耗尽时，目标变量被赋值为此类型的单例（而非抛出异常）。
LLM_UNCERTAIN_SPEC = IbSpec(name="llm_uncertain", is_nullable=True, is_user_defined=False)

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

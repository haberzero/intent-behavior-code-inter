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
    Describes a generic list type: list[element_type].
    """

    element_type_name: str = "any"
    element_type_module: Optional[str] = None

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
EXCEPTION_SPEC  = IbSpec(name="Exception",   is_nullable=True,  is_user_defined=False)

BOUND_METHOD_SPEC = BoundMethodSpec(name="bound_method", is_nullable=True, is_user_defined=False)
LIST_SPEC         = ListSpec(name="list",   is_nullable=True,  is_user_defined=False)
TUPLE_SPEC        = TupleSpec(name="tuple", is_nullable=True,  is_user_defined=False)
DICT_SPEC         = DictSpec(name="dict",   is_nullable=True,  is_user_defined=False)
MODULE_SPEC       = ModuleSpec(name="module", is_nullable=False, is_user_defined=False)

ENUM_SPEC = ClassSpec(name="Enum", is_nullable=True, is_user_defined=False,
                      parent_name="Object")
ENUM_SPEC._axiom_name = "enum"

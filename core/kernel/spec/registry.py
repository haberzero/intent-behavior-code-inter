"""
core/kernel/spec/registry.py

SpecRegistry — pure-data type registry with capability delegation.
SpecFactory  — factory for creating IbSpec instances.

Architecture
------------
A SpecRegistry holds a flat dictionary of IbSpec objects keyed by their
qualified name.  It also holds an AxiomRegistry reference.

Capability access pattern (replaces the old spec._axiom.get_xxx()):

    cap = registry.get_call_cap(spec)
    if cap:
        ret_name = cap.resolve_return_type_name(arg_names)

This keeps all capability logic in the axiom layer (which knows behaviour)
and all data in the spec layer (which knows structure).

Specs stored in the registry are clones of the prototypes; this ensures
each engine instance has isolated mutable state (e.g. compiler-registered
user-defined classes do not leak between engines).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base import IbSpec
from .member import MemberSpec, MethodMemberSpec
from .specs import (
    FuncSpec, ClassSpec, ListSpec, TupleSpec, DictSpec, BoundMethodSpec, ModuleSpec, LazySpec,
    INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC, VOID_SPEC, ANY_SPEC, AUTO_SPEC,
    NONE_SPEC, SLICE_SPEC, CALLABLE_SPEC, BEHAVIOR_SPEC, EXCEPTION_SPEC,
    BOUND_METHOD_SPEC, LIST_SPEC, TUPLE_SPEC, DICT_SPEC, MODULE_SPEC, ENUM_SPEC,
)

if TYPE_CHECKING:
    from core.kernel.axioms.registry import AxiomRegistry
    from core.kernel.axioms.protocols import (
        CallCapability, IterCapability, SubscriptCapability,
        OperatorCapability, ConverterCapability,
        FromPromptCapability, IlmoutputHintCapability,
        ParserCapability,
    )


# ------------------------------------------------------------------ #
# SpecFactory                                                          #
# ------------------------------------------------------------------ #

class _FuncSpecCallCapability:
    """
    Sentinel ``CallCapability`` for ``FuncSpec`` and ``BoundMethodSpec`` instances.

    These specs ARE inherently callable (they carry their own parameter and return
    type information).  ``SpecRegistry.resolve_return()`` handles the actual
    return-type inference; this object satisfies the boolean "is callable?" check
    and provides stubs for other capability methods used by the semantic analyser.
    """
    def resolve_return_type_name(self, arg_type_names: list) -> None:
        return None  # Handled by SpecRegistry.resolve_return(FuncSpec, ...)

    def get_writable_trait(self):
        return None

    def get_parser_capability(self):
        return None


_FUNC_SPEC_CALL_CAP = _FuncSpecCallCapability()


class SpecFactory:
    """
    Creates IbSpec instances.

    All type-name parameters are plain strings — no spec objects are
    required as input, so there are no circular reference risks.
    """

    def create_primitive(self, name: str, is_nullable: bool = False) -> IbSpec:
        return IbSpec(name=name, is_nullable=is_nullable, is_user_defined=False)

    def create_func(
        self,
        name: str = "callable",
        param_type_names: Optional[List[str]] = None,
        param_type_modules: Optional[List[Optional[str]]] = None,
        return_type_name: str = "void",
        return_type_module: Optional[str] = None,
        is_user_defined: bool = False,
        is_llm: bool = False,
    ) -> FuncSpec:
        return FuncSpec(
            name=name,
            is_nullable=True,
            is_user_defined=is_user_defined,
            param_type_names=list(param_type_names or []),
            param_type_modules=list(param_type_modules or []),
            return_type_name=return_type_name,
            return_type_module=return_type_module,
            is_llm=is_llm,
        )

    def create_class(
        self,
        name: str,
        module: Optional[str] = None,
        parent_name: Optional[str] = None,
        parent_module: Optional[str] = None,
        is_user_defined: bool = True,
    ) -> ClassSpec:
        return ClassSpec(
            name=name,
            module_path=module,
            is_nullable=True,
            is_user_defined=is_user_defined,
            parent_name=parent_name,
            parent_module=parent_module,
        )

    def create_list(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
    ) -> ListSpec:
        name = f"list[{element_type_name}]" if element_type_name != "any" else "list"
        return ListSpec(
            name=name,
            is_nullable=True,
            is_user_defined=False,
            element_type_name=element_type_name,
            element_type_module=element_type_module,
        )

    def create_dict(
        self,
        key_type_name: str = "any",
        value_type_name: str = "any",
        key_type_module: Optional[str] = None,
        value_type_module: Optional[str] = None,
    ) -> DictSpec:
        name = f"dict[{key_type_name},{value_type_name}]"
        return DictSpec(
            name=name,
            is_nullable=True,
            is_user_defined=False,
            key_type_name=key_type_name,
            key_type_module=key_type_module,
            value_type_name=value_type_name,
            value_type_module=value_type_module,
        )

    def create_tuple(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
    ) -> TupleSpec:
        name = f"tuple[{element_type_name}]" if element_type_name != "any" else "tuple"
        return TupleSpec(
            name=name,
            is_nullable=True,
            is_user_defined=False,
            element_type_name=element_type_name,
            element_type_module=element_type_module,
        )

    def create_bound_method(
        self,
        receiver_type_name: str,
        func_spec_name: str,
        receiver_type_module: Optional[str] = None,
    ) -> BoundMethodSpec:
        return BoundMethodSpec(
            name="bound_method",
            is_nullable=True,
            is_user_defined=False,
            receiver_type_name=receiver_type_name,
            receiver_type_module=receiver_type_module,
            func_spec_name=func_spec_name,
        )

    def create_module(self, name: str, module: Optional[str] = None) -> ModuleSpec:
        return ModuleSpec(
            name=name,
            module_path=module,
            is_nullable=False,
            is_user_defined=False,
        )


# ------------------------------------------------------------------ #
# SpecRegistry                                                         #
# ------------------------------------------------------------------ #

class SpecRegistry:
    """
    Central type registry.

    Stores cloned IbSpec objects by qualified name.
    Delegates all capability queries to the held AxiomRegistry.

    Usage pattern (compiler / runtime):

        spec = registry.resolve("int")       # look up a type
        cap  = registry.get_call_cap(spec)   # query capability
        ret  = registry.resolve_return(spec, [arg_spec])  # type inference
    """

    def __init__(self, axiom_registry: "AxiomRegistry"):
        self._specs: Dict[str, IbSpec] = {}
        self._axiom_registry = axiom_registry
        self.factory = SpecFactory()

    # ---------------------------------------------------------- #
    # Registration                                               #
    # ---------------------------------------------------------- #

    def register(self, spec: IbSpec) -> IbSpec:
        """
        Register a (clone of a) spec.

        If a spec with the same qualified name is already registered,
        the existing one is returned (idempotent for built-ins).
        For user-defined specs the caller may want to force-overwrite;
        use ``register_force`` in that case.
        """
        key = self._key(spec)
        if key in self._specs:
            existing = self._specs[key]
            # Merge members from incoming spec into existing (supports incremental build)
            for mname, mspec in spec.members.items():
                existing.members.setdefault(mname, mspec)
            return existing
        cloned = spec.clone()
        self._specs[key] = cloned
        return cloned

    def register_force(self, spec: IbSpec) -> IbSpec:
        """Register, overwriting any existing entry."""
        key = self._key(spec)
        cloned = spec.clone()
        self._specs[key] = cloned
        return cloned

    def resolve(
        self,
        name: str,
        module: Optional[str] = None,
    ) -> Optional[IbSpec]:
        """
        Look up a spec by (module, name).

        Falls back to an unqualified lookup if the module-qualified key
        is not found.  Returns None if the type is genuinely unknown.
        """
        if module:
            spec = self._specs.get(f"{module}.{name}")
            if spec:
                return spec
        return self._specs.get(name)

    @property
    def all_specs(self) -> Dict[str, IbSpec]:
        return dict(self._specs)

    def get_axiom_registry(self) -> "AxiomRegistry":
        return self._axiom_registry

    # ---------------------------------------------------------- #
    # Capability access (replaces spec.get_xxx_trait())          #
    # ---------------------------------------------------------- #

    def get_axiom(self, spec: Optional[IbSpec]) -> Any:
        """Return the axiom for this spec, or None."""
        if spec is None:
            return None
        return self._axiom_registry.get_axiom(spec.get_base_name())

    def get_call_cap(self, spec: IbSpec) -> Optional["CallCapability"]:
        # FuncSpec and BoundMethodSpec are inherently callable — resolve_return handles them.
        if isinstance(spec, (FuncSpec, BoundMethodSpec)):
            return _FUNC_SPEC_CALL_CAP
        # ClassSpec is callable (constructor)
        if isinstance(spec, ClassSpec):
            return _FUNC_SPEC_CALL_CAP
        axiom = self.get_axiom(spec)
        return axiom.get_call_capability() if axiom else None

    def get_iter_cap(self, spec: IbSpec) -> Optional["IterCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_iter_capability() if axiom else None

    def get_subscript_cap(self, spec: IbSpec) -> Optional["SubscriptCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_subscript_capability() if axiom else None

    def get_operator_cap(self, spec: IbSpec) -> Optional["OperatorCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_operator_capability() if axiom else None

    def get_converter_cap(self, spec: IbSpec) -> Optional["ConverterCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_converter_capability() if axiom else None

    def get_parser_cap(self, spec: IbSpec) -> Optional["ParserCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_parser_capability() if axiom else None

    def get_from_prompt_cap(self, spec: IbSpec) -> Optional["FromPromptCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_from_prompt_capability() if axiom else None

    def get_llm_output_hint_cap(self, spec: IbSpec) -> Optional["IlmoutputHintCapability"]:
        axiom = self.get_axiom(spec)
        return axiom.get_llmoutput_hint_capability() if axiom else None

    # ---------------------------------------------------------- #
    # Derived capability helpers                                 #
    # ---------------------------------------------------------- #

    def is_callable(self, spec: Optional[IbSpec]) -> bool:
        if spec is None:
            return False
        if isinstance(spec, FuncSpec):
            return True
        return self.get_call_cap(spec) is not None

    def is_dynamic(self, spec: Optional[IbSpec]) -> bool:
        """True for any/auto and any axiom that declares itself dynamic."""
        if spec is None:
            return True  # unknown type treated as dynamic
        if spec.name in ("any", "auto"):
            return True
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.is_dynamic())

    def is_class_spec(self, spec: Optional[IbSpec]) -> bool:
        if spec is None:
            return False
        if isinstance(spec, ClassSpec):
            return True
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.is_class())

    def is_module_spec(self, spec: Optional[IbSpec]) -> bool:
        if spec is None:
            return False
        if isinstance(spec, ModuleSpec):
            return True
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.is_module())

    def can_return_from_isolated(self, spec: IbSpec) -> bool:
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.can_return_from_isolated())

    # ---------------------------------------------------------- #
    # Type-inference helpers                                     #
    # ---------------------------------------------------------- #

    def resolve_return(
        self,
        spec: IbSpec,
        arg_specs: List[IbSpec],
    ) -> Optional[IbSpec]:
        """
        Infer the return type when ``spec`` is called with ``arg_specs``.

        For FuncSpec (user-defined / axiom-bootstrapped functions) the
        return type is explicit.  For dynamic callables the axiom is
        consulted.
        """
        if isinstance(spec, FuncSpec):
            return self.resolve(spec.return_type_name, spec.return_type_module) or self.resolve("any")
        # ClassSpec called as constructor returns an instance of itself
        if isinstance(spec, ClassSpec):
            return spec
        axiom = self.get_axiom(spec)
        if axiom:
            cap = axiom.get_call_capability()
            if cap:
                arg_names = [a.get_base_name() for a in arg_specs]
                ret_name = cap.resolve_return_type_name(arg_names)
                if ret_name:
                    return self.resolve(ret_name) or self.resolve("any")
        return None

    def resolve_op(
        self,
        spec: IbSpec,
        op: str,
        other: Optional[IbSpec],
    ) -> Optional[IbSpec]:
        """Infer the result type for a binary operator."""
        axiom = self.get_axiom(spec)
        if axiom:
            cap = axiom.get_operator_capability()
            if cap:
                other_name = other.get_base_name() if other else None
                ret_name = cap.resolve_operation_type_name(op, other_name)
                if ret_name:
                    return self.resolve(ret_name) or self.resolve("any")
        # User-defined class types support == and != by identity
        if isinstance(spec, ClassSpec) and op in ("==", "!="):
            return self.resolve("bool")
        return None

    def resolve_iter_element(self, spec: IbSpec) -> Optional[IbSpec]:
        """Infer the element type of an iterable."""
        if isinstance(spec, (ListSpec, TupleSpec)):
            return self.resolve(spec.element_type_name, spec.element_type_module) or self.resolve("any")
        axiom = self.get_axiom(spec)
        if axiom:
            cap = axiom.get_iter_capability()
            if cap:
                elem_name = cap.get_element_type_name()
                if elem_name:
                    return self.resolve(elem_name) or self.resolve("any")
        return None

    def resolve_subscript(
        self,
        spec: IbSpec,
        key_spec: IbSpec,
    ) -> Optional[IbSpec]:
        """Infer the item type when spec[key] is accessed."""
        if isinstance(spec, (ListSpec, TupleSpec)):
            if key_spec.get_base_name() == "int":
                return self.resolve(spec.element_type_name, spec.element_type_module) or self.resolve("any")
        if isinstance(spec, DictSpec):
            return self.resolve(spec.value_type_name, spec.value_type_module) or self.resolve("any")
        axiom = self.get_axiom(spec)
        if axiom:
            cap = axiom.get_subscript_capability()
            if cap:
                item_name = cap.resolve_item_type_name(key_spec.get_base_name())
                if item_name:
                    return self.resolve(item_name) or self.resolve("any")
        return None

    def resolve_member(self, spec: IbSpec, attr_name: str) -> Optional[IbSpec]:
        """
        Resolve the type of an attribute / method on ``spec``.

        Searches own members first, then the parent class chain.
        For ``LazySpec`` placeholders the real spec is looked up first so
        that cross-file imports resolve correctly during semantic analysis.
        """
        # Transparently resolve lazy placeholders created by the scheduler.
        if isinstance(spec, LazySpec) and not spec.members:
            resolved = self.resolve(spec.name, spec.module_path)
            if resolved and resolved is not spec:
                return self.resolve_member(resolved, attr_name)
            return self.resolve("any")

        member = spec.members.get(attr_name)
        if member is not None:
            if isinstance(member, MethodMemberSpec):
                return FuncSpec(
                    name=attr_name,
                    is_user_defined=spec.is_user_defined,
                    param_type_names=list(member.param_type_names),
                    param_type_modules=list(member.param_type_modules),
                    return_type_name=member.return_type_name,
                    return_type_module=member.return_type_module,
                    is_llm=member.is_llm(),
                )
            # Enum variant access: return the enum class type itself
            if isinstance(spec, ClassSpec) and spec.parent_name == "Enum" and spec.is_user_defined:
                return spec
            return self.resolve(member.type_name, member.type_module) or self.resolve("any")

        # Walk parent chain for class specs
        if isinstance(spec, ClassSpec) and spec.parent_name:
            parent = self.resolve(spec.parent_name, spec.parent_module)
            if parent and parent is not spec:
                return self.resolve_member(parent, attr_name)

        # Dynamic fallback
        if self.is_dynamic(spec):
            return self.resolve("any")

        return None

    def is_assignable(self, src: Optional[IbSpec], target: Optional[IbSpec]) -> bool:
        """
        Check whether a value of type ``src`` can be assigned to a
        variable of type ``target``.
        """
        if src is None or target is None:
            return False
        if src is target:
            return True
        if self.is_dynamic(target):
            return True
        if self.is_dynamic(src):
            return self.is_dynamic(target)

        if src.name == target.name and src.module_path == target.module_path:
            return True

        # Axiom-driven compatibility (e.g. bool isa int, None isa nullable)
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom and src_axiom.is_compatible(target.get_base_name()):
            return True

        # Nullable target accepts None
        if target.is_nullable and src.name == "None":
            return True

        # Class inheritance: walk src's parent chain
        if isinstance(src, ClassSpec) and src.parent_name:
            parent = self.resolve(src.parent_name, src.parent_module)
            if parent and parent is not src:
                return self.is_assignable(parent, target)

        return False

    def get_diff_hint(self, src: IbSpec, target: IbSpec) -> Optional[str]:
        """Return an axiom-provided diagnostic hint for a type mismatch."""
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom and hasattr(src_axiom, "get_diff_hint"):
            return src_axiom.get_diff_hint(target.get_base_name())
        return None

    def resolve_specialization(
        self,
        spec: IbSpec,
        arg_specs: List[IbSpec],
    ) -> Optional[IbSpec]:
        """Resolve a generic type specialisation, e.g. list[int]."""
        axiom = self.get_axiom(spec)
        if axiom and hasattr(axiom, "resolve_specialization"):
            arg_names = [a.get_base_name() for a in arg_specs]
            return axiom.resolve_specialization_by_names(self, arg_names)
        return None

    # ---------------------------------------------------------- #
    # Axiom-method bootstrapping                                 #
    # ---------------------------------------------------------- #

    def _bootstrap_axiom_methods(self) -> None:
        """
        After all axioms and primitive specs are registered, populate
        each spec's members dict with the method signatures declared by
        its axiom.  This replaces the old AxiomHydrator.inject_axioms().
        """
        for key, spec in list(self._specs.items()):
            axiom = self.get_axiom(spec)
            if not axiom:
                continue
            method_specs = axiom.get_method_specs()
            for m_name, m_spec in method_specs.items():
                spec.members.setdefault(m_name, m_spec)

    # ---------------------------------------------------------- #
    # Convenience resolution helpers                             #
    # ---------------------------------------------------------- #

    def resolve_from_value(self, value: Any) -> Optional[IbSpec]:
        """Resolve a spec from a Python native value's type."""
        if isinstance(value, bool):
            return self.resolve("bool")
        if isinstance(value, int):
            return self.resolve("int")
        if isinstance(value, float):
            return self.resolve("float")
        if isinstance(value, str):
            return self.resolve("str")
        if value is None:
            return self.resolve("void")
        return None

    def get_all_modules(self) -> Dict[str, "ModuleSpec"]:
        return {k: v for k, v in self._specs.items() if isinstance(v, ModuleSpec)}

    def get_all_funcs(self) -> Dict[str, "FuncSpec"]:
        return {k: v for k, v in self._specs.items() if isinstance(v, FuncSpec)}

    def get_all_classes(self) -> Dict[str, "ClassSpec"]:
        return {k: v for k, v in self._specs.items() if isinstance(v, ClassSpec)}

    @property
    def all_specs(self) -> Dict[str, IbSpec]:  # type: ignore[override]
        return dict(self._specs)

    @property
    def all_descriptors(self) -> Dict[str, IbSpec]:
        """Alias for all_specs for backward compatibility with ContractValidator."""
        return self.all_specs

    def get_metadata_registry(self) -> "SpecRegistry":
        """Return self. Allows ContractValidator to receive the registry."""
        return self

    # ---------------------------------------------------------- #
    # Internal helpers                                           #
    # ---------------------------------------------------------- #

    @staticmethod
    def _key(spec: IbSpec) -> str:
        if spec.module_path:
            return f"{spec.module_path}.{spec.name}"
        return spec.name


# ------------------------------------------------------------------ #
# Default registry factory                                            #
# ------------------------------------------------------------------ #

def create_default_spec_registry(axiom_registry: "AxiomRegistry") -> SpecRegistry:
    """
    Create and populate a SpecRegistry with all built-in primitive specs.
    Replaces the old ``create_default_registry()`` from kernel/factory.py.
    """
    reg = SpecRegistry(axiom_registry)

    for proto in (
        INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC, VOID_SPEC,
        ANY_SPEC, AUTO_SPEC, NONE_SPEC, SLICE_SPEC,
        CALLABLE_SPEC, BEHAVIOR_SPEC, EXCEPTION_SPEC,
        BOUND_METHOD_SPEC, LIST_SPEC, TUPLE_SPEC, DICT_SPEC, MODULE_SPEC,
        ENUM_SPEC,
    ):
        reg.register(proto)

    # Populate method members from axioms
    reg._bootstrap_axiom_methods()

    return reg

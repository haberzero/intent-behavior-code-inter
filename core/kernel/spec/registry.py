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

from .base import IbSpec, TypeDef, TypeKind
from .member import MemberSpec, MethodMemberSpec
from .type_ref import TypeRef
from .specs import (
    INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC, VOID_SPEC, ANY_SPEC, AUTO_SPEC, FN_SPEC,
    NONE_SPEC, SLICE_SPEC, CALLABLE_SPEC, BEHAVIOR_SPEC, DEFERRED_SPEC, OPTIONAL_SPEC, EXCEPTION_SPEC,
    BOUND_METHOD_SPEC, LIST_SPEC, TUPLE_SPEC, DICT_SPEC, MODULE_SPEC, ENUM_SPEC,
    LLM_CALL_RESULT_SPEC, LLM_UNCERTAIN_SPEC, INTENT_SPEC, INTENT_CONTEXT_SPEC,
    LLM_ERROR_SPEC, LLM_PARSE_ERROR_SPEC, LLM_RETRY_EXHAUSTED_ERROR_SPEC, LLM_CALL_ERROR_SPEC,
)
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from core.kernel.axioms.registry import AxiomRegistry
    from core.kernel.axioms.protocols import TypeAxiom


# ------------------------------------------------------------------ #
# SpecFactory                                                          #
# ------------------------------------------------------------------ #


class SpecFactory:
    """
    Creates IbSpec instances.

    All type-name parameters are plain strings — no spec objects are
    required as input, so there are no circular reference risks.
    """

    def create_primitive(self, name: str, is_nullable: bool = False) -> IbSpec:
        return IbSpec(name=name, kind=TypeKind.PRIMITIVE.value, is_nullable=is_nullable, is_user_defined=False)

    def create_func(
        self,
        name: str = "callable",
        param_type_names: Optional[List[str]] = None,
        param_type_modules: Optional[List[Optional[str]]] = None,
        return_type_name: str = "void",
        return_type_module: Optional[str] = None,
        is_user_defined: bool = False,
        is_llm: bool = False,
    ) -> "TypeDef":
        names = list(param_type_names or [])
        mods = list(param_type_modules or [])
        while len(mods) < len(names):
            mods.append(None)
        return TypeDef(
            name=name,
            kind=TypeKind.FUNCTION.value,
            is_nullable=True,
            is_user_defined=is_user_defined,
            is_llm=is_llm,
            return_type=TypeRef.of(return_type_name, return_type_module),
            param_types=[TypeRef.of(n, m) for n, m in zip(names, mods)],
        )

    def create_class(
        self,
        name: str,
        module: Optional[str] = None,
        parent_name: Optional[str] = None,
        parent_module: Optional[str] = None,
        is_user_defined: bool = True,
    ) -> "TypeDef":
        parent_type = TypeRef.of(parent_name, parent_module) if parent_name else None
        return TypeDef(
            name=name,
            kind=TypeKind.CLASS.value,
            module_path=module,
            is_nullable=True,
            is_user_defined=is_user_defined,
            parent_type=parent_type,
        )

    def create_list(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
        allowed_element_type_names: Optional[list] = None,
    ) -> "TypeDef":
        if allowed_element_type_names:
            sorted_names = sorted(allowed_element_type_names)
            list_name = f"list[{','.join(sorted_names)}]"
            return TypeDef(
                name=list_name,
                kind=TypeKind.LIST.value,
                is_nullable=True,
                is_user_defined=False,
                element_type=TypeRef.of("any"),
                allowed_element_types=[TypeRef.of(n) for n in allowed_element_type_names],
            )
        list_name = f"list[{element_type_name}]" if element_type_name != "any" else "list"
        return TypeDef(
            name=list_name,
            kind=TypeKind.LIST.value,
            is_nullable=True,
            is_user_defined=False,
            element_type=TypeRef.of(element_type_name, element_type_module),
        )

    def create_dict(
        self,
        key_type_name: str = "any",
        value_type_name: str = "any",
        key_type_module: Optional[str] = None,
        value_type_module: Optional[str] = None,
    ) -> "TypeDef":
        return TypeDef(
            name=f"dict[{key_type_name},{value_type_name}]",
            kind=TypeKind.DICT.value,
            is_nullable=True,
            is_user_defined=False,
            key_type=TypeRef.of(key_type_name, key_type_module),
            value_type=TypeRef.of(value_type_name, value_type_module),
        )

    def create_tuple(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
    ) -> "TypeDef":
        tuple_name = f"tuple[{element_type_name}]" if element_type_name != "any" else "tuple"
        return TypeDef(
            name=tuple_name,
            kind=TypeKind.TUPLE.value,
            is_nullable=True,
            is_user_defined=False,
            element_type=TypeRef.of(element_type_name, element_type_module),
        )

    def create_bound_method(
        self,
        receiver_type_name: str,
        func_spec_name: str,
        receiver_type_module: Optional[str] = None,
    ) -> "TypeDef":
        return TypeDef(
            name="bound_method",
            kind=TypeKind.BOUND_METHOD.value,
            is_nullable=True,
            is_user_defined=False,
            func_spec_name=func_spec_name,
            receiver_type=TypeRef.of(receiver_type_name, receiver_type_module),
        )

    def create_module(self, name: str, module: Optional[str] = None) -> "TypeDef":
        return TypeDef(
            name=name,
            kind=TypeKind.MODULE.value,
            module_path=module,
            is_nullable=False,
            is_user_defined=False,
        )

    def create_deferred(
        self,
        value_type_name: str = "auto",
        value_type_module: Optional[str] = None,
    ) -> "TypeDef":
        """Create a TypeDef describing a deferred (lambda/snapshot) expression.

        Capture mode (``lambda`` vs ``snapshot``) is a property of the *value*
        (``IbDeferred.capture_mode``) and of the creating AST node
        (``IbLambdaExpr.capture_mode``); it is intentionally NOT stored on the
        type spec.
        """
        deferred_name = f"deferred[{value_type_name}]" if value_type_name != "auto" else "deferred"
        spec = TypeDef(
            name=deferred_name,
            kind=TypeKind.CALLABLE_INSTANCE.value,
            is_nullable=True,
            is_user_defined=False,
            value_type=TypeRef.of(value_type_name, value_type_module),
        )
        # Route axiom dispatch to the "deferred" axiom even for parameterised
        # specs like "deferred[int]".
        spec._axiom_name = "deferred"
        return spec

    def create_optional(
        self,
        wrapped_type_name: str = "any",
        wrapped_type_module: Optional[str] = None,
    ) -> "TypeDef":
        """Create an Optional[T] spec."""
        return TypeDef(
            name=f"Optional[{wrapped_type_name}]",
            kind=TypeKind.OPTIONAL.value,
            is_nullable=True,
            is_user_defined=False,
            wrapped_type=TypeRef.of(wrapped_type_name, wrapped_type_module),
        )

    def create_behavior(
        self,
        value_type_name: str = "auto",
        value_type_module: Optional[str] = None,
    ) -> "TypeDef":
        """
        Create a ``TypeDef`` for a typed ``@~...~`` deferred behavior expression.

        ``value_type_name`` is the LLM output type declared by the user (e.g. "int",
        "str").  When it is ``"auto"`` the compiler cannot infer the return type at
        call sites (same behaviour as before this feature was introduced).

        Capture mode (``lambda`` vs ``snapshot``) lives on the *value*
        (``IbBehavior.capture_mode``), not on the type.

        Example::

            # fn f = lambda -> int: @~...~  →  create_behavior(value_type_name="int")
            factory.create_behavior(value_type_name="int")
        """
        beh_name = f"behavior[{value_type_name}]" if value_type_name != "auto" else "behavior"
        spec = TypeDef(
            name=beh_name,
            kind=TypeKind.CALLABLE_INSTANCE.value,
            is_nullable=True,
            is_user_defined=False,
            value_type=TypeRef.of(value_type_name, value_type_module),
        )
        # Route axiom dispatch to the "behavior" axiom even for parameterised
        # specs like "behavior[int]".
        spec._axiom_name = "behavior"
        return spec


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

    def resolve_typeref(self, ref: "TypeRef") -> Optional[IbSpec]:
        """
        Look up a spec by TypeRef compatibility entry point.

        For non-generic TypeRefs this delegates to ``resolve(head, module)``.
        For generic TypeRefs (e.g. list[int]) it first attempts to look up
        the fully-encoded canonical name, then falls back to the base type.

        This method is the primary resolution path for new code that already
        holds a TypeRef and needs an IbSpec for capability queries.
        """
        if ref.args:
            # Try canonical name first (e.g. "list[int]", "dict[str,int]")
            result = self.resolve(ref.canonical_name, ref.module)
            if result is not None:
                return result
        # Fall back to bare head name (works for non-generic and base-type lookup)
        return self.resolve(ref.head, ref.module)

    @property
    def all_specs(self) -> Dict[str, IbSpec]:
        return dict(self._specs)

    def get_axiom_registry(self) -> "AxiomRegistry":
        return self._axiom_registry

    # ---------------------------------------------------------- #
    # Capability access (unified post-M5)                        #
    # ---------------------------------------------------------- #
    #
    # All capability accessors return the axiom itself when the axiom
    # declares the corresponding ``has_*_cap`` flag, else ``None``.
    # This preserves the truthy-check idiom used throughout the compiler
    # and runtime ( ``if cap: cap.method()`` ) while collapsing the
    # legacy per-capability Protocol classes into a single TypeAxiom
    # interface.
    #
    # For ``get_call_cap``, structural callables (FUNCTION / BOUND_METHOD /
    # CALLABLE_SIG / CLASS) carry their own callability and return ``True``
    # as a non-None marker; ``resolve_return()`` handles the actual return
    # type inference for these structural specs.

    def get_axiom(self, spec: Optional[IbSpec]) -> Optional["TypeAxiom"]:
        """Return the axiom for this spec, or None."""
        if spec is None:
            return None
        return self._axiom_registry.get_axiom(spec.get_base_name())

    def get_call_cap(self, spec: Optional[IbSpec]) -> Optional["TypeAxiom"]:
        if spec is None:
            return None
        # Structural callables carry their signature directly on the spec —
        # ``resolve_return()`` handles return-type inference for them.
        # We return the axiom (if any) so callers can still query other
        # capability methods; if no axiom exists we fall back to a truthy
        # marker (the spec itself) to satisfy ``if call_trait:`` checks.
        if spec.kind in (
            TypeKind.FUNCTION.value,
            TypeKind.BOUND_METHOD.value,
            TypeKind.CALLABLE_SIG.value,
            TypeKind.CLASS.value,
        ):
            axiom = self.get_axiom(spec)
            return axiom if (axiom and axiom.has_call_cap) else spec
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_call_cap) else None

    def get_iter_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_iter_cap) else None

    def get_subscript_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_subscript_cap) else None

    def get_operator_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_operator_cap) else None

    def get_converter_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        """Return the converter capability for ``spec``, or None.

        ``can_convert_from(src)`` answers "can *this* target type accept an
        explicit cast FROM src?" — the target-side query for explicit casts.
        This is intentionally distinct from ``is_compatible(target)`` which
        is the source-side query for *implicit* assignment compatibility.

        TODO (deferred): activate this in
        ``semantic_analyzer.py::_resolve_cast_expr()`` once compile-time
        cast validation is added.  Currently ``IbCastExpr`` validation is
        purely runtime via ``value.receive("cast_to", [target_class])``.
        """
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_converter_cap) else None

    def get_parser_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_parser_cap) else None

    def get_from_prompt_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_from_prompt_cap) else None

    def get_llm_output_hint_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        axiom = self.get_axiom(spec)
        return axiom if (axiom and axiom.has_output_hint_cap) else None

    # ---------------------------------------------------------- #
    # Derived capability helpers                                 #
    # ---------------------------------------------------------- #

    def is_callable(self, spec: Optional[IbSpec]) -> bool:
        if spec is None:
            return False
        if spec.kind in (TypeKind.FUNCTION.value, TypeKind.BOUND_METHOD.value, TypeKind.CALLABLE_SIG.value):
            return True
        return self.get_call_cap(spec) is not None

    def is_callable_instance(self, spec: Optional[IbSpec]) -> bool:
        """True when spec represents a callable instance (deferred / behavior).

        Callable instances are values produced by ``lambda``/``snapshot``
        expressions or by ``@~...~`` LLM behaviors.  At the type level they all
        share ``TypeKind.CALLABLE_INSTANCE``; the runtime distinguishes regular
        deferred-expression evaluation from LLM behavior invocation via the
        spec's axiom name (``"deferred"`` vs ``"behavior"``) and via the value's
        payload type.
        """
        if spec is None:
            return False
        return spec.kind == TypeKind.CALLABLE_INSTANCE.value

    def is_behavior(self, spec: Optional[IbSpec]) -> bool:
        """True when spec is a callable instance dispatched to the LLM behavior axiom."""
        if spec is None:
            return False
        return spec.kind == TypeKind.CALLABLE_INSTANCE.value and spec.get_base_name() == "behavior"

    def is_dynamic(self, spec: Optional[IbSpec]) -> bool:
        """True for any/auto and any axiom that declares itself dynamic."""
        if spec is None:
            return True  # unknown type treated as dynamic
        if spec.name in ("any", "auto", "fn"):
            return True
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.is_dynamic())

    def is_class_spec(self, spec: Optional[IbSpec]) -> bool:
        if spec is None:
            return False
        if spec.kind == TypeKind.CLASS.value:
            return True
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.is_class())

    def is_module_spec(self, spec: Optional[IbSpec]) -> bool:
        if spec is None:
            return False
        if spec.kind == TypeKind.MODULE.value:
            return True
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.is_module())

    def can_return_from_isolated(self, spec: IbSpec) -> bool:
        axiom = self.get_axiom(spec)
        return bool(axiom and axiom.can_return_from_isolated())

    # ---------------------------------------------------------- #
    # Type-inference helpers                                     #
    # ---------------------------------------------------------- #

    def get_base_spec(self, spec: Optional["IbSpec"]) -> Optional["IbSpec"]:
        """
        Return the unspecialised base spec for a generic type.

        For specialised specs (e.g. ``list[int]``, ``dict[str,int]``) the name
        encodes the type arguments, but the axiom and capability lookup is always
        keyed on the base name (``list``, ``dict``).  Use this helper whenever
        you need to query capabilities or perform semantic classification on a
        type and want to tolerate generic specialisations transparently.

        Examples::

            get_base_spec(list[int])  → list spec
            get_base_spec(dict[str,int]) → dict spec
            get_base_spec(int)        → int spec  (already base)
            get_base_spec(None)       → None
        """
        if spec is None:
            return None
        base_name = spec.get_base_name()
        if base_name != spec.name:
            return self.resolve(base_name) or spec
        return spec

    def resolve_return(
        self,
        spec: IbSpec,
        arg_specs: List[IbSpec],
    ) -> Optional[IbSpec]:
        """
        Infer the return type when ``spec`` is called with ``arg_specs``.

        For TypeDef (user-defined / axiom-bootstrapped functions) the
        return type is explicit.  For dynamic callables the axiom is
        consulted.

        TypeDef / TypeDef with a concrete ``value_type_name``
        (i.e. not ``"auto"`` / ``"any"``) return the declared value type
        directly, enabling compile-time type inference at call sites:

            fn f = lambda -> int: @~ compute something ~
            int result = f()   # resolves to int, no SEM_003
        """
        if spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
            ret_ref = getattr(spec, "return_type", None)
            if ret_ref is not None and ret_ref.head:
                return self.resolve_typeref(ret_ref) or self.resolve("any")
        # TypeDef called as constructor returns an instance of itself
        if spec.kind == TypeKind.CLASS.value:
            return spec
        # Typed deferred / behavior: carry the expected value type explicitly.
        if spec.kind == TypeKind.CALLABLE_INSTANCE.value:
            v_ref = getattr(spec, "value_type", None)
            if v_ref is not None and v_ref.head not in ("auto", "any", "", None):
                return self.resolve_typeref(v_ref) or self.resolve("auto")
        axiom = self.get_axiom(spec)
        if axiom and axiom.has_call_cap:
            arg_names = [a.get_base_name() for a in arg_specs]
            ret_name = axiom.resolve_return_type_name(arg_names)
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
        if axiom and axiom.has_operator_cap:
            other_name = other.get_base_name() if other else None
            ret_name = axiom.resolve_operation_type_name(op, other_name)
            if ret_name:
                return self.resolve(ret_name) or self.resolve("any")
        # None 比较：任何类型均可与 None 用 == 或 != 比较，返回 bool
        if op in ("==", "!=") and (spec.name == "None" or (other and other.name == "None")):
            return self.resolve("bool")
        # User-defined class types support == and != by identity
        if spec.kind == TypeKind.CLASS.value and op in ("==", "!="):
            return self.resolve("bool")
        # All user-defined class instances support 'not' via IbObject.__not__ base implementation
        if spec.kind == TypeKind.CLASS.value and op == "not" and other is None:
            return self.resolve("bool")
        return None

    def resolve_iter_element(self, spec: IbSpec) -> Optional[IbSpec]:
        """Infer the element type of an iterable."""
        if spec.kind in (TypeKind.LIST.value, TypeKind.TUPLE.value):
            # Multi-type list: element access returns any (user must cast explicitly)
            if spec.kind == TypeKind.LIST.value and getattr(spec, 'allowed_element_type_names', None):
                return self.resolve("any")
            return self.resolve(spec.element_type.head, spec.element_type.module) or self.resolve("any")
        axiom = self.get_axiom(spec)
        if axiom and axiom.has_iter_cap:
            elem_name = axiom.get_element_type_name()
            if elem_name:
                return self.resolve(elem_name) or self.resolve("any")
        return None

    def resolve_subscript(
        self,
        spec: IbSpec,
        key_spec: IbSpec,
    ) -> Optional[IbSpec]:
        """Infer the item type when spec[key] is accessed."""
        if spec.kind in (TypeKind.LIST.value, TypeKind.TUPLE.value):
            if key_spec.get_base_name() == "int":
                # Multi-type list: subscript access returns any
                if spec.kind == TypeKind.LIST.value and getattr(spec, 'allowed_element_type_names', None):
                    return self.resolve("any")
                return self.resolve(spec.element_type.head, spec.element_type.module) or self.resolve("any")
        if spec.kind == TypeKind.DICT.value:
            return self.resolve(spec.value_type.head, spec.value_type.module) or self.resolve("any")
        axiom = self.get_axiom(spec)
        if axiom and axiom.has_subscript_cap:
            item_name = axiom.resolve_item_type_name(key_spec.get_base_name())
            if item_name:
                return self.resolve(item_name) or self.resolve("any")
        return None

    def resolve_member(self, spec: IbSpec, attr_name: str) -> Optional[IbSpec]:
        """
        Resolve the type of an attribute / method on ``spec``.

        Searches own members first, then the parent class chain.
        For ``TypeDef`` placeholders the real spec is looked up first so
        that cross-file imports resolve correctly during semantic analysis.
        """
        # Transparently resolve lazy placeholders created by the scheduler.
        if spec.kind == TypeKind.LAZY.value and not spec.members:
            resolved = self.resolve(spec.name, spec.module_path)
            if resolved and resolved is not spec:
                return self.resolve_member(resolved, attr_name)
            return self.resolve("any")

        member = spec.members.get(attr_name)
        if member is not None:
            if isinstance(member, MethodMemberSpec):
                # G2/G3: For specialized generic containers, override the return type of
                # methods that return the element/value type.
                # Override is applied regardless of the axiom's declared return type —
                # specialization is based on the container's runtime type parameter.
                #
                # TypeDef[T]:
                #   pop()         → T  (was "any")
                #   __getitem__() → T  (was "any", G3)
                # TypeDef[K,V]:
                #   pop(key)  → V  (was "any")
                #   get(key)  → V  (was "any", G3)
                #   values()  → list[V]  (was bare "list", G3)
                #   keys()    → list[K]  (was bare "list", G3)
                effective_return = member.return_type.head
                effective_return_module = member.return_type.module

                if (
                    spec.kind == TypeKind.LIST.value
                    # Multi-type lists (list[int,str,...]) have allowed_element_types set and
                    # use element_type="any" intentionally — skip G3 specialization for them.
                    and not spec.allowed_element_types
                ):
                    elem = spec.element_type.head
                    if elem != "any" and attr_name in ("pop", "__getitem__"):
                        effective_return = elem
                        effective_return_module = spec.element_type.module
                elif spec.kind == TypeKind.DICT.value:
                    val = spec.value_type.head
                    key = spec.key_type.head
                    if attr_name in ("pop", "get") and val != "any":
                        # G3: dict[K,V].get(key) → V  (same as pop)
                        effective_return = val
                        effective_return_module = spec.value_type.module
                    elif attr_name == "values" and val != "any":
                        # G3: dict[K,V].values() → list[V]
                        # Eagerly register list[V] if not yet in registry so that
                        # resolve_return (called by visit_IbCall) can find it by name.
                        list_v_name = f"list[{val}]"
                        if not self.resolve(list_v_name):
                            list_base = self.resolve("list")
                            elem_spec = self.resolve(val) or self.resolve("any")
                            if list_base and elem_spec:
                                self.resolve_specialization(list_base, [elem_spec])
                        effective_return = list_v_name
                        effective_return_module = None
                    elif attr_name == "keys" and key != "any":
                        # G3: dict[K,V].keys() → list[K]
                        list_k_name = f"list[{key}]"
                        if not self.resolve(list_k_name):
                            list_base = self.resolve("list")
                            key_spec = self.resolve(key) or self.resolve("any")
                            if list_base and key_spec:
                                self.resolve_specialization(list_base, [key_spec])
                        effective_return = list_k_name
                        effective_return_module = None

                # G2: specialize write-method parameter types for list[T].
                # append(item: any) → append(item: T)
                # insert(idx: int, item: any) → insert(idx: int, item: T)
                # __setitem__(idx: int, value: any) → __setitem__(idx: int, value: T)
                effective_params = list(member.param_type_names)
                # Ensure parallel module list has the same length (may be shorter than names).
                raw_modules: List[Optional[str]] = list(member.param_type_modules)
                while len(raw_modules) < len(effective_params):
                    raw_modules.append(None)
                effective_param_modules = raw_modules
                if (
                    spec.kind == TypeKind.LIST.value
                    and attr_name in ("append", "insert", "__setitem__")
                    and spec.element_type.head != "any"
                    and not spec.allowed_element_types
                ):
                    elem = spec.element_type.head
                    elem_mod = spec.element_type.module
                    # last param is always the element (value/item)
                    if effective_params:
                        effective_params[-1] = elem
                        effective_param_modules[-1] = elem_mod
                elif spec.kind == TypeKind.OPTIONAL.value:
                    wrapped = spec.wrapped_type.head
                    wrapped_mod = spec.wrapped_type.module
                    if wrapped != "any" and attr_name in ("unwrap", "or_else"):
                        effective_return = wrapped
                        effective_return_module = wrapped_mod
                    if wrapped != "any" and attr_name == "or_else" and effective_params:
                        # Optional[T].or_else(default) expects default of type T.
                        effective_params[0] = wrapped
                        effective_param_modules[0] = wrapped_mod
                from .base import TypeDef
                return TypeDef(
                    name=attr_name,
                    kind=TypeKind.FUNCTION.value,
                    is_user_defined=spec.is_user_defined,
                    is_llm=member.is_llm(),
                    return_type=TypeRef.of(effective_return, effective_return_module),
                    param_types=[TypeRef.of(n, m) for n, m in zip(effective_params, effective_param_modules)],
                )
            # Enum variant access: return the enum class type itself
            if (spec.kind == TypeKind.CLASS.value and spec.parent_type is not None
                    and spec.parent_type.head == "Enum" and spec.is_user_defined):
                return spec
            return self.resolve_typeref(member.type_ref) or self.resolve("any")

        # Walk parent chain for class specs
        if spec.kind == TypeKind.CLASS.value and spec.parent_type is not None:
            parent = self.resolve_typeref(spec.parent_type)
            if parent and parent is not spec:
                return self.resolve_member(parent, attr_name)

        # Dynamic fallback
        if self.is_dynamic(spec):
            return self.resolve("any")

        return None

    def is_assignable(self, src: Optional[IbSpec], target: Optional[IbSpec],
                       _visited: Optional[frozenset] = None) -> bool:
        """
        Check whether a value of type ``src`` can be assigned to a
        variable of type ``target``.

        ``_visited`` is an internal cycle-guard set used when walking the
        class inheritance chain; callers should never pass it explicitly.
        """
        if src is None or target is None:
            return False
        if src is target:
            return True
        if self.is_dynamic(target):
            return True
        if self.is_dynamic(src):
            if self.is_dynamic(target):
                return True
            # A dynamic callable (fn / auto) can be assigned to any callable slot,
            # including typed TypeDef/TypeDef (e.g. `fn f = make_adder()`).
            if self.is_callable(target):
                return True
            return False

        if target.kind == TypeKind.OPTIONAL.value:
            inner_target = self.resolve(target.wrapped_type.head, target.wrapped_type.module) or self.resolve("any")
            if src.name == "None":
                return True
            if src.kind == TypeKind.OPTIONAL.value:
                inner_src = self.resolve(src.wrapped_type.head, src.wrapped_type.module) or self.resolve("any")
                return self.is_assignable(inner_src, inner_target, _visited)
            return self.is_assignable(src, inner_target, _visited)

        if src.kind == TypeKind.OPTIONAL.value:
            return False

        if src.name == target.name and src.module_path == target.module_path:
            return True

        # Multi-type list compatibility: list[int,str] is assignable to list or list[int,str]
        if src.kind == TypeKind.LIST.value and target.kind == TypeKind.LIST.value:
            src_allowed = getattr(src, 'allowed_element_type_names', None) or []
            tgt_allowed = getattr(target, 'allowed_element_type_names', None) or []
            if src_allowed or tgt_allowed:
                # If target is bare list, accept any list variant
                if not tgt_allowed and target.element_type.head == "any":
                    return True
                # If target has allowed types, source must have same or subset
                if tgt_allowed and src_allowed:
                    return set(src_allowed) == set(tgt_allowed)
                # Single-type target, multi-type source: relaxed — allow
                return True

        # Axiom-driven compatibility (e.g. bool isa int)
        # Pass the full target name so axioms can handle typed variants like "deferred[int]".
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom and src_axiom.is_compatible(target.name):
            return True

        # Class inheritance: walk src's parent chain.
        # _visited guards against malformed circular inheritance declarations.
        if src.kind == TypeKind.CLASS.value and src.parent_type is not None:
            visit_key = f"{src.name}@{src.module_path or ''}"
            visited = _visited or frozenset()
            if visit_key in visited:
                # Cycle detected in inheritance chain — stop traversal.
                return False
            parent = self.resolve_typeref(src.parent_type)
            if parent and parent is not src:
                return self.is_assignable(parent, target, visited | {visit_key})

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
        """Resolve a generic type specialisation, e.g. list[int].

        Special case: ``fn[TYPE]`` — internal subscript for expression-side return-type inference.
        ``fn f = lambda -> int: EXPR`` causes the semantic analyser to build a
        ``TypeDef(value_type_name="int")`` via this path.  This enables
        call-site inference: ``int r = f()`` compiles without SEM_003.
        """
        # Special case: fn[RETURN_TYPE] → TypeDef(value_type_name=RETURN_TYPE)
        if spec.name == "fn" and arg_specs:
            value_type = arg_specs[0]
            return self.factory.create_deferred(
                value_type_name=value_type.name,
                value_type_module=getattr(value_type, 'module_path', None),
            )

        if spec.name == "Optional" and arg_specs:
            value_type = arg_specs[0]
            result = self.register(self.factory.create_optional(
                wrapped_type_name=value_type.name,
                wrapped_type_module=getattr(value_type, "module_path", None),
            ))
            # Keep Optional[T] behavior consistent with other specialized specs.
            optional_axiom = self._axiom_registry.get_axiom("Optional")
            if optional_axiom:
                method_specs = optional_axiom.get_method_specs()
                for m_name, m_spec in method_specs.items():
                    result.members.setdefault(m_name, m_spec)
            return result

        # G1: early-cache hit — avoid allocating a temporary spec when the
        # specialisation is already registered (e.g. repeated list[int] refs).
        # Use spec.name (full name with type params) rather than get_base_name()
        # so that nested generics like list[list[int]] key correctly.
        if arg_specs:
            arg_names = [a.name for a in arg_specs]
            if len(arg_names) == 1:
                candidate_key = f"{spec.name}[{arg_names[0]}]"
            else:
                sorted_names = sorted(arg_names)
                candidate_key = f"{spec.name}[{','.join(sorted_names)}]"
            cached = self.resolve(candidate_key)
            if cached is not None:
                return cached

        axiom = self.get_axiom(spec)
        if axiom and hasattr(axiom, "resolve_specialization_by_names"):
            if not arg_specs:
                arg_names_inner: List[str] = []
            else:
                arg_names_inner = arg_names  # already computed above
            result = axiom.resolve_specialization_by_names(self, arg_names_inner)
            if result is not None:
                # Bootstrap axiom methods for the newly registered specialised spec.
                # _bootstrap_axiom_methods() ran at init time before this spec existed,
                # so we must populate its members here using the same axiom.
                method_specs = axiom.get_method_specs()
                for m_name, m_spec in method_specs.items():
                    result.members.setdefault(m_name, m_spec)
            return result
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
            # Uncertain 字面量哨兵：Uncertain 关键字被解析为此特殊字符串
            if value == "__IBCI_UNCERTAIN_LITERAL__":
                return self.resolve("llm_uncertain")
            return self.resolve("str")
        if value is None:
            return self.resolve("None")
        return None

    def get_all_modules(self) -> Dict[str, IbSpec]:
        return {k: v for k, v in self._specs.items() if v.kind == TypeKind.MODULE.value}

    def get_all_funcs(self) -> Dict[str, IbSpec]:
        return {k: v for k, v in self._specs.items() if v.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value)}

    def get_all_classes(self) -> Dict[str, IbSpec]:
        return {k: v for k, v in self._specs.items() if v.kind == TypeKind.CLASS.value}

    @property
    def all_specs(self) -> Dict[str, IbSpec]:  # type: ignore[override]
        return dict(self._specs)

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
        ANY_SPEC, AUTO_SPEC, FN_SPEC, NONE_SPEC, SLICE_SPEC,
        CALLABLE_SPEC, BEHAVIOR_SPEC, DEFERRED_SPEC, EXCEPTION_SPEC,
        OPTIONAL_SPEC, BOUND_METHOD_SPEC, LIST_SPEC, TUPLE_SPEC, DICT_SPEC, MODULE_SPEC,
        ENUM_SPEC, LLM_CALL_RESULT_SPEC, LLM_UNCERTAIN_SPEC, INTENT_SPEC, INTENT_CONTEXT_SPEC,
        LLM_ERROR_SPEC, LLM_PARSE_ERROR_SPEC, LLM_RETRY_EXHAUSTED_ERROR_SPEC, LLM_CALL_ERROR_SPEC,
    ):
        reg.register(proto)

    # Populate method members from axioms
    reg._bootstrap_axiom_methods()

    return reg

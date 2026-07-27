"""
core/kernel/spec/registry/_capabilities.py

_CapabilityMixin — capability accessors that delegate to the AxiomRegistry.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from ..base import IbSpec, TypeKind

if TYPE_CHECKING:
    from core.kernel.axioms.protocols import TypeAxiom


class _CapabilityMixin:
    # ---------------------------------------------------------- #
    # Capability access                                          #
    # ---------------------------------------------------------- #
    #
    # All capability accessors return the axiom itself when the axiom
    # declares the corresponding ``has_*_cap`` flag, else ``None``.
    # This preserves the truthy-check idiom used throughout the compiler
    # and runtime ( ``if cap: cap.method()`` ) while collapsing the
    # per-capability Protocol classes into a single TypeAxiom
    # interface.
    #
    # For ``get_call_cap``, structural callables (FUNCTION / BOUND_METHOD /
    # CALLABLE_SIG / CLASS) carry their own callability and return ``True``
    # as a non-None marker; ``resolve_call_return()`` handles the actual
    # return type inference for these structural specs.

    def _get_cap(self, spec: Optional[IbSpec], flag_attr: str) -> Optional["TypeAxiom"]:
        """Shared helper: return axiom if it has the named capability flag, else None."""
        if spec is None:
            return None
        axiom = self.get_axiom(spec)
        return axiom if (axiom and getattr(axiom, flag_attr)) else None

    def get_call_cap(self, spec: Optional[IbSpec]) -> Optional["TypeAxiom"]:
        if spec is None:
            return None
        # Structural callables carry their signature directly on the spec —
        # ``resolve_call_return()`` handles return-type inference for them.
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
        return self._get_cap(spec, "has_iter_cap")

    def get_subscript_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        return self._get_cap(spec, "has_subscript_cap")

    def get_operator_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        return self._get_cap(spec, "has_operator_cap")

    def get_converter_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        """Return the converter capability for ``spec``, or None.

        ``can_convert_from(src)`` answers "can *this* target type accept an
        explicit cast FROM src?" — the target-side query for explicit casts.
        This is intentionally distinct from ``is_compatible(target)`` which
        is the source-side query for *implicit* assignment compatibility.

        Used by TypeCheckingPass.visit_IbCastExpr for compile-time SEM_091
        warnings.  Runtime ``IbCastExpr`` still validates via
        ``value.receive("cast_to", [target_class])``.
        """
        return self._get_cap(spec, "has_converter_cap")

    def get_parser_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        return self._get_cap(spec, "has_parser_cap")

    def get_from_prompt_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        return self._get_cap(spec, "has_from_prompt_cap")

    def get_llm_output_hint_cap(self, spec: IbSpec) -> Optional["TypeAxiom"]:
        return self._get_cap(spec, "has_output_hint_cap")

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
        """True when spec represents a callable instance (fn_callable / behavior).

        Callable instances are values produced by ``lambda``/``snapshot``
        expressions or by ``@~...~`` LLM behaviors.  At the type level they all
        share ``TypeKind.CALLABLE_INSTANCE``; the runtime distinguishes regular
        fn_callable expression execution from LLM behavior invocation via the
        spec's axiom name (``"fn_callable"`` vs ``"behavior"``) and via the value's
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

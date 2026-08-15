"""
core/kernel/spec/registry/_protocol.py — Protocol membership mixin.

This mixin gives SpecRegistry the ability to answer protocol-membership
questions.  It is the first step toward replacing scattered capability
flags with a single protocol abstraction.

The implementation intentionally preserves existing permissiveness for
dynamic types: ``any`` / ``auto`` / dynamic axioms satisfy every protocol,
matching the gradual nature of IBCI's type system.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ..base import IbSpec, TypeKind
from core.kernel.protocol import ProtocolDef, ProtocolRegistry


class _ProtocolMixin:
    # ---------------------------------------------------------- #
    # Protocol registry access                                    #
    # ---------------------------------------------------------- #

    def get_protocol(self, name: str) -> Optional[ProtocolDef]:
        """Return the protocol definition, or None if unknown."""
        protocols: ProtocolRegistry = self.protocols
        return protocols.get(name)

    def register_protocol(self, protocol: ProtocolDef) -> ProtocolDef:
        """Register a protocol definition in this engine's registry."""
        return self.protocols.register(protocol)

    def protocol_names(self) -> Tuple[str, ...]:
        return tuple(self.protocols.names())

    def protocol_methods(self, name: str) -> Tuple[str, ...]:
        protocol = self.get_protocol(name)
        return protocol.methods if protocol is not None else ()

    def get_protocol_cap(self, spec: Optional[IbSpec], protocol_name: str):
        """Return the axiom that provides a protocol capability, if any.

        This is a convenience for callers that need the axiom object after
        confirming protocol satisfaction.  It returns None when the protocol
        is not satisfied or no axiom is registered for the type.
        """
        if not self.satisfies_protocol(spec, protocol_name):
            return None
        return self.get_axiom(spec)
    def protocol_methods(self, name: str) -> Tuple[str, ...]:
        protocol = self.get_protocol(name)
        return protocol.methods if protocol is not None else ()

    # ---------------------------------------------------------- #
    # Protocol satisfaction                                       #
    # ---------------------------------------------------------- #

    def satisfies_protocol(self, spec: Optional[IbSpec], protocol_name: str) -> bool:
        """Return True when ``spec`` satisfies the named protocol.

        Dynamic types are considered to satisfy every protocol (existing
        gradual-typing permissiveness).  Built-in protocol satisfaction is
        derived from axiom capability flags and class member tables.

        This is the single entry point that future user-defined protocol
        checks should also use.
        """
        if spec is None:
            return False
        if self.is_dynamic(spec):
            return True
        # A protocol declaration is not itself an implementation.
        if spec.kind == TypeKind.PROTOCOL.value:
            return False
        protocol = self.get_protocol(protocol_name)
        if protocol is None:
            return False

        # Callable has a dedicated structural path.
        if protocol_name == "callable":
            return self.is_callable(spec)

        axiom = self.get_axiom(spec)

        # Built-in capability flags (kept as the current source of truth
        # until the axiom layer is fully protocol-driven).
        if protocol_name == "iterable":
            if spec.kind in (TypeKind.LIST.value, TypeKind.TUPLE.value, TypeKind.GENERATOR.value):
                return True
            if axiom is not None and axiom.has_iter_cap:
                return True
            return self._class_has_any_method(spec, ("__iter__",))

        if protocol_name == "subscriptable":
            if spec.kind in (TypeKind.LIST.value, TypeKind.TUPLE.value, TypeKind.DICT.value):
                return True
            if axiom is not None and axiom.has_subscript_cap:
                return True
            return self._class_has_any_method(spec, ("__getitem__",))

        if protocol_name == "operator":
            if axiom is not None and axiom.has_operator_cap:
                return True
            return self._class_has_any_method(spec, protocol.methods)

        if protocol_name == "converter":
            if axiom is not None and axiom.has_converter_cap:
                return True
            return self._class_has_any_method(spec, ("cast_to",))

        if protocol_name == "parser":
            if axiom is not None and axiom.has_parser_cap:
                return True
            return self._class_has_any_method(spec, ("parse_value",))

        if protocol_name == "from_prompt":
            if axiom is not None and axiom.has_from_prompt_cap:
                return True
            return self._class_has_any_method(spec, ("__from_prompt__",))

        if protocol_name == "output_hint":
            if axiom is not None and axiom.has_output_hint_cap:
                return True
            return self._class_has_any_method(spec, ("__outputhint_prompt__",))

        if protocol_name == "payload_prompt":
            if axiom is not None and axiom.has_payload_prompt_cap:
                return True
            return self._class_has_any_method(spec, ("__payload_prompt__",))

        if protocol_name == "snapshotable":
            return self._class_has_all_methods(spec, ("__snapshot__", "__restore__"))

        # Generic user-defined/forward protocol: structural satisfaction by
        # required method names on the class chain.
        if protocol.methods:
            return self._class_has_all_methods(spec, protocol.methods)
        return False

    # ---------------------------------------------------------- #
    # Internal helpers                                            #
    # ---------------------------------------------------------- #

    def _class_has_any_method(self, spec: IbSpec, method_names: Tuple[str, ...]) -> bool:
        """True when any of the named methods exists on the class chain."""
        seen = set()
        cur: Optional[IbSpec] = spec
        while cur is not None:
            key = (getattr(cur, "module_path", None), getattr(cur, "name", None))
            if key in seen:
                break
            seen.add(key)
            members = getattr(cur, "members", None) or {}
            if any(name in members for name in method_names):
                return True
            parent_ref = getattr(cur, "parent_type", None)
            if parent_ref is None:
                break
            cur = self.resolve_typeref(parent_ref)
        return False

    def _class_has_all_methods(self, spec: IbSpec, method_names: Tuple[str, ...]) -> bool:
        return all(self._class_has_any_method(spec, (name,)) for name in method_names)

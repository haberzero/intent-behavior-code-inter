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

from typing import FrozenSet, Optional, Tuple

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
        result = self.protocols.register(protocol)
        # 协议方法名索引失效（dunder 分派索引以注册表为权威源）
        self._dunder_names_cache = None
        return result

    def dunder_names(self) -> FrozenSet[str]:
        """并集：全部协议 methods 的方法名集合（receive dunder 分派索引权威源）。

        从协议注册表派生（单一权威），惰性缓存；新协议注册时失效重建。
        供运行时 receive 分派判断"消息名是否协议方法"。
        """
        cached = getattr(self, "_dunder_names_cache", None)
        if cached is None:
            names: set = set()
            for protocol in self.protocols.all():
                names.update(protocol.methods)
            cached = frozenset(names)
            self._dunder_names_cache = cached
        return cached

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

    def type_param_bound_errors(
        self,
        spec: Optional[IbSpec],
        arg_specs: list,
    ) -> list:
        """Return a list of human-readable bound violations for a generic class.

        ``spec`` is a generic class TypeDef with ``type_params`` and
        ``type_param_bounds``.  Each type argument is checked against the
        protocol bound declared for the corresponding type parameter.
        """
        if spec is None:
            return []
        type_params = list(getattr(spec, "type_params", None) or [])
        bounds = dict(getattr(spec, "type_param_bounds", None) or {})
        if not bounds:
            return []
        errors = []
        for param, arg in zip(type_params, arg_specs):
            bound = bounds.get(param)
            if bound and not self.satisfies_protocol(arg, bound):
                arg_name = getattr(arg, "name", str(arg))
                errors.append(
                    f"Type argument '{arg_name}' for '{param}' does not satisfy "
                    f"protocol '{bound}'"
                )
        return errors

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

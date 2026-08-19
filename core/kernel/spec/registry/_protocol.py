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
        return self.protocols.register(protocol)

    def dunder_names(self) -> FrozenSet[str]:
        """并集：全部协议 methods 的方法名集合（receive dunder 分派索引权威源）。

        从协议注册表派生（单一权威），按注册表版本号惰性缓存——任何注册路径
        （register_protocol / register_from_spec / 直接 registry.register）均经
        ProtocolRegistry.register 递增版本，索引随版本失效重建。
        """
        version = self.protocols.version
        cached = getattr(self, "_dunder_names_cache", None)
        if cached is None or cached[0] != version:
            names: set = set()
            for protocol in self.protocols.all():
                names.update(protocol.methods)
            cached = (version, frozenset(names))
            self._dunder_names_cache = cached
        return cached[1]

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
        derived from the **protocol entry's satisfaction declaration**
        (数据驱动：kind 特判集 / axiom 能力字段名 / 结构成员判定，
        替代协议名硬编码 if 链；布尔字段为 axiom 声明值，协议条目为
        "协议 ↔ 能力"映射的单一权威)。

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

        # Callable has a dedicated structural path (结构化 kind + axiom cap 合成，
        # 无法以单一字段声明表达——保留专用路径)。
        if protocol_name == "callable":
            return self.is_callable(spec)

        # 数据驱动判定（协议条目声明，单一权威）：
        # 1. kind 特判集；2. axiom 能力字段；3. 结构成员。
        if protocol.kinds and spec.kind in protocol.kinds:
            return True
        if protocol.axiom_cap:
            axiom = self.get_axiom(spec)
            if axiom is not None and getattr(axiom, protocol.axiom_cap, False):
                return True
        structural = protocol.structural_methods or protocol.methods
        if structural:
            # has_declaration：条目是否携带内置判定声明（kinds/axiom_cap/
            # structural_methods 任一）——无声明（用户/前向协议）按 required
            # methods 全部结构判定（与既有通用路径一致）。
            has_declaration = bool(protocol.kinds or protocol.axiom_cap or protocol.structural_methods)
            if protocol.structural_all or not has_declaration:
                return self._class_has_all_methods(spec, structural)
            return self._class_has_any_method(spec, structural)
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

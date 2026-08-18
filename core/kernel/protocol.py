"""
core/kernel/protocol.py — Protocol kernel model.

This module introduces a first-class protocol abstraction into the IBCI
kernel.  It is intentionally minimal for the first protocol-kernel
refactor: it models protocols as named collections of method signatures,
and lets the SpecRegistry answer "does this type satisfy this protocol".

The long-term goal is a complete trait/type-class system.  This first step
does not expose user syntax; it only gives the kernel a single authority
for protocol identity and protocol membership, replacing scattered magic
strings and ad-hoc capability flags.

Design principles:
- Protocol identity is a plain value (name + methods), like TypeRef.
- A ProtocolRegistry is per-SpecRegistry, so engine isolation is preserved.
- Existing capabilities/dunders are modelled as built-in protocols.
- Future user-defined protocols can reuse the same registry and membership
  resolution path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from core.kernel.spec.base import TypeKind


@dataclass(frozen=True)
class ProtocolDef:
    """A named protocol with a set of required method names.

    ``methods`` are the *canonical* method names that implementations must
    provide.  For built-in dunder protocols these are the dunder names.
    For future user protocols these will be ordinary method names.

    ``kinds`` / ``axiom_cap`` / ``structural_methods`` / ``structural_all``
    are the **satisfaction declaration** (阶段 C): they data-drive
    ``SpecRegistry.satisfies_protocol``——kind 特判集、axiom 能力字段名、
    结构成员判定（任意/全部）。内置协议在条目内声明判定（单一权威，替代
    satisfies 内部 if 链）；用户协议（无内置声明）按 required methods
    全部结构判定。
    """

    name: str
    methods: Tuple[str, ...] = ()
    description: str = ""
    parent: Optional[str] = None
    kinds: Tuple[str, ...] = ()
    axiom_cap: Optional[str] = None
    structural_methods: Tuple[str, ...] = ()
    structural_all: bool = False

    def requires(self, method: str) -> bool:
        return method in self.methods


class ProtocolRegistry:
    """Per-engine registry of protocol definitions.

    This is the single authority for "which protocols exist".  It does not
    answer "which types implement a protocol"; that is the responsibility of
    SpecRegistry (which has access to both axiom capabilities and class
    member tables).
    """

    def __init__(self) -> None:
        self._protocols: Dict[str, ProtocolDef] = {}
        self._version = 0

    @property
    def version(self) -> int:
        """注册表变更版本号（每次 register 递增）——派生索引失效契约。"""
        return self._version

    def register(self, protocol: ProtocolDef) -> ProtocolDef:
        existing = self._protocols.get(protocol.name)
        if existing is not None and existing != protocol:
            # Strict identity: duplicate registration with different shape is a bug.
            raise ValueError(
                f"Protocol '{protocol.name}' is already registered with a different definition"
            )
        self._protocols[protocol.name] = protocol
        self._version += 1
        return protocol

    def get(self, name: str) -> Optional[ProtocolDef]:
        return self._protocols.get(name)

    def names(self) -> List[str]:
        return sorted(self._protocols)

    def all(self) -> Tuple[ProtocolDef, ...]:
        return tuple(self._protocols.values())

    def __contains__(self, name: str) -> bool:
        return name in self._protocols

    def register_from_spec(self, spec: Any) -> Optional[ProtocolDef]:
        """Register a protocol from a PROTOCOL-kind TypeDef.

        The protocol's required methods are derived from the spec's ``members``
        dictionary.  This is the bridge between the type-system representation
        of protocols and the runtime protocol registry.
        """
        name = getattr(spec, "name", None)
        if not name:
            return None
        members = getattr(spec, "members", None) or {}
        methods = tuple(sorted(members.keys()))
        parent_ref = getattr(spec, "parent_type", None)
        parent = parent_ref.head if parent_ref is not None else None
        protocol = ProtocolDef(
            name=name,
            methods=methods,
            description="User-defined protocol",
            parent=parent,
        )
        return self.register(protocol)


# ---------------------------------------------------------------------------
# Built-in protocol definitions
# ---------------------------------------------------------------------------
#
# These names are intentionally stable.  They are the kernel-level identity
# for capabilities that previously lived only as TypeAxiom flags or as
# hard-coded dunder strings.

BUILTIN_PROTOCOLS: Tuple[ProtocolDef, ...] = (
    ProtocolDef(
        name="callable",
        methods=("__call__",),
        description="Values that can be invoked as functions.",
        # 专用路径：SpecRegistry.is_callable（结构化 kind + axiom cap 合成）
    ),
    ProtocolDef(
        name="iterable",
        methods=("__iter__",),
        description="Values that can be iterated with for.",
        kinds=(TypeKind.LIST.value, TypeKind.TUPLE.value, TypeKind.GENERATOR.value),
        axiom_cap="has_iter_cap",
        structural_methods=("__iter__",),
    ),
    ProtocolDef(
        name="subscriptable",
        methods=("__getitem__",),
        description="Values that support obj[key].",
        kinds=(TypeKind.LIST.value, TypeKind.TUPLE.value, TypeKind.DICT.value),
        axiom_cap="has_subscript_cap",
        structural_methods=("__getitem__",),
    ),
    ProtocolDef(
        name="operator",
        methods=(
            "__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__",
            "__mod__", "__pow__", "__and__", "__or__", "__xor__",
            "__lshift__", "__rshift__", "__lt__", "__le__", "__gt__",
            "__ge__", "__eq__", "__ne__", "__neg__", "__pos__",
            "__invert__", "__not__", "__contains__",
        ),
        description="Values that participate in operator dispatch.",
        axiom_cap="has_operator_cap",
    ),
    ProtocolDef(
        name="attribute",
        methods=("__getattr__", "__setattr__"),
        description="Values that support attribute read/write access.",
    ),
    ProtocolDef(
        name="converter",
        methods=("cast_to",),
        description="Values that can participate in explicit casts.",
        axiom_cap="has_converter_cap",
        structural_methods=("cast_to",),
    ),
    ProtocolDef(
        name="parser",
        methods=("parse_value",),
        description="Values that can parse raw text into a typed value.",
        axiom_cap="has_parser_cap",
        structural_methods=("parse_value",),
    ),
    ProtocolDef(
        name="to_prompt",
        methods=("__to_prompt__",),
        description="Values that can render themselves into LLM prompt text.",
        # 通用渲染路径：axiom 能力统一声明（BaseAxiom 默认 True）——所有公理类型
        # 的 __to_prompt__ 均可用；用户类经结构成员判定（spec.members）。
        axiom_cap="has_to_prompt_cap",
    ),
    ProtocolDef(
        name="from_prompt",
        methods=("__from_prompt__",),
        description="Values that can parse LLM output into a typed value.",
        axiom_cap="has_from_prompt_cap",
        structural_methods=("__from_prompt__",),
    ),
    ProtocolDef(
        name="validate_prompt",
        methods=("__validate_prompt__",),
        description="Values that can pre-validate raw LLM output.",
    ),
    ProtocolDef(
        name="output_hint",
        methods=("__outputhint_prompt__",),
        description="Values that can provide an LLM output format hint.",
        axiom_cap="has_output_hint_cap",
        structural_methods=("__outputhint_prompt__",),
    ),
    ProtocolDef(
        name="payload_prompt",
        methods=("__payload_prompt__",),
        description="Values that can provide multi-modal content blocks.",
        axiom_cap="has_payload_prompt_cap",
        structural_methods=("__payload_prompt__",),
    ),
    ProtocolDef(
        name="snapshotable",
        methods=("__snapshot__", "__restore__"),
        description="Values that can participate in llmexcept snapshot/restore.",
        structural_methods=("__snapshot__", "__restore__"),
        structural_all=True,
    ),
    ProtocolDef(
        name="llm_callable",
        methods=("__llm_call__",),
        description=(
            "Values that can be consumed as unified LLM calls (behavior values, "
            "llm callable-class instances, anonymous callable instances).  "
            "``__llm_call__`` is the required method for ``satisfies_protocol("
            "... , 'llm_callable')``（能否被 LLM 消费的唯一判定）;  ``__intent__`` / "
            "``__retry__`` are optional capabilities discovered at runtime via "
            "receive (the required/optional split is formalized later)."
        ),
        structural_methods=("__llm_call__",),
    ),
)


def register_builtin_protocols(registry: ProtocolRegistry) -> None:
    for protocol in BUILTIN_PROTOCOLS:
        registry.register(protocol)

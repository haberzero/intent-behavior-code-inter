"""
core/kernel/spec/registry/__init__.py

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

``SpecRegistry`` is composed from the following mixins (MRO left-to-right):
``_RuntimeMixin``, ``_AssignabilityMixin``, ``_MemberMixin``,
``_InferenceMixin``, ``_CapabilityMixin``, ``SpecRegistryBase``.
All shared state lives on ``SpecRegistryBase`` (see ``_base.py`` for the
shared-state protocol).
"""

from __future__ import annotations

from ._base import SpecRegistryBase
from ._capabilities import _CapabilityMixin
from ._inference import _InferenceMixin
from ._members import _MemberMixin
from ._assignability import _AssignabilityMixin
from ._runtime import _RuntimeMixin, create_default_spec_registry
from .factory import SpecFactory


class SpecRegistry(
    _RuntimeMixin,
    _AssignabilityMixin,
    _MemberMixin,
    _InferenceMixin,
    _CapabilityMixin,
    SpecRegistryBase,
):
    pass


__all__ = ["SpecRegistry", "SpecFactory", "create_default_spec_registry"]

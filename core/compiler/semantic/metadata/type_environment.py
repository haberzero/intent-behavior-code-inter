"""
Type Inference State

Managed inference state for the type checking pass.
Replaces the former TypeEnvironment (which was never used by any pass).

Design principles:
- NOT a constraint solver — no unification, no constraint graph
- Provides auto-return accumulation (existing capability preserved)
- Introduces TypeSlot: single-write-once binding point for controlled
  deferred resolution (-> auto contextual, fn parameter propagation future)
- Core IBCI philosophy: "single lock + axiom dispatch" — TypeSlot locks once
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Any, Tuple


@dataclass(frozen=True)
class TypeSlot:
    """A placeholder for types that may be refined during analysis.

    NOT a constraint-solving variable (no unification).
    Rather: a single-write-once slot that starts as 'pending'
    and locks to a concrete IbSpec after first resolution.

    Usage:
        slot = TypeSlot(name="fn_return")
        locked = slot.lock(int_spec)
        assert locked.resolved is int_spec
        # locked.lock(str_spec) raises TypeSlotConflict
    """
    name: str  # debug label
    bound_to: Optional[Any] = None  # None = pending, IbSpec = locked

    def lock(self, spec: Any) -> 'TypeSlot':
        """Lock this slot to a concrete type. Immutable — returns new slot.

        Raises TypeSlotConflict if already locked to a different type.
        """
        if self.bound_to is not None:
            if self.bound_to is not spec and self.bound_to != spec:
                raise TypeSlotConflict(self, spec)
            return self
        return replace(self, bound_to=spec)

    @property
    def is_locked(self) -> bool:
        """Whether this slot has been resolved."""
        return self.bound_to is not None

    @property
    def resolved(self) -> Optional[Any]:
        """The locked type, or None if still pending."""
        return self.bound_to


class TypeSlotConflict(Exception):
    """Raised when attempting to lock a TypeSlot to a conflicting type."""

    def __init__(self, slot: TypeSlot, attempted_spec: Any):
        self.slot = slot
        self.attempted_spec = attempted_spec
        super().__init__(
            f"TypeSlot '{slot.name}' already locked to "
            f"'{getattr(slot.bound_to, 'name', slot.bound_to)}', "
            f"cannot re-lock to '{getattr(attempted_spec, 'name', attempted_spec)}'"
        )


@dataclass(frozen=True)
class TypeInferenceState:
    """
    Managed inference state for the semantic type checking pass.

    NOT a constraint solver. Provides:
    1. Auto-return accumulation (for `-> auto` function return type inference)
    2. TypeSlot management (for controlled deferred binding)

    Immutable: all mutation methods return new instances.
    """
    # For `-> auto` functions: accumulated return types
    auto_return_accumulator: tuple = ()

    # Named type slots for deferred resolution
    slots: Dict[str, TypeSlot] = field(default_factory=dict)

    @classmethod
    def create_empty(cls) -> 'TypeInferenceState':
        """Create an empty inference state."""
        return cls()

    # ---- Auto-return accumulation (existing capability) ----

    def accumulate_return(self, type_spec: Any) -> 'TypeInferenceState':
        """Accumulate a return type for auto inference (returns new state)."""
        return replace(self, auto_return_accumulator=self.auto_return_accumulator + (type_spec,))

    def get_accumulated_returns(self) -> List[Any]:
        """Get all accumulated return types."""
        return list(self.auto_return_accumulator)

    def clear_auto_accumulator(self) -> 'TypeInferenceState':
        """Clear auto return accumulator (returns new state)."""
        return replace(self, auto_return_accumulator=())

    # ---- TypeSlot management (new: deferred binding) ----

    def create_slot(self, name: str) -> Tuple['TypeInferenceState', TypeSlot]:
        """Create a named TypeSlot. Returns (new_state, slot).

        The slot starts pending and can be locked once.
        """
        slot = TypeSlot(name=name)
        new_slots = {**self.slots, name: slot}
        new_state = replace(self, slots=new_slots)
        return new_state, slot

    def lock_slot(self, name: str, spec: Any) -> 'TypeInferenceState':
        """Lock a named slot to a concrete type. Returns new state.

        Raises KeyError if slot doesn't exist.
        Raises TypeSlotConflict if slot is already locked to different type.
        """
        if name not in self.slots:
            raise KeyError(f"TypeSlot '{name}' not found")
        locked = self.slots[name].lock(spec)
        new_slots = {**self.slots, name: locked}
        return replace(self, slots=new_slots)

    def get_slot(self, name: str) -> Optional[TypeSlot]:
        """Get a named TypeSlot, or None if not found."""
        return self.slots.get(name)

    # ---- Compatibility / diagnostics ----

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for diagnostics."""
        return {
            'auto_returns': len(self.auto_return_accumulator),
            'slots': {name: slot.is_locked for name, slot in self.slots.items()},
        }

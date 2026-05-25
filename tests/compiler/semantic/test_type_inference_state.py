"""
Tests for TypeInferenceState and TypeSlot.

Validates:
- TypeSlot single-lock semantics
- TypeInferenceState auto-return accumulation
- TypeSlot creation and resolution
- TypeSlotConflict on double-lock with different types
- Backward compatibility alias (TypeEnvironment = TypeInferenceState)
"""

import pytest
from core.compiler.semantic.metadata import TypeInferenceState, TypeEnvironment, TypeSlot, TypeSlotConflict


class TestTypeSlot:
    """TypeSlot: single-write-once binding point."""

    def test_slot_starts_pending(self):
        slot = TypeSlot(name="test")
        assert not slot.is_locked
        assert slot.resolved is None

    def test_slot_locks_once(self):
        slot = TypeSlot(name="test")
        locked = slot.lock("int_spec")
        assert locked.is_locked
        assert locked.resolved == "int_spec"

    def test_slot_immutable_original_unchanged(self):
        slot = TypeSlot(name="test")
        locked = slot.lock("int_spec")
        # Original slot is unchanged (frozen dataclass)
        assert not slot.is_locked
        assert locked.is_locked

    def test_slot_relock_same_type_ok(self):
        slot = TypeSlot(name="test")
        locked = slot.lock("int_spec")
        # Re-locking to same type is idempotent
        same = locked.lock("int_spec")
        assert same.resolved == "int_spec"

    def test_slot_relock_different_type_raises(self):
        slot = TypeSlot(name="test")
        locked = slot.lock("int_spec")
        with pytest.raises(TypeSlotConflict) as exc_info:
            locked.lock("str_spec")
        assert "test" in str(exc_info.value)
        assert "int_spec" in str(exc_info.value)


class TestTypeInferenceState:
    """TypeInferenceState: managed inference state."""

    def test_create_empty(self):
        state = TypeInferenceState.create_empty()
        assert state.auto_return_accumulator == ()
        assert state.slots == {}

    def test_auto_return_accumulation(self):
        state = TypeInferenceState.create_empty()
        state2 = state.accumulate_return("int")
        state3 = state2.accumulate_return("str")
        # Original unchanged (immutable)
        assert state.get_accumulated_returns() == []
        assert state3.get_accumulated_returns() == ["int", "str"]

    def test_clear_auto_accumulator(self):
        state = TypeInferenceState.create_empty()
        state2 = state.accumulate_return("int").accumulate_return("str")
        cleared = state2.clear_auto_accumulator()
        assert cleared.get_accumulated_returns() == []

    def test_create_slot(self):
        state = TypeInferenceState.create_empty()
        new_state, slot = state.create_slot("return_type")
        assert slot.name == "return_type"
        assert not slot.is_locked
        assert "return_type" in new_state.slots

    def test_lock_slot(self):
        state = TypeInferenceState.create_empty()
        state, _slot = state.create_slot("T")
        locked_state = state.lock_slot("T", "int_spec")
        assert locked_state.get_slot("T").is_locked
        assert locked_state.get_slot("T").resolved == "int_spec"

    def test_lock_nonexistent_slot_raises(self):
        state = TypeInferenceState.create_empty()
        with pytest.raises(KeyError):
            state.lock_slot("nonexistent", "int_spec")

    def test_to_dict(self):
        state = TypeInferenceState.create_empty()
        state = state.accumulate_return("int")
        state, _ = state.create_slot("T")
        d = state.to_dict()
        assert d['auto_returns'] == 1
        assert d['slots'] == {'T': False}

    def test_immutability(self):
        """TypeInferenceState is frozen — no in-place mutation."""
        import dataclasses
        state = TypeInferenceState.create_empty()
        with pytest.raises(dataclasses.FrozenInstanceError):
            state.auto_return_accumulator = ("hack",)


class TestBackwardCompatibility:
    """TypeEnvironment alias still works for existing code."""

    def test_alias_is_same_class(self):
        assert TypeEnvironment is TypeInferenceState

    def test_old_construction_pattern(self):
        # This pattern is used in test_symbol_collection_pass.py
        env = TypeEnvironment()
        assert env.get_accumulated_returns() == []

    def test_create_empty_works(self):
        env = TypeEnvironment.create_empty()
        assert isinstance(env, TypeInferenceState)

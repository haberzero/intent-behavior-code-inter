"""
tests/runtime/test_ib_cell.py

Unit tests for ``core/runtime/objects/cell.py``.

Coverage:
  - Empty-cell construction and is_empty()
  - Initialized-cell construction
  - get / set round-trip
  - Reading from empty cell raises a meaningful RuntimeError
  - Multiple references share state (closure-sharing semantics, axiom SC-3/SC-4)
  - Identity-based equality / hashability
  - trace_refs() yields current value (non-empty) or nothing (empty)
  - __repr__ does not raise and reflects state
  - Cell holding another cell (nesting)
  - set() to new value replaces previous reference, get() reflects latest

These tests intentionally do NOT depend on KernelRegistry / IbObject —
``IbCell`` is a pure VM container and its contract is independent of the
IBCI type system.
"""

import pytest

from core.runtime.objects.cell import IbCell


# ---------------------------------------------------------------------------
# Construction & emptiness
# ---------------------------------------------------------------------------


def test_default_construction_is_empty():
    cell = IbCell()
    assert cell.is_empty() is True


def test_initialized_construction_is_not_empty():
    cell = IbCell(42)
    assert cell.is_empty() is False


def test_empty_sentinel_is_singleton():
    # Two empty cells share the same EMPTY sentinel reachable via the class.
    a = IbCell()
    b = IbCell()
    assert a.is_empty() and b.is_empty()
    # Sentinel exposed on the class is identity-stable.
    assert IbCell.EMPTY is IbCell.EMPTY
    # And both empty cells store that same sentinel internally.
    assert a._value is b._value is IbCell.EMPTY


# ---------------------------------------------------------------------------
# get / set
# ---------------------------------------------------------------------------


def test_get_returns_initial_value():
    cell = IbCell("hello")
    assert cell.get() == "hello"


def test_set_then_get_round_trip():
    cell = IbCell()
    cell.set(7)
    assert cell.is_empty() is False
    assert cell.get() == 7
    cell.set(8)
    assert cell.get() == 8


def test_get_from_empty_cell_raises():
    cell = IbCell()
    with pytest.raises(RuntimeError, match="IbCell read before initialization"):
        cell.get()


def test_set_does_not_box_or_transform():
    # Cell is a pure container; whatever is stored is what comes back.
    sentinel = object()
    cell = IbCell()
    cell.set(sentinel)
    assert cell.get() is sentinel


# ---------------------------------------------------------------------------
# Sharing semantics (SC-3 / SC-4)
# ---------------------------------------------------------------------------


def test_shared_cell_reflects_writes_through_any_alias():
    """Multiple closures holding the SAME IbCell see each other's writes."""
    cell = IbCell(1)
    alias_a = cell
    alias_b = cell
    alias_a.set(99)
    assert alias_b.get() == 99
    assert cell.get() == 99


def test_distinct_cells_are_independent():
    """Two cells with equal values are nonetheless independent stores."""
    c1 = IbCell(10)
    c2 = IbCell(10)
    c1.set(20)
    assert c2.get() == 10  # untouched


# ---------------------------------------------------------------------------
# Identity semantics
# ---------------------------------------------------------------------------


def test_distinct_cells_with_equal_values_are_not_equal():
    c1 = IbCell(5)
    c2 = IbCell(5)
    assert c1 != c2
    assert not (c1 == c2)


def test_same_cell_equals_itself():
    cell = IbCell(5)
    assert cell == cell


def test_cell_is_hashable_and_usable_as_dict_key():
    c1 = IbCell(1)
    c2 = IbCell(1)
    bucket = {c1: "first", c2: "second"}
    assert bucket[c1] == "first"
    assert bucket[c2] == "second"
    assert len(bucket) == 2


# ---------------------------------------------------------------------------
# trace_refs (GC hook for M2)
# ---------------------------------------------------------------------------


def test_trace_refs_empty_yields_nothing():
    cell = IbCell()
    assert list(cell.trace_refs()) == []


def test_trace_refs_initialized_yields_value():
    obj = object()
    cell = IbCell(obj)
    refs = list(cell.trace_refs())
    assert len(refs) == 1
    assert refs[0] is obj


def test_trace_refs_after_set_reflects_new_value():
    a = object()
    b = object()
    cell = IbCell(a)
    cell.set(b)
    refs = list(cell.trace_refs())
    assert refs == [b]


# ---------------------------------------------------------------------------
# Nesting
# ---------------------------------------------------------------------------


def test_cell_can_hold_another_cell():
    inner = IbCell("nested")
    outer = IbCell(inner)
    got = outer.get()
    assert got is inner
    assert got.get() == "nested"


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------


def test_repr_empty_does_not_raise_and_marks_empty():
    s = repr(IbCell())
    assert "IbCell" in s
    assert "EMPTY" in s


def test_repr_initialized_includes_value():
    s = repr(IbCell(123))
    assert "IbCell" in s
    assert "123" in s

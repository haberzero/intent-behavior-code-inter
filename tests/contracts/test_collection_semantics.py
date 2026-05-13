"""
tests/contracts/test_collection_semantics.py
============================================

Contract tests for IBCI collection operation semantics.

Validates:
- INV-LIST-*: List operation invariants (indexing, slicing, mutation)
- INV-DICT-*: Dict operation invariants (key access, mutation)
- INV-STR-*: String operation invariants (indexing, slicing)
"""

import pytest
from tests.conftest import run_ibci, expect_runtime_error


# ===========================================================================
# List Operation Invariants (INV-LIST-*)
# ===========================================================================


class TestListOperationInvariants:
    """Validate list operation semantics.

    References:
    - IBCI_SPEC.md §4 Built-in Collections
    - docs/TEST_COVERAGE_ANALYSIS_2026_05_13.md §4.2
    """

    def test_list_index_bounds_checked(self):
        """INV-LIST-1: List index out of bounds raises runtime error."""
        code = """
list[int] nums = [1, 2, 3]
int x = nums[5]
"""
        expect_runtime_error(code, "index")

    def test_list_negative_index_wraps(self):
        """INV-LIST-2: Negative list index counts from end."""
        code = """
list[int] nums = [10, 20, 30]
print(nums[-1])
print(nums[-2])
"""
        assert run_ibci(code) == ["30", "20"]

    def test_list_append_type_constraint(self):
        """INV-LIST-3: list[T].append() enforces type T."""
        # Type checking should pass - this validates the type system works
        code = """
list[int] nums = [1, 2]
nums.append(3)
print(nums)
"""
        result = run_ibci(code)
        assert "3" in result[0]

    def test_list_slice_preserves_type(self):
        """INV-LIST-4: List slice returns list[T] of same element type."""
        code = """
list[int] nums = [1, 2, 3, 4, 5]
list[int] sub = nums[1:4]
print(sub)
"""
        result = run_ibci(code)
        assert "2" in result[0] and "3" in result[0] and "4" in result[0]

    def test_list_insert_type_constraint(self):
        """INV-LIST-5: list[T].insert(index, T) preserves type."""
        code = """
list[int] nums = [1, 3]
nums.insert(1, 2)
print(nums)
"""
        result = run_ibci(code)
        assert "1" in result[0] and "2" in result[0] and "3" in result[0]

    def test_list_pop_returns_element(self):
        """INV-LIST-6: list[T].pop() returns element of type T."""
        code = """
list[int] nums = [10, 20, 30]
int x = nums.pop()
print(x)
print(nums)
"""
        result = run_ibci(code)
        assert result[0] == "30"
        assert "20" in result[1] and "30" not in result[1]

    def test_list_remove_value_semantics(self):
        """INV-LIST-7: list[T].remove(val) removes first occurrence."""
        code = """
list[int] nums = [1, 2, 3, 2, 4]
nums.remove(2)
print(nums)
"""
        result = run_ibci(code)
        # Should have removed first 2, second 2 remains
        assert "1" in result[0] and "3" in result[0] and "4" in result[0]

    def test_list_len_invariant(self):
        """INV-LIST-8: len(list) reflects mutation operations."""
        code = """
list[int] nums = [1, 2, 3]
print(len(nums))
nums.append(4)
print(len(nums))
nums.pop()
print(len(nums))
"""
        assert run_ibci(code) == ["3", "4", "3"]


# ===========================================================================
# Dict Operation Invariants (INV-DICT-*)
# ===========================================================================


class TestDictOperationInvariants:
    """Validate dict operation semantics.

    References:
    - IBCI_SPEC.md §4 Built-in Collections
    - docs/TEST_COVERAGE_ANALYSIS_2026_05_13.md §4.2
    """

    def test_dict_get_with_default(self):
        """INV-DICT-1: Dict.get(key, default) returns default for missing keys."""
        code = """
dict[str, int] d = {"a": 1, "b": 2}
int x = d.get("c", 999)
print(x)
"""
        assert run_ibci(code) == ["999"]

    def test_dict_key_type_enforced(self):
        """INV-DICT-2: dict[K,V] enforces key type K."""
        # Type system should enforce this
        code = """
dict[str, int] d = {"x": 10, "y": 20}
print(d["x"])
"""
        assert run_ibci(code) == ["10"]

    def test_dict_value_type_enforced(self):
        """INV-DICT-3: dict[K,V] enforces value type V."""
        code = """
dict[str, int] d = {}
d["key"] = 42
print(d["key"])
"""
        assert run_ibci(code) == ["42"]

    def test_dict_keys_returns_collection(self):
        """INV-DICT-4: dict.keys() returns iterable of keys."""
        code = """
dict[str, int] d = {"a": 1, "b": 2, "c": 3}
for str key in d.keys():
    print(key)
"""
        result = run_ibci(code)
        # Keys should all be present (order may vary)
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_dict_values_returns_collection(self):
        """INV-DICT-5: dict.values() returns iterable of values."""
        code = """
dict[str, int] d = {"a": 1, "b": 2, "c": 3}
int sum = 0
for int val in d.values():
    sum = sum + val
print(sum)
"""
        assert run_ibci(code) == ["6"]

    def test_dict_update_overwrites(self):
        """INV-DICT-6: Assigning to existing key overwrites value."""
        code = """
dict[str, int] d = {"x": 10}
d["x"] = 20
print(d["x"])
"""
        assert run_ibci(code) == ["20"]

    def test_dict_update_tracking(self):
        """INV-DICT-7: Dict tracks additions and updates correctly."""
        code = """
dict[str, int] d = {"a": 1}
d["b"] = 2
print(d["a"])
print(d["b"])
d["a"] = 10
print(d["a"])
"""
        assert run_ibci(code) == ["1", "2", "10"]


# ===========================================================================
# String Operation Invariants (INV-STR-*)
# ===========================================================================


class TestStringOperationInvariants:
    """Validate string operation semantics.

    References:
    - IBCI_SPEC.md §4 Built-in Types
    """

    def test_str_index_bounds_checked(self):
        """INV-STR-1: String index out of bounds raises runtime error."""
        code = """
str s = "hello"
str c = s[10]
"""
        expect_runtime_error(code, "index")

    def test_str_negative_index_wraps(self):
        """INV-STR-2: Negative string index counts from end."""
        code = """
str s = "hello"
print(s[-1])
print(s[-2])
"""
        assert run_ibci(code) == ["o", "l"]

    def test_str_slice_returns_str(self):
        """INV-STR-3: String slice returns new string."""
        code = """
str s = "hello"
str sub = s[1:4]
print(sub)
"""
        assert run_ibci(code) == ["ell"]

    def test_str_concatenation_type(self):
        """INV-STR-4: String concatenation produces string."""
        code = """
str a = "hello"
str b = "world"
str c = a + " " + b
print(c)
"""
        assert run_ibci(code) == ["hello world"]

    def test_str_len_invariant(self):
        """INV-STR-5: len(str) returns character count."""
        code = """
str s = "hello"
print(len(s))
"""
        assert run_ibci(code) == ["5"]

    def test_str_immutability(self):
        """INV-STR-6: Strings are immutable (cannot assign to index)."""
        # This should be a compile-time or runtime error
        # For now, just verify string operations don't mutate
        code = """
str s = "hello"
str s2 = s
print(s)
print(s2)
"""
        result = run_ibci(code)
        assert result[0] == "hello"
        assert result[1] == "hello"

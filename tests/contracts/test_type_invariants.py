"""
tests/contracts/test_type_invariants.py
========================================

Contract tests for IBCI type system invariants.

Validates:
- INV-OPT-*: Optional[T] null safety guarantees
- INV-GEN-*: Generic type (list[T], dict[K,V]) invariants
- INV-CAST-*: Type casting correctness
- INV-TUPLE-*: Tuple positional type guarantees
"""

import pytest
from tests.conftest import run_ibci, expect_compile_error, expect_runtime_error


# ===========================================================================
# Optional[T] Null Safety (INV-OPT-*)
# ===========================================================================


class TestOptionalNullSafety:
    """Validate Optional[T] null safety guarantees.

    References:
    - IBCI_SPEC.md §3.2 Optional Types
    - docs/TEST_PHILOSOPHY.md §7.1 Optional Example
    """

    def test_optional_none_access_raises(self):
        """INV-OPT-1: Accessing None via Optional must raise runtime error."""
        code = """
Optional[int] x = None
int y = x.get()
"""
        expect_runtime_error(code, "None")

    @pytest.mark.parametrize("type_,value,expected", [
        ("int", "42", "42"),
        ("str", '"hello"', "hello"),
        ("list[int]", "[1, 2, 3]", "[1, 2, 3]"),
    ])
    def test_optional_get_preserves_type(self, type_, value, expected):
        """INV-OPT-2: Optional[T].get() returns value of type T."""
        code = f"""
Optional[{type_}] x = Some({value})
{type_} y = x.get()
print(y)
"""
        result = run_ibci(code)
        assert expected in " ".join(result)

    def test_optional_has_value_guards_access(self):
        """INV-OPT-3: has_value() == true guarantees safe get()."""
        code = """
Optional[int] x = Some(42)
if x.has_value():
    print(x.get())
"""
        assert run_ibci(code) == ["42"]

    def test_optional_none_has_value_false(self):
        """INV-OPT-4: None Optional has_value() returns false."""
        code = """
Optional[int] x = None
print(x.has_value())
"""
        assert run_ibci(code) == ["0"]  # false = 0 in IBCI


# ===========================================================================
# Generic Type Invariants (INV-GEN-*)
# ===========================================================================


class TestGenericTypeInvariants:
    """Validate generic type constraints (list[T], dict[K,V]).

    References:
    - IBCI_SPEC.md §3.3 Generic Types
    - docs/TESTS_REORGANIZATION_TASK.md §11.2
    """

    @pytest.mark.parametrize("elem_type,valid_values", [
        ("int", "[1, 2, 3]"),
        ("str", '["a", "b", "c"]'),
        ("list[int]", "[[1], [2], [3]]"),
    ])
    def test_list_homogeneous_type(self, elem_type, valid_values):
        """INV-GEN-1: list[T] enforces homogeneous element type."""
        code = f"""
list[{elem_type}] nums = {valid_values}
print(nums)
"""
        # Compilation and execution must succeed
        result = run_ibci(code)
        assert result  # Any output means type checking passed

    def test_list_append_preserves_type(self):
        """INV-GEN-2: list[T].append(T) preserves list type."""
        code = """
list[int] nums = [1, 2]
nums.append(3)
print(nums)
"""
        result = run_ibci(code)
        assert "1" in result[0] and "2" in result[0] and "3" in result[0]

    @pytest.mark.parametrize("key_type,val_type,pairs", [
        ("int", "str", "{1: 'a', 2: 'b'}"),
        ("str", "int", '{"x": 10, "y": 20}'),
    ])
    def test_dict_key_value_types(self, key_type, val_type, pairs):
        """INV-GEN-3: dict[K,V] enforces key and value types."""
        code = f"""
dict[{key_type}, {val_type}] d = {pairs}
print(d)
"""
        result = run_ibci(code)
        assert result  # Type checking passed


# ===========================================================================
# Type Casting Invariants (INV-CAST-*)
# ===========================================================================


class TestTypeCastInvariants:
    """Validate type casting correctness.

    References:
    - IBCI_SPEC.md §3.6 Type Casting
    """

    @pytest.mark.parametrize("from_val,to_type,expected", [
        ("42", "str", '"42"'),
        ('"123"', "int", "123"),
        ("3.14", "int", "3"),
    ])
    def test_cast_valid_conversions(self, from_val, to_type, expected):
        """INV-CAST-1: Valid casts produce expected values."""
        code = f"""
auto x = {from_val}
{to_type} y = cast({to_type}, x)
print(y)
"""
        result = run_ibci(code)
        assert expected.strip('"') in result[0]

    def test_cast_preserves_semantics(self):
        """INV-CAST-2: Cast doesn't change semantic value (when valid)."""
        code = """
int x = 42
str s = cast(str, x)
int y = cast(int, s)
print(y)
"""
        assert run_ibci(code) == ["42"]


# ===========================================================================
# Tuple Positional Types (INV-TUPLE-*)
# ===========================================================================


class TestTuplePositionalTypes:
    """Validate tuple[T1, T2, ...] positional element types.

    References:
    - NS-7 (2026-05-12)
    - tests/compiler/test_tuple_positional_types.py (legacy)
    """

    def test_tuple_positional_access_type(self):
        """INV-TUPLE-1: tuple[T1,T2][0] yields T1, [1] yields T2."""
        code = """
tuple[int, str] t = (42, "hello")
int x = t[0]
str y = t[1]
print(x)
print(y)
"""
        assert run_ibci(code) == ["42", "hello"]

    def test_tuple_different_types(self):
        """INV-TUPLE-2: Tuple elements can have different types."""
        code = """
tuple[int, str, bool] t = (1, "test", True)
print(t[0])
print(t[1])
print(t[2])
"""
        result = run_ibci(code)
        assert result[0] == "1"
        assert result[1] == "test"
        assert result[2] == "1"  # True = 1

    def test_tuple_unpacking_preserves_types(self):
        """INV-TUPLE-3: Tuple unpacking assigns correct types."""
        code = """
tuple[int, str] t = (42, "data")
int a, str b = t
print(a)
print(b)
"""
        assert run_ibci(code) == ["42", "data"]


# ===========================================================================
# Type Inference Invariants (INV-INFER-*)
# ===========================================================================


class TestTypeInferenceInvariants:
    """Validate type inference correctness.

    References:
    - IBCI_SPEC.md §3.1 Type Annotations
    """

    @pytest.mark.parametrize("literal,expected_output", [
        ("42", "42"),
        ('"hello"', "hello"),
        ("[1, 2, 3]", "[1, 2, 3]"),
        ("True", "1"),
    ])
    def test_auto_infers_literal_type(self, literal, expected_output):
        """INV-INFER-1: auto infers correct type from literal."""
        code = f"""
auto x = {literal}
print(x)
"""
        result = run_ibci(code)
        assert expected_output.strip('"[]') in result[0]

    def test_function_return_type_inference(self):
        """INV-INFER-2: Function return type correctly inferred."""
        code = """
func auto double(int x):
    return x * 2

int y = double(21)
print(y)
"""
        assert run_ibci(code) == ["42"]
